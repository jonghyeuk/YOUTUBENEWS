import os
import json
from datetime import datetime

from engines.profile_engine import ContentProfileEngine
from engines.script_engine import ScriptEngine
from engines.image_engine import ImageEngine
from engines.tts_engine import TTSEngine
from engines.video_engine import VideoRenderEngine
from engines.subtitle_engine import SubtitleEngine
from engines.stt_subtitle_engine import STTSubtitleEngine
from models.types import TitleThumbnailResult, TopicScore
from utils.logger import setup_logger


logger = setup_logger()


def run_news_pipeline(
    news_content: str,
    news_mode: str = "accident_news",
    image_style: str = "realistic",
    duration_minutes: float = 5
):
    """
    뉴스 영상 생성 파이프라인

    Args:
        news_content: 뉴스 내용 (사용자 입력)
        news_mode: 뉴스 모드 (accident_news / rumor_news)
        image_style: 이미지 스타일 (anime / realistic)
        duration_minutes: 영상 길이 (분)

    Returns:
        결과 딕셔너리
    """
    logger.info(f"Starting news pipeline - Mode: {news_mode}, Style: {image_style}, Duration: {duration_minutes}min")

    # 출력 디렉토리 설정
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"news_{news_mode}_{timestamp}"
    export_dir = os.path.join("export", project_name)

    os.makedirs(export_dir, exist_ok=True)
    os.makedirs(os.path.join(export_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(export_dir, "audio"), exist_ok=True)

    # 환경변수 설정
    os.environ["IMAGE_STYLE"] = image_style

    # 1) 프로필 생성
    logger.info("[1/6] Building content profile...")
    profile_engine = ContentProfileEngine()
    profile = profile_engine.build_news_profile(
        news_mode=news_mode,
        duration_minutes=duration_minutes
    )
    logger.info(f"Profile: {profile.template_id}, Duration: {profile.duration_sec}s")

    # 2) 더미 타이틀 블록 (뉴스는 키워드 기반이 아님)
    title_block = TitleThumbnailResult(
        topic_score=TopicScore(0, 0, 0, 0),
        final_title=f"뉴스 영상 - {news_mode}",
        main_keyword="뉴스",
        sub_keywords=[],
        thumbnail_text="뉴스",
        thumbnail_image_prompt="News thumbnail"
    )

    # 3) 스크립트 생성
    logger.info("[2/6] Generating script from news content...")
    script_engine = ScriptEngine()
    script = script_engine.generate_news_script(
        news_content=news_content,
        news_mode=news_mode,
        profile=profile,
        title_block=title_block
    )
    logger.info(f"Script generated: {len(script.scenes)} scenes")

    # 4) 이미지 생성
    logger.info("[3/6] Generating images...")
    image_engine = ImageEngine()
    image_paths, image_event_logs = image_engine.generate_scene_images(
        script.scenes,
        os.path.join(export_dir, "images"),
        category=profile.category,
        profile=profile
    )
    logger.info(f"Images generated: {len(image_paths)}")

    # 5) TTS 음성 생성
    logger.info("[4/6] Generating audio...")
    tts_engine = TTSEngine()

    try:
        audio_files = tts_engine.generate_audio(
            script.scenes,
            profile,
            os.path.join(export_dir, "audio")
        )
        logger.info(f"Audio files: {len(audio_files)}")
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return None

    # 6) 자막 생성 (STT 기반 - 음성에서 타이밍 추출)
    subtitle_mode = os.getenv("SUBTITLE_MODE", "full_highlight")
    subtitle_size = os.getenv("SUBTITLE_SIZE", "medium")
    use_stt_subtitle = os.getenv("USE_STT_SUBTITLE", "true").lower() == "true"
    resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
    width, height = map(int, resolution.split("x"))

    subtitle_path = None
    if subtitle_mode != "none":
        logger.info(f"[5/6] Generating subtitles ({subtitle_mode})...")
        subtitle_path = os.path.join(export_dir, "subtitles.ass")

        if use_stt_subtitle:
            # ★ 새로운 방식: 음성에서 실제 타이밍 추출
            logger.info("Using STT-based subtitle (extracting timing from audio)...")
            stt_engine = STTSubtitleEngine(font_size_preset=subtitle_size)

            stt_engine.generate_subtitles_from_audio(
                audio_files=audio_files,
                output_path=subtitle_path,
                video_width=width,
                video_height=height,
                subtitle_mode=subtitle_mode
            )
        else:
            # 기존 방식: 텍스트 길이로 타이밍 예측 (fallback)
            logger.info("Using prediction-based subtitle (fallback)...")
            subtitle_engine = SubtitleEngine(font_size_preset=subtitle_size)

            if subtitle_mode == "full_highlight":
                subtitle_engine.generate_full_highlight_subtitles(
                    script.scenes, audio_files, subtitle_path, width, height
                )
            elif subtitle_mode == "full":
                subtitle_engine.generate_full_subtitles(
                    script.scenes, audio_files, subtitle_path, width, height
                )
            elif subtitle_mode == "highlight":
                all_subtitles = []
                current_offset = 0.0
                for idx, scene in enumerate(script.scenes):
                    if idx < len(audio_files):
                        scene_duration = audio_files[idx].get("duration", scene.duration_sec)
                    else:
                        scene_duration = scene.duration_sec
                    scene_subs = subtitle_engine.generate_scene_subtitles(
                        narration=scene.narration,
                        scene_id=scene.scene_id,
                        scene_duration=scene_duration,
                        start_offset=current_offset,
                        emotion_tag=getattr(scene, 'emotion_tag', 'neutral')
                    )
                    all_subtitles.extend(scene_subs)
                    current_offset += scene_duration
                if all_subtitles:
                    subtitle_engine.save_ass_file(all_subtitles, subtitle_path, width, height)

        logger.info("Subtitles generated")

    # 7) 영상 렌더링
    logger.info("[6/6] Rendering video...")
    video_engine = VideoRenderEngine()

    video_path = video_engine.render_video(
        image_paths,
        audio_files,
        script,
        os.path.join(export_dir, "video.mp4"),
        resolution=resolution,
        video_paths={},
        subtitle_path=subtitle_path,
        subtitle_engine=None,
        per_scene_subtitle=False,
        subtitle_mode=subtitle_mode
    )

    # 썸네일 생성
    thumbnail_path = os.path.join(export_dir, "thumbnail.png")
    try:
        if script.scenes:
            first_scene = script.scenes[0]
            image_engine.generate_thumbnail(
                prompt=first_scene.image_prompt,
                text="뉴스",
                output_path=thumbnail_path,
                category=profile.category
            )
    except Exception as e:
        logger.warning(f"Thumbnail generation failed: {e}")
        thumbnail_path = None

    # 메타데이터 저장
    meta = {
        "news_mode": news_mode,
        "image_style": image_style,
        "duration_minutes": duration_minutes,
        "scene_count": len(script.scenes),
        "subtitle_mode": subtitle_mode,
        "created_at": timestamp
    }

    meta_path = os.path.join(export_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 결과 요약
    print("\n" + "=" * 60)
    print("★ 뉴스 영상 생성 완료")
    print("=" * 60)
    print(f"✅ 모드: {news_mode}")
    print(f"✅ 이미지 스타일: {image_style}")
    print(f"✅ 씬 개수: {len(script.scenes)}")
    print(f"✅ 출력 디렉토리: {export_dir}")
    print("=" * 60 + "\n")

    logger.info(f"Pipeline completed! Output: {export_dir}")

    return {
        "script": script,
        "profile": profile,
        "export_dir": export_dir,
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "image_paths": image_paths,
        "audio_files": audio_files,
        "meta_path": meta_path,
        "event_logs": image_event_logs
    }


# 기존 호환성을 위한 래퍼
def run_pipeline(keyword: str, duration_minutes: int = 15, mode_id: str = "accident_news"):
    """기존 호환성을 위한 래퍼 함수"""
    return run_news_pipeline(
        news_content=keyword,
        news_mode=mode_id,
        image_style=os.getenv("IMAGE_STYLE", "realistic"),
        duration_minutes=duration_minutes
    )


if __name__ == "__main__":
    # 테스트 실행
    test_news = """
    서울 강남구에서 오늘 오전 교통사고가 발생했습니다.
    경찰에 따르면 승용차와 오토바이가 충돌해 오토바이 운전자가 부상을 입었습니다.
    사고 원인은 현재 조사 중입니다.
    """

    result = run_news_pipeline(
        news_content=test_news,
        news_mode="accident_news",
        image_style="realistic",
        duration_minutes=3
    )

    if result:
        print(f"\nVideo: {result['video_path']}")
        print(f"Export: {result['export_dir']}")
