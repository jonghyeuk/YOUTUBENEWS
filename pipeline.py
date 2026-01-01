"""
메인 파이프라인 - 인기 영상 기반 콘텐츠 생성
개별 이미지 생성 방식 (fal.ai/DALL-E/Imagen)
"""
import os
import json
from datetime import datetime
from typing import Optional, Callable, List
from dataclasses import asdict

from models.types import Project, Script, Scene, AudioSegment
from engines import (
    ScriptEngine,
    TTSEngine,
    ImageEngine,
    SubtitleEngine,
    VideoEngine,
    TrendEngine,
    TranscriptEngine,
)
from config import DURATION_SPECS


class Pipeline:
    """인기 영상 분석 기반 콘텐츠 생성 파이프라인"""

    def __init__(self, project_dir: str = "projects"):
        self.project_dir = project_dir
        self.script_engine = ScriptEngine()
        self.subtitle_engine = SubtitleEngine()
        self.video_engine = VideoEngine()
        self.trend_engine = TrendEngine()
        self.transcript_engine = TranscriptEngine()

        # 이미지 엔진 (기본: fal.ai)
        self.image_engine: Optional[ImageEngine] = None

        # 현재 프로젝트
        self.project: Optional[Project] = None

        # 진행 콜백 (UI 업데이트용)
        self.on_progress: Optional[Callable] = None

    def create_project(self, topic: str, duration_min: int) -> Project:
        """새 프로젝트 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 폴더명에 사용할 수 없는 문자 제거
        safe_topic = topic[:20]
        # 줄바꿈, 탭 제거
        safe_topic = safe_topic.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # Windows 금지 문자 제거
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            safe_topic = safe_topic.replace(char, "")
        # 공백을 언더스코어로
        safe_topic = safe_topic.replace(" ", "_")
        # 연속 언더스코어 정리
        while "__" in safe_topic:
            safe_topic = safe_topic.replace("__", "_")
        safe_topic = safe_topic.strip("_")

        project_id = f"{safe_topic}_{timestamp}"

        project_path = os.path.join(self.project_dir, project_id)
        os.makedirs(project_path, exist_ok=True)

        self.project = Project(
            project_id=project_id,
            title=topic,
            duration_min=duration_min,
            topic=topic
        )

        self._log(f"프로젝트 생성: {project_id}")
        return self.project

    # ─────────────────────────────────────────────
    # Step 1: 트렌드 분석 & 스크립트 추출
    # ─────────────────────────────────────────────

    def step1_analyze_trend(self, keyword: str, max_results: int = 10) -> list:
        """1단계: 트렌드 분석 - 인기 영상 찾기"""
        self._log(f"1단계: '{keyword}' 트렌드 분석 중...")

        videos = self.trend_engine.search_trending(
            keyword=keyword,
            max_results=max_results
        )

        self._log(f"인기 영상 {len(videos)}개 발견")
        return videos

    def step1b_extract_transcript(self, video_id: str) -> dict:
        """1-B단계: 영상 자막 추출 및 분석"""
        self._log(f"자막 추출 중: {video_id}")

        extracted = self.transcript_engine.extract_transcript(video_id)
        structure = self.transcript_engine.analyze_structure(extracted.text)

        self._log(f"자막 추출 완료: {len(extracted.text)}자")
        return {
            "transcript": extracted,
            "structure": structure
        }

    # ─────────────────────────────────────────────
    # Step 2: 스크립트 생성 (직접 or 리라이트)
    # ─────────────────────────────────────────────

    def step2_generate_script(self, source_text: str = None) -> Script:
        """2단계: 스크립트 생성"""
        self._log("2단계: 스크립트 생성 중...")

        if source_text:
            # 원본 텍스트 리라이트
            script = self.script_engine.rewrite_from_source(
                source_text=source_text,
                duration_min=self.project.duration_min
            )
        else:
            # 주제로 새 스크립트 생성
            script = self.script_engine.generate(
                topic=self.project.topic,
                duration_min=self.project.duration_min
            )

        self.project.script = script
        self.project.current_step = 2

        # 스크립트 파일 저장
        script_path = self._get_path("script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"제목: {script.title}\n\n")
            for scene in script.scenes:
                f.write(f"[씬 {scene.scene_id}: {scene.title}]\n")
                f.write(f"{scene.text}\n\n")

        self._log(f"스크립트 생성 완료: {len(script.scenes)}개 씬")
        return script

    def generate_youtube_metadata(self) -> dict:
        """AI 기반 유튜브 제목/썸네일 문구 생성"""
        if not self.project or not self.project.script:
            raise ValueError("스크립트가 없습니다")

        self._log("유튜브 제목/썸네일 생성 중... (AI)")

        style = getattr(self.project, 'style', '정보')
        duration = self.project.duration_min

        metadata = self.script_engine.generate_youtube_metadata(
            script=self.project.script,
            style=style,
            duration_min=duration
        )

        # 프로젝트에 저장
        self.project.youtube_metadata = metadata

        self._log(f"유튜브 메타데이터 생성 완료")
        return metadata

    # ─────────────────────────────────────────────
    # Step 3: TTS 생성
    # ─────────────────────────────────────────────

    def step3_generate_tts(self, engine: str = "wavenet", style: str = None, speed: float = None) -> str:
        """3단계: TTS 음성 생성 (언어별 + 스타일별 음성/감정 지원)"""
        # 프로젝트에 저장된 언어 가져오기
        language = getattr(self.project, 'language', 'ko')
        speed_info = f", 속도: {speed}" if speed else ""
        self._log(f"3단계: TTS 생성 중... (엔진: {engine}, 언어: {language}, 스타일: {style}{speed_info})")

        tts_engine = TTSEngine(engine=engine, style=style, speed=speed, language=language)
        audio_path = self._get_path("audio_full.mp3")

        audio_path, segments, subtitle_segments = tts_engine.generate_full_audio(
            script=self.project.script,
            output_path=audio_path
        )

        self.project.audio_path = audio_path
        self.project.audio_segments = segments
        self.project.subtitle_segments = subtitle_segments  # 자막 싱크용
        self.project.current_step = 3

        total_duration = sum(s.duration for s in segments)
        self._log(f"TTS 생성 완료: {total_duration:.1f}초, 자막 세그먼트: {len(subtitle_segments)}개")
        return audio_path

    # ─────────────────────────────────────────────
    # Step 4: 이미지 생성 (개별)
    # ─────────────────────────────────────────────

    def step4_generate_images(
        self,
        engine: str = "fal",
        style_prefix: str = ""
    ) -> List[str]:
        """4단계: 씬별 이미지 생성"""
        self._log(f"4단계: 이미지 생성 중... (엔진: {engine})")

        # 이미지 엔진 초기화
        self.image_engine = ImageEngine(engine=engine)
        images_dir = self._get_path("images")

        # 씬별 이미지 생성
        image_paths = self.image_engine.generate_scene_images(
            script=self.project.script,
            output_dir=images_dir,
            style_prefix=style_prefix
        )

        # 씬에 이미지 경로 할당
        for i, scene in enumerate(self.project.script.scenes):
            if i < len(image_paths):
                scene.image_paths = [image_paths[i]]

        self.project.cut_paths = image_paths
        self.project.current_step = 4

        self._log(f"이미지 생성 완료: {len(image_paths)}장")
        return image_paths

    def step4_generate_images_from_prompts(
        self,
        prompts: List[str],
        engine: str = "fal",
        model: str = None,
        storymaker_config: dict = None
    ) -> List[str]:
        """4단계 (대안): 프롬프트 리스트로 이미지 생성

        Args:
            prompts: 이미지 프롬프트 리스트
            engine: 이미지 엔진 (fal, dalle, imagen, storymaker)
            model: 모델명
            storymaker_config: StoryMaker 설정 (region, world_style, character_type)
        """
        # 모델별 가격 정보
        MODEL_PRICES = {
            "flux-schnell": "$0.003",
            "flux-dev": "$0.025",
            "flux-pro": "$0.05",
            "flux-pro-v1.1": "$0.05",
            "flux-ultra": "$0.06",
            "imagen-3-fast": "저렴",
            "imagen-3": "고품질",
            "dall-e-3": "$0.04~0.12",
        }

        price = MODEL_PRICES.get(model, "") if model else ""
        model_info = f", 모델: {model} ({price})" if model else ""
        total_cost = f" ≈ ${len(prompts) * 0.003:.2f}" if model == "flux-schnell" else ""

        # StoryMaker 설정 로그
        style_info = ""
        if storymaker_config:
            style_info = f", 스타일: {storymaker_config.get('region', 'korea')}"

        self._log(f"4단계: 이미지 생성 중... ({len(prompts)}장, 엔진: {engine}{model_info}{total_cost}{style_info})")

        self.image_engine = ImageEngine(engine=engine, model=model)
        images_dir = self._get_path("images")

        image_paths = self.image_engine.generate_images_from_prompts(
            prompts=prompts,
            output_dir=images_dir,
            storymaker_config=storymaker_config
        )

        # 씬에 이미지 경로 할당 (씬별 image_count에 맞게 분배)
        image_idx = 0
        for scene in self.project.script.scenes:
            count = getattr(scene, 'image_count', 1)
            scene.image_paths = []
            for _ in range(count):
                if image_idx < len(image_paths):
                    scene.image_paths.append(image_paths[image_idx])
                    image_idx += 1

        self.project.cut_paths = image_paths
        self.project.current_step = 4

        self._log(f"이미지 생성 완료: {len(image_paths)}장")
        return image_paths

    # ─────────────────────────────────────────────
    # Step 5: 자막 생성
    # ─────────────────────────────────────────────

    def step5_generate_subtitles(self, use_whisper: bool = False) -> str:
        """5단계: 자막 생성"""
        # 자막 세그먼트가 있으면 실제 오디오 길이 기반 (권장)
        has_subtitle_segments = hasattr(self.project, 'subtitle_segments') and self.project.subtitle_segments
        if has_subtitle_segments:
            method = "실제 오디오 길이 기반"
        elif use_whisper:
            method = "Whisper"
        else:
            method = "대본 기반 (추정)"
        self._log(f"5단계: 자막 생성 중... ({method})")

        subtitle_engine = SubtitleEngine(use_whisper=use_whisper)
        subtitle_path = self._get_path("subtitles.ass")

        # generate_srt returns the actual path (.ass format)
        actual_path = subtitle_engine.generate_srt(
            script=self.project.script,
            audio_segments=self.project.audio_segments,
            output_path=subtitle_path,
            audio_path=self.project.audio_path if use_whisper else None,
            subtitle_segments=self.project.subtitle_segments if has_subtitle_segments else None
        )

        self.project.subtitle_path = actual_path
        self.project.current_step = 5

        self._log(f"자막 생성 완료 ({method})")
        return actual_path

    # ─────────────────────────────────────────────
    # Step 6: 영상 렌더링
    # ─────────────────────────────────────────────

    def step6_render_video(
        self,
        use_ken_burns: bool = True,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.15
    ) -> str:
        """6단계: 영상 렌더링"""
        effects = []
        if use_ken_burns:
            effects.append("줌 효과")
        if bgm_path:
            effects.append(f"BGM({int(bgm_volume*100)}%)")
        effect_str = " + ".join(effects) if effects else "기본"
        self._log(f"6단계: 영상 렌더링 중... ({effect_str})")

        clips_dir = self._get_path("clips")

        # 씬 이미지 매핑 (각 씬당 1개 이미지)
        scene_images = {}
        for scene in self.project.script.scenes:
            scene_images[scene.scene_id] = scene.image_paths

        # 씬별 클립 생성 (줌 효과 옵션)
        clip_paths = self.video_engine.render_scene_clips(
            scene_images=scene_images,
            audio_segments=self.project.audio_segments,
            output_dir=clips_dir,
            use_ken_burns=use_ken_burns
        )

        # BGM 경로 로깅
        if bgm_path and os.path.exists(bgm_path):
            self._log(f"BGM 적용: {os.path.basename(bgm_path)}")
        else:
            bgm_path = None  # 경로가 없으면 None으로 처리

        # 클립 합치기 + 오디오 (+ BGM)
        video_path = self._get_path("video_no_sub.mp4")
        self.video_engine.concat_clips(
            clip_paths=clip_paths,
            audio_path=self.project.audio_path,
            output_path=video_path,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume
        )

        self.project.video_path = video_path
        self.project.current_step = 6

        self._log("영상 렌더링 완료")
        return video_path

    # ─────────────────────────────────────────────
    # Step 7: 자막 번인
    # ─────────────────────────────────────────────

    def step7_burn_subtitles(self) -> str:
        """7단계: 자막 번인 → 최종 영상"""
        self._log("7단계: 자막 번인 중...")

        final_path = self._get_path("final_with_sub.mp4")

        self.video_engine.burn_subtitles(
            video_path=self.project.video_path,
            subtitle_path=self.project.subtitle_path,
            output_path=final_path
        )

        self.project.final_video_path = final_path
        self.project.status = "completed"
        self.project.current_step = 7

        self._log("최종 영상 생성 완료!")
        return final_path

    # ─────────────────────────────────────────────
    # 전체 실행
    # ─────────────────────────────────────────────

    def run_all(
        self,
        topic: str,
        duration_min: int,
        tts_engine: str = "wavenet",
        image_engine: str = "fal",
        style_prefix: str = "",
        use_ken_burns: bool = True,
        bgm_path: Optional[str] = None
    ) -> str:
        """
        전체 파이프라인 실행

        Args:
            topic: 영상 주제
            duration_min: 영상 길이 (분)
            tts_engine: TTS 엔진 (wavenet, elevenlabs, openai)
            image_engine: 이미지 엔진 (fal, dalle, imagen)
            style_prefix: 이미지 스타일 접두사
            use_ken_burns: 이미지 줌 효과 사용 여부
            bgm_path: 배경음악 파일 경로

        Returns:
            최종 영상 경로
        """
        self.create_project(topic, duration_min)
        self.step2_generate_script()
        self.step3_generate_tts(tts_engine)
        self.step4_generate_images(engine=image_engine, style_prefix=style_prefix)
        self.step5_generate_subtitles()
        self.step6_render_video(use_ken_burns=use_ken_burns, bgm_path=bgm_path)
        return self.step7_burn_subtitles()

    def run_from_trend(
        self,
        keyword: str,
        video_id: str,
        duration_min: int,
        tts_engine: str = "wavenet",
        image_engine: str = "fal",
        style_prefix: str = "",
        use_ken_burns: bool = True,
        bgm_path: Optional[str] = None
    ) -> str:
        """
        인기 영상 분석 기반 파이프라인 실행

        Args:
            keyword: 검색 키워드
            video_id: 참조할 YouTube 영상 ID
            duration_min: 영상 길이 (분)
            bgm_path: 배경음악 파일 경로

        Returns:
            최종 영상 경로
        """
        self.create_project(keyword, duration_min)

        # 원본 영상 자막 추출
        data = self.step1b_extract_transcript(video_id)
        source_text = data["transcript"].text

        # 리라이트
        self.step2_generate_script(source_text=source_text)
        self.step3_generate_tts(tts_engine)
        self.step4_generate_images(engine=image_engine, style_prefix=style_prefix)
        self.step5_generate_subtitles()
        self.step6_render_video(use_ken_burns=use_ken_burns, bgm_path=bgm_path)
        return self.step7_burn_subtitles()

    # ─────────────────────────────────────────────
    # 유틸리티
    # ─────────────────────────────────────────────

    def _get_path(self, filename: str) -> str:
        """프로젝트 내 파일 경로 생성"""
        project_path = os.path.join(self.project_dir, self.project.project_id)
        os.makedirs(project_path, exist_ok=True)
        return os.path.join(project_path, filename)

    def _log(self, message: str):
        """로그 출력 및 콜백 호출"""
        print(f"[Pipeline] {message}")
        if self.on_progress:
            self.on_progress(message)

    # ─────────────────────────────────────────────
    # 프로젝트 저장/불러오기
    # ─────────────────────────────────────────────

    def save_project(self) -> str:
        """프로젝트 상태를 JSON으로 저장"""
        if not self.project:
            raise ValueError("저장할 프로젝트가 없습니다")

        project_path = os.path.join(self.project_dir, self.project.project_id)
        save_path = os.path.join(project_path, "project.json")

        # Project를 dict로 변환
        data = {
            "project_id": self.project.project_id,
            "title": self.project.title,
            "duration_min": self.project.duration_min,
            "topic": self.project.topic,
            "audio_path": self.project.audio_path,
            "sheet_image_path": self.project.sheet_image_path,
            "cut_paths": self.project.cut_paths,
            "subtitle_path": self.project.subtitle_path,
            "video_path": self.project.video_path,
            "final_video_path": self.project.final_video_path,
            "current_step": self.project.current_step,
            "status": self.project.status,
        }

        # Script 저장
        if self.project.script:
            data["script"] = {
                "title": self.project.script.title,
                "duration_min": self.project.script.duration_min,
                "total_panels": self.project.script.total_panels,
                "scenes": [asdict(s) for s in self.project.script.scenes]
            }

        # AudioSegments 저장
        if self.project.audio_segments:
            data["audio_segments"] = [asdict(seg) for seg in self.project.audio_segments]

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._log(f"프로젝트 저장 완료: {save_path}")
        return save_path

    def load_project(self, project_id: str) -> Project:
        """저장된 프로젝트 불러오기"""
        project_path = os.path.join(self.project_dir, project_id)
        load_path = os.path.join(project_path, "project.json")

        if not os.path.exists(load_path):
            raise FileNotFoundError(f"프로젝트를 찾을 수 없습니다: {load_path}")

        with open(load_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Script 복원
        script = None
        if "script" in data and data["script"]:
            scenes = [Scene(**s) for s in data["script"]["scenes"]]
            script = Script(
                title=data["script"]["title"],
                scenes=scenes,
                duration_min=data["script"]["duration_min"],
                total_panels=data["script"]["total_panels"]
            )

        # AudioSegments 복원
        audio_segments = []
        if "audio_segments" in data and data["audio_segments"]:
            audio_segments = [AudioSegment(**seg) for seg in data["audio_segments"]]

        # Project 복원
        self.project = Project(
            project_id=data["project_id"],
            title=data["title"],
            duration_min=data["duration_min"],
            topic=data["topic"],
            script=script,
            audio_path=data.get("audio_path"),
            audio_segments=audio_segments,
            sheet_image_path=data.get("sheet_image_path"),
            cut_paths=data.get("cut_paths", []),
            subtitle_path=data.get("subtitle_path"),
            video_path=data.get("video_path"),
            final_video_path=data.get("final_video_path"),
            current_step=data.get("current_step", 0),
            status=data.get("status", "loaded")
        )

        self._log(f"프로젝트 불러오기 완료: {project_id}")
        return self.project

    def list_projects(self) -> List[dict]:
        """저장된 프로젝트 목록 조회"""
        projects = []

        if not os.path.exists(self.project_dir):
            return projects

        for folder in os.listdir(self.project_dir):
            project_path = os.path.join(self.project_dir, folder)
            json_path = os.path.join(project_path, "project.json")

            if os.path.isdir(project_path) and os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    projects.append({
                        "project_id": folder,
                        "title": data.get("title", folder),
                        "duration_min": data.get("duration_min", 0),
                        "status": data.get("status", "unknown"),
                        "has_images": len(data.get("cut_paths", [])) > 0,
                        "has_audio": data.get("audio_path") is not None,
                        "has_video": data.get("final_video_path") is not None,
                    })
                except Exception as e:
                    print(f"[Pipeline] 프로젝트 로드 실패: {folder} - {e}")

        # 최신순 정렬
        projects.sort(key=lambda x: x["project_id"], reverse=True)
        return projects

    def regenerate_tts(
        self,
        engine: str = "elevenlabs",
        voice_id: str = None,
        speed: float = 0.9,
        style: str = "정보"
    ) -> str:
        """
        기존 스크립트로 TTS만 재생성 (다른 채널용)

        Args:
            engine: TTS 엔진 (elevenlabs, wavenet, openai)
            voice_id: 음성 ID (엔진별)
            speed: 음성 속도
            style: 스타일 (elevenlabs 설정 적용)

        Returns:
            새 오디오 파일 경로
        """
        if not self.project or not self.project.script:
            raise ValueError("스크립트가 있는 프로젝트를 먼저 불러오세요")

        self._log(f"TTS 재생성 시작: engine={engine}, style={style}")

        # 새 오디오 파일명 (타임스탬프로 구분)
        timestamp = datetime.now().strftime("%H%M%S")
        audio_filename = f"tts_{timestamp}.mp3"

        # 기존 step3 호출
        audio_path = self.step3_generate_tts(
            engine=engine,
            style=style
        )

        self._log(f"TTS 재생성 완료: {audio_path}")
        return audio_path

    def regenerate_subtitles(self, use_whisper: bool = False) -> str:
        """자막만 재생성"""
        if not self.project or not self.project.audio_path:
            raise ValueError("오디오가 있는 프로젝트를 먼저 불러오세요")

        return self.step5_generate_subtitles(use_whisper=use_whisper)

    def rerender_video(
        self,
        use_ken_burns: bool = True,
        bgm_path: str = None,
        bgm_volume: float = 0.15
    ) -> str:
        """기존 이미지 + 새 TTS로 영상 재렌더링"""
        if not self.project:
            raise ValueError("프로젝트를 먼저 불러오세요")

        # 씬-이미지 매핑 재구성
        scene_images = {}
        if self.project.script and self.project.cut_paths:
            img_idx = 0
            for scene in self.project.script.scenes:
                count = scene.image_count or 1
                scene_images[scene.scene_id] = []
                for _ in range(count):
                    if img_idx < len(self.project.cut_paths):
                        scene_images[scene.scene_id].append(self.project.cut_paths[img_idx])
                        img_idx += 1

        # 렌더링
        self.step6_render_video(use_ken_burns=use_ken_burns, bgm_path=bgm_path)
        return self.step7_burn_subtitles()
