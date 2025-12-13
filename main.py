import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from engines.topic_engine import TitleThumbnailEngine
from engines.profile_engine import ContentProfileEngine
from engines.script_engine import ScriptEngine
from engines.image_engine import ImageEngine
from engines.video_clip_engine import VideoClipEngine
from engines.tts_engine import TTSEngine
from engines.video_engine import VideoRenderEngine
from engines.subtitle_engine import SubtitleEngine
from engines.parallax_engine import ParallaxEngine
from engines.youtube_metadata_engine import YouTubeMetadataEngine
from utils.logger import setup_logger


logger = setup_logger()


def run_pipeline(keyword: str, duration_minutes: int = 15, mode_id: str = "senior_kr_v1"):
    """
    전체 파이프라인 실행

    Args:
        keyword: 주제어
        duration_minutes: 영상 길이 (분)
        mode_id: 모드 ID (senior_kr_v1, history_kr_v1, drama_kr_v1)

    Returns:
        결과 딕셔너리
    """
    logger.info(f"Starting pipeline - Keyword: {keyword}, Duration: {duration_minutes}min, Mode: {mode_id}")

    # 출력 디렉토리 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"{keyword.replace(' ', '_')}_{timestamp}"
    export_dir = os.path.join("export", project_name)

    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(os.path.join(export_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(export_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(export_dir, "videos"), exist_ok=True)

    # 1) 제목/썸네일/스코어
    logger.info("[1/9] Generating title and thumbnail...")
    tt_engine = TitleThumbnailEngine()
    title_block = tt_engine.generate(keyword)
    logger.info(f"Title: {title_block.final_title}")

    # 2) 프로필(시니어 템플릿 등)
    logger.info("[2/9] Building content profile...")
    profile_engine = ContentProfileEngine()
    profile = profile_engine.build_profile(keyword, mode_id=mode_id, duration_minutes=duration_minutes)
    logger.info(f"Profile: {profile.template_id}, Category: {profile.category}, Duration: {profile.duration_sec}s")

    # 3) 시나리오 (B-roll 쿼리 포함)
    logger.info("[3/9] Generating script...")
    script_engine = ScriptEngine()
    script = script_engine.generate(profile, title_block)
    logger.info(f"Script generated: {len(script.scenes)} scenes")

    # B-roll 사용 scene 수 계산
    broll_count = sum(1 for s in script.scenes if getattr(s, 'use_video', False))
    logger.info(f"B-roll videos: {broll_count}/{len(script.scenes)} scenes")

    # 4) 이미지 생성
    logger.info("[4/9] Generating images...")
    image_engine = ImageEngine()
    image_paths, image_event_logs = image_engine.generate_scene_images(
        script.scenes,
        os.path.join(export_dir, "images"),
        category=profile.category,
        profile=profile  # ★ 통합 설정 전달
    )

    # 5) B-roll 비디오 다운로드
    logger.info("[5/9] Downloading B-roll videos...")
    video_clip_engine = VideoClipEngine()
    video_paths = video_clip_engine.search_and_download_clips(
        script.scenes,
        os.path.join(export_dir, "videos")
    )
    logger.info(f"Downloaded {len(video_paths)} B-roll videos")

    # 6) 썸네일 생성 (스크립트 기반 컨텍스트 반영)
    logger.info("[6/9] Generating thumbnail (context-aware)...")

    # 스크립트 내용을 분석하여 맥락에 맞는 썸네일 생성
    thumbnail_text, thumbnail_image_prompt = tt_engine.generate_contextual_thumbnail(
        script, profile.category, keyword
    )

    thumbnail_path = image_engine.generate_thumbnail(
        thumbnail_image_prompt,
        thumbnail_text,
        os.path.join(export_dir, "thumbnail.png"),
        category=profile.category
    )

    # 썸네일 정보 업데이트 (메타데이터용)
    title_block.thumbnail_text = thumbnail_text
    title_block.thumbnail_image_prompt = thumbnail_image_prompt

    # 7) TTS 음성 생성
    logger.info("[7/9] Generating audio...")
    tts_engine = TTSEngine()

    # ★ 15분 이상 영상: 파트별 TTS 생성 (동적 분배)
    # 실제 생성된 scenes를 4등분하여 기승전결 분배
    def create_dynamic_part_boundaries(scenes):
        """실제 생성된 scenes를 4등분하여 파트별 인덱스 반환"""
        total = len(scenes)
        if total == 0:
            return {}

        # 4등분 (나머지는 마지막 파트에 할당)
        part_size = total // 4
        remainder = total % 4

        boundaries = {}
        start = 0
        for i, part_name in enumerate(["기", "승", "전", "결"]):
            # 마지막 파트에 나머지 할당
            end = start + part_size + (1 if i < remainder else 0)
            if i == 3:  # 결 파트는 나머지 전부
                end = total
            boundaries[part_name] = list(range(start, end))
            start = end

        return boundaries

    # ★ TTS 실패 시 파이프라인 중단
    try:
        if profile.duration_sec >= 900:
            logger.info("[TTS] ★ 파트별 TTS 병렬 생성 모드 (4 workers)")
            audio_files = []
            part_audio_groups = {}  # 파트별 오디오 그룹

            # 동적으로 파트 경계 생성
            PART_INDICES = create_dynamic_part_boundaries(script.scenes)
            logger.info(f"[TTS] 동적 파트 분배: {len(script.scenes)}개 씬 → {{{', '.join(f'{k}:{len(v)}개' for k,v in PART_INDICES.items())}}}")

            # ★ 병렬 TTS 생성 함수
            def generate_part_audio(part_name, indices):
                part_scenes = [script.scenes[i] for i in indices]
                if not part_scenes:
                    return part_name, [], indices
                logger.info(f"[TTS] === 파트 '{part_name}' 시작 ({len(part_scenes)}개 씬) ===")
                part_audios = tts_engine.generate_audio(
                    part_scenes,
                    profile,
                    os.path.join(export_dir, "audio")
                )
                total_duration = sum(a.get('duration', 0) for a in part_audios)
                logger.info(f"[TTS] 파트 '{part_name}' 완료: {total_duration:.1f}초")
                return part_name, part_audios, indices

            # ★ 순차 처리: Gemini API RPM(분당 요청) 제한 준수
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures = {
                    executor.submit(generate_part_audio, part_name, indices): part_name
                    for part_name, indices in PART_INDICES.items()
                }

                results = {}
                for future in as_completed(futures):
                    part_name, part_audios, indices = future.result()
                    results[part_name] = (part_audios, indices)
                    part_audio_groups[part_name] = part_audios

            # 파트 순서대로 audio_files 정렬 (기→승→전→결)
            for part_name in ["기", "승", "전", "결"]:
                if part_name in results:
                    audio_files.extend(results[part_name][0])
        else:
            audio_files = tts_engine.generate_audio(
                script.scenes,
                profile,
                os.path.join(export_dir, "audio")
            )
    except RuntimeError as e:
        logger.error(f"[TTS] ✗ TTS 생성 실패로 파이프라인 중단: {e}")
        print("\n" + "=" * 60)
        print("❌ TTS 생성 실패 - 파이프라인 중단")
        print(f"   오류: {e}")
        print("   → Gemini API 할당량 초과일 수 있습니다.")
        print("   → 잠시 후 다시 시도하거나 다른 TTS 엔진을 선택하세요.")
        print("=" * 60 + "\n")
        return None

    # 7.5) 2.5D/Parallax 모션 효과 (중요 장면)
    parallax_enabled = os.getenv("PARALLAX_ENABLED", "true").lower() == "true"
    parallax_clips = {}

    if parallax_enabled:
        logger.info("[7.5/9] Applying Parallax motion effects...")
        parallax_engine = ParallaxEngine(enabled=True)

        # 오디오 duration 리스트 생성
        audio_durations = [
            audio_files[idx].get("duration", script.scenes[idx].duration_sec)
            if idx < len(audio_files) else script.scenes[idx].duration_sec
            for idx in range(len(script.scenes))
        ]

        parallax_clips = parallax_engine.process_scene_images(
            script.scenes,
            image_paths,
            audio_durations,
            os.path.join(export_dir, "parallax")
        )

        if parallax_clips:
            logger.info(f"Parallax effects applied to {len(parallax_clips)} scenes")
            # Parallax 클립을 video_paths에 병합 (parallax 우선)
            for idx, clip_path in parallax_clips.items():
                video_paths[idx] = clip_path
    else:
        logger.info("[7.5/9] Parallax effects disabled")

    # 8) 자막 생성 (시니어 모드)
    subtitle_mode = os.getenv("SUBTITLE_MODE", "highlight")
    subtitle_size = os.getenv("SUBTITLE_SIZE", "auto")
    subtitle_path = None

    # 해상도 파싱
    resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
    width, height = map(int, resolution.split("x"))

    # ★ 15분 이상 영상: 파트별 비디오+자막 처리 (싱크 오차 최소화)
    if profile.duration_sec >= 900:
        logger.info("[8-9/9] ★ 파트별 비디오+자막 생성 모드 (싱크 오차 최소화)")

        video_engine = VideoRenderEngine()
        subtitle_engine = SubtitleEngine(font_size_preset=subtitle_size)
        part_video_paths = []

        # 동적 파트 인덱스 사용 (TTS 생성 시 사용한 것과 동일)
        for part_name, part_indices in PART_INDICES.items():
            if not part_indices:
                continue

            logger.info(f"[파트 {part_name}] === 씬 인덱스 {part_indices} 처리 중 ===")

            # 파트별 데이터 추출 (인덱스 기반)
            part_scenes = [script.scenes[i] for i in part_indices]
            part_images = [image_paths[i] for i in part_indices if i < len(image_paths)]
            # ★ part_audio_groups에서 해당 파트의 오디오 가져오기
            part_audios = part_audio_groups.get(part_name, [])
            part_videos = {idx: video_paths[orig_idx] for idx, orig_idx in enumerate(part_indices)
                          if orig_idx in video_paths}

            # 파트별 오디오 총 길이
            part_audio_dur = sum(a.get("duration", 0) for a in part_audios)
            logger.info(f"[파트 {part_name}] 오디오 총 길이: {part_audio_dur:.1f}초")

            # ★ 씬별 자막 모드 사용 (싱크 오차 방지) - 모든 자막 모드에 적용
            # per_scene_subtitle=True면 각 클립에 자막 번인 후 합치기
            use_per_scene_subtitle = subtitle_mode in ["full_highlight", "full", "highlight"] and subtitle_mode != "none"

            # 폴백: 기존 방식 (파트별 자막 생성)
            part_subtitle_path = None
            if subtitle_mode != "none" and not use_per_scene_subtitle:
                part_subtitle_path = os.path.join(export_dir, f"subtitles_{part_name}.ass")

                if subtitle_mode == "full_highlight":
                    subtitle_engine.generate_full_highlight_subtitles(
                        part_scenes,
                        part_audios,
                        part_subtitle_path,
                        width,
                        height
                    )
                elif subtitle_mode == "full":
                    subtitle_engine.generate_full_subtitles(
                        part_scenes,
                        part_audios,
                        part_subtitle_path,
                        width,
                        height
                    )
                elif subtitle_mode == "highlight":
                    all_subtitles = []
                    current_offset = 0.0
                    for idx, scene in enumerate(part_scenes):
                        if idx < len(part_audios):
                            scene_duration = part_audios[idx].get("duration", scene.duration_sec)
                        else:
                            scene_duration = scene.duration_sec
                        scene_subs = subtitle_engine.generate_scene_subtitles(
                            narration=scene.narration,
                            scene_id=scene.scene_id,
                            scene_duration=scene_duration,
                            start_offset=current_offset,
                            emotion_tag=getattr(scene, 'emotion_tag', 'warm')
                        )
                        all_subtitles.extend(scene_subs)
                        current_offset += scene_duration
                    if all_subtitles:
                        subtitle_engine.save_ass_file(all_subtitles, part_subtitle_path, width, height)

                logger.info(f"[파트 {part_name}] 자막 생성 완료: {part_subtitle_path}")

            # ★ 파트별 비디오 렌더링
            part_video_path = os.path.join(export_dir, f"video_{part_name}.mp4")

            # 파트용 임시 ScriptResult 생성
            from models.types import ScriptResult
            part_script = ScriptResult(
                profile=script.profile,
                final_title=script.final_title,
                scenes=part_scenes,
                character_profile=script.character_profile
            )

            video_engine.render_video(
                part_images,
                part_audios,
                part_script,
                part_video_path,
                resolution=resolution,
                video_paths=part_videos,
                subtitle_path=part_subtitle_path,
                subtitle_engine=subtitle_engine if use_per_scene_subtitle else None,
                per_scene_subtitle=use_per_scene_subtitle,
                subtitle_mode=subtitle_mode
            )

            if os.path.exists(part_video_path):
                part_video_paths.append(part_video_path)
                logger.info(f"[파트 {part_name}] 비디오 렌더링 완료: {part_video_path}")

        # ★ 모든 파트 비디오 합치기
        logger.info(f"[최종] {len(part_video_paths)}개 파트 비디오 합치는 중...")
        video_path = os.path.join(export_dir, "video.mp4")
        if len(part_video_paths) > 1:
            video_engine._concat_clips(part_video_paths, video_path)
        elif len(part_video_paths) == 1:
            import shutil
            shutil.copy(part_video_paths[0], video_path)
        else:
            logger.error("[최종] 파트 비디오가 없습니다!")
            video_path = None

        logger.info(f"[최종] ✓ 파트별 영상 합치기 완료: {video_path}")

    else:
        # 15분 미만: 기존 방식 (한 번에 처리)
        if subtitle_mode != "none":
            logger.info(f"[8/9] Generating subtitles ({subtitle_mode} mode, size: {subtitle_size})...")
            subtitle_engine = SubtitleEngine(font_size_preset=subtitle_size)

            if subtitle_mode == "highlight":
                # 하이라이트 감성 자막 (1~3 단어 키워드)
                all_subtitles = []
                current_offset = 0.0

                for idx, scene in enumerate(script.scenes):
                    # 실제 오디오 duration 사용
                    if idx < len(audio_files):
                        scene_duration = audio_files[idx].get("duration", scene.duration_sec)
                    else:
                        scene_duration = scene.duration_sec

                    scene_subs = subtitle_engine.generate_scene_subtitles(
                        narration=scene.narration,
                        scene_id=scene.scene_id,
                        scene_duration=scene_duration,
                        start_offset=current_offset,
                        emotion_tag=getattr(scene, 'emotion_tag', 'warm')
                    )
                    all_subtitles.extend(scene_subs)
                    current_offset += scene_duration

                if all_subtitles:
                    subtitle_path = os.path.join(export_dir, "subtitles.ass")
                    subtitle_engine.save_ass_file(all_subtitles, subtitle_path, width, height)
                    logger.info(f"Generated {len(all_subtitles)} highlight subtitles")

            elif subtitle_mode == "full":
                # 전체 자막 (나레이션 전문)
                subtitle_path = os.path.join(export_dir, "subtitles.ass")
                subtitle_engine.generate_full_subtitles(
                    script.scenes,
                    audio_files,
                    subtitle_path,
                    width,
                    height
                )
                logger.info("Generated full narration subtitles")

            elif subtitle_mode == "full_highlight":
                # 전체 자막 + 하이라이트 감성 자막 (동시 표시)
                subtitle_path = os.path.join(export_dir, "subtitles.ass")
                subtitle_engine.generate_full_highlight_subtitles(
                    script.scenes,
                    audio_files,
                    subtitle_path,
                    width,
                    height
                )
                logger.info("Generated full + highlight subtitles")
        else:
            logger.info("[8/9] Subtitles disabled")

        # 9) 영상 렌더링
        logger.info("[9/9] Rendering video...")
        video_engine = VideoRenderEngine()

        # ★ 씬별 자막 모드 (싱크 오차 방지) - 모든 자막 모드에 적용
        use_per_scene = subtitle_mode in ["full_highlight", "full", "highlight"]
        if use_per_scene:
            logger.info("[9/9] ★ 씬별 자막 모드 사용 (싱크 정확도 향상)")

        video_path = video_engine.render_video(
            image_paths,
            audio_files,
            script,
            os.path.join(export_dir, "video.mp4"),
            resolution=resolution,
            video_paths=video_paths,
            subtitle_path=subtitle_path if not use_per_scene else None,
            subtitle_engine=subtitle_engine if use_per_scene else None,
            per_scene_subtitle=use_per_scene,
            subtitle_mode=subtitle_mode
        )

    # 메타데이터 저장
    meta = {
        "keyword": keyword,
        "duration_minutes": duration_minutes,
        "title": title_block.final_title,
        "thumbnail_text": title_block.thumbnail_text,
        "category": profile.category,
        "template_id": profile.template_id,
        "subtitle_mode": subtitle_mode,
        "parallax_enabled": parallax_enabled,
        "parallax_scenes": list(parallax_clips.keys()),
        "topic_score": {
            "search_volume": title_block.topic_score.search_volume_score,
            "competition": title_block.topic_score.competition_score,
            "senior_fit": title_block.topic_score.senior_fit_score,
            "final": title_block.topic_score.final_score,
        },
        "scenes": [
            {
                "scene_id": s.scene_id,
                "title": s.title,
                "duration_sec": s.duration_sec,
                "use_video": getattr(s, 'use_video', False),
                "broll_query": getattr(s, 'broll_query', ''),
                "has_parallax": idx in parallax_clips
            }
            for idx, s in enumerate(script.scenes)
        ],
        "broll_count": broll_count,
        "created_at": timestamp
    }

    meta_path = os.path.join(export_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ★ YouTube 설명란 자동 생성
    logger.info("[9/9] Generating YouTube metadata...")
    youtube_engine = YouTubeMetadataEngine(category=profile.category)
    youtube_metadata = youtube_engine.generate_metadata(
        video_title=title_block.final_title,
        story_title=title_block.main_keyword,
        synopsis="",  # 필요시 스크립트에서 추출
        keywords=title_block.sub_keywords,
        thumbnail_path=thumbnail_path,
        video_path=video_path
    )

    # YouTube 설명란 텍스트 파일 저장 (복사용)
    description_path = os.path.join(export_dir, "youtube_description.txt")
    youtube_engine.save_description_file(youtube_metadata["description"], description_path)

    # meta.json에 YouTube 메타데이터 추가
    meta["youtube"] = youtube_metadata
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ★ 디버그: 파이프라인 요약 로그
    print("\n" + "=" * 60)
    print("★ 파이프라인 검수 요약")
    print("=" * 60)

    # 이미지 실패 요약
    image_errors = [log for log in image_event_logs if "error" in log]
    if image_errors:
        print(f"⚠️ 이미지 생성 실패: {len(image_errors)}개")
        for log in image_errors:
            print(f"   - Scene {log['scene_idx']} ({log['scene_id']})")
    else:
        print(f"✅ 이미지: {len(script.scenes)}개 모두 성공")

    # TTS 성공 (실패 시 이 지점까지 도달하지 않음)
    print(f"✅ TTS: {len(audio_files)}개 모두 성공")

    # 오디오 총 길이
    total_audio = sum(af.get("duration", 0) for af in audio_files)
    print(f"✅ 총 오디오 길이: {total_audio:.1f}초 ({total_audio/60:.1f}분)")

    # 자막 생성 여부
    subtitles_path = os.path.join(export_dir, "subtitles.ass")
    if os.path.exists(subtitles_path):
        print(f"✅ 자막 파일 생성됨")
    else:
        print(f"⚠️ 자막 파일 없음")

    print("=" * 60 + "\n")

    logger.info(f"Pipeline completed! Output: {export_dir}")

    return {
        "title_block": title_block,
        "profile": profile,
        "script": script,
        "export_dir": export_dir,
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "meta_path": meta_path,
        "youtube_description_path": description_path,  # YouTube 설명란 파일
        "event_logs": image_event_logs,  # 이벤트 로그 추가
        "parallax_scenes": list(parallax_clips.keys())  # Parallax 적용 장면 인덱스
    }


if __name__ == "__main__":
    # 테스트 실행
    result = run_pipeline("고혈압 관리", duration_minutes=15)

    print("\n" + "=" * 60)
    print("=== RESULT ===")
    print("=" * 60)
    print(f"Title: {result['title_block'].final_title}")
    print(f"Category: {result['profile'].category}")
    print(f"Template: {result['profile'].template_id}")
    print(f"Duration: {result['profile'].duration_sec}s")
    print(f"\nScenes ({len(result['script'].scenes)}):")
    for s in result['script'].scenes:
        print(f"  - {s.scene_id}: {s.duration_sec}s")
    print(f"\nExport directory: {result['export_dir']}")
