"""
메인 파이프라인 - 전체 영상 생성 프로세스 제어
정서 단락 전환점 기반 이미지 배치 워크플로우
"""
import os
from datetime import datetime
from typing import Optional, Callable

from models.types import Project, Script
from engines import (
    ScriptEngine,
    TTSEngine,
    ImageEngine,
    ImageSplitter,
    SubtitleEngine,
    VideoEngine,
    EmotionalTransitionEngine,
    ImagePlacementPlan
)
from config import DURATION_SPECS


class Pipeline:
    """자동 스토리 영상 생성 파이프라인"""

    def __init__(self, project_dir: str = "projects"):
        self.project_dir = project_dir
        self.script_engine = ScriptEngine()
        self.image_engine = ImageEngine()
        self.image_splitter = ImageSplitter()
        self.subtitle_engine = SubtitleEngine()
        self.video_engine = VideoEngine()
        self.emotional_engine = EmotionalTransitionEngine()

        # 현재 프로젝트
        self.project: Optional[Project] = None

        # 이미지 배치 계획 (정서 전환점 기반)
        self.placement_plan: Optional[ImagePlacementPlan] = None

        # 진행 콜백 (UI 업데이트용)
        self.on_progress: Optional[Callable] = None

    def create_project(self, topic: str, duration_min: int) -> Project:
        """새 프로젝트 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_id = f"{topic[:20]}_{timestamp}".replace(" ", "_")

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

    def step1_generate_script(self) -> Script:
        """1단계: 대본 생성"""
        self._log("1단계: 대본 생성 중...")

        script = self.script_engine.generate(
            topic=self.project.topic,
            duration_min=self.project.duration_min
        )

        self.project.script = script
        self.project.current_step = 1

        # 대본 파일 저장
        script_path = self._get_path("script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"제목: {script.title}\n\n")
            for scene in script.scenes:
                f.write(f"[씬 {scene.scene_id}: {scene.title}]\n")
                f.write(f"{scene.text}\n\n")

        self._log(f"대본 생성 완료: {len(script.scenes)}개 씬")
        return script

    def step2_generate_tts(self, engine: str = "wavenet") -> str:
        """2단계: TTS 음성 생성"""
        self._log(f"2단계: TTS 생성 중... (엔진: {engine})")

        tts_engine = TTSEngine(engine=engine)
        audio_path = self._get_path("audio_full.mp3")

        audio_path, segments = tts_engine.generate_full_audio(
            script=self.project.script,
            output_path=audio_path
        )

        self.project.audio_path = audio_path
        self.project.audio_segments = segments
        self.project.current_step = 2

        total_duration = sum(s.duration for s in segments)
        self._log(f"TTS 생성 완료: {total_duration:.1f}초")
        return audio_path

    def step2b_analyze_transitions(self) -> ImagePlacementPlan:
        """2-B단계: 정서 단락 전환점 분석"""
        self._log("2-B단계: 정서 전환점 분석 중...")

        plan = self.emotional_engine.analyze_transitions(
            script=self.project.script,
            audio_segments=self.project.audio_segments,
            duration_min=self.project.duration_min
        )

        self.placement_plan = plan

        # 분석 결과 저장
        plan_path = self._get_path("transition_plan.json")
        import json
        with open(plan_path, "w", encoding="utf-8") as f:
            plan_data = {
                "total_panels": plan.total_panels,
                "duration_seconds": plan.duration_seconds,
                "transitions": [
                    {
                        "panel_id": t.panel_id,
                        "time_start": t.time_start,
                        "time_end": t.time_end,
                        "type": t.transition_type,
                        "description_ko": t.description_ko,
                        "description_en": t.description_en,
                        "scene_id": t.scene_id
                    }
                    for t in plan.transitions
                ]
            }
            json.dump(plan_data, f, ensure_ascii=False, indent=2)

        self._log(f"정서 전환점 분석 완료: {len(plan.transitions)}개 전환점")
        return plan

    def step3_generate_images(self, style: str = "cinematic") -> str:
        """3단계: 합본 이미지 생성 (정서 전환점 기반)"""
        self._log("3단계: 스토리보드 이미지 생성 중...")

        sheet_path = self._get_path("sheet.png")

        # 정서 전환점 분석이 있으면 해당 설명 사용
        if self.placement_plan and self.placement_plan.transitions:
            transition_descriptions = [
                t.description_en for t in self.placement_plan.transitions
            ]
            self._log(f"정서 전환점 기반 {len(transition_descriptions)}개 패널 프롬프트 사용")

            self.image_engine.generate_sheet_with_transitions(
                script=self.project.script,
                output_path=sheet_path,
                transition_descriptions=transition_descriptions,
                style=style
            )
        else:
            # 폴백: 대본 기반 자동 생성
            self._log("대본 기반 자동 비트 생성")
            self.image_engine.generate_sheet(
                script=self.project.script,
                output_path=sheet_path,
                style=style
            )

        self.project.sheet_image_path = sheet_path
        self.project.current_step = 3

        self._log("스토리보드 이미지 생성 완료")
        return sheet_path

    def step4_split_images(self) -> list:
        """4단계: 이미지 분할"""
        self._log("4단계: 이미지 분할 중...")

        cuts_dir = self._get_path("cuts")

        cut_paths = self.image_splitter.split(
            sheet_path=self.project.sheet_image_path,
            output_dir=cuts_dir,
            duration_min=self.project.duration_min
        )

        self.project.cut_paths = cut_paths
        self.project.current_step = 4

        self._log(f"이미지 분할 완료: {len(cut_paths)}개 컷")
        return cut_paths

    def step5_assign_scenes(self) -> dict:
        """5단계: 씬별 이미지 배분 (정서 전환점 기반)"""
        self._log("5단계: 씬별 이미지 배분 중...")

        scenes_dir = self._get_path("scenes")

        # 정서 전환점 계획이 있으면 그것 사용
        if self.placement_plan and self.placement_plan.transitions:
            scene_panels = self.emotional_engine.assign_panels_to_scenes(
                plan=self.placement_plan,
                script=self.project.script
            )

            # 패널 ID를 실제 이미지 경로로 변환
            scene_images = {}
            for scene_id, panel_ids in scene_panels.items():
                scene_images[scene_id] = [
                    self.project.cut_paths[pid - 1]
                    for pid in panel_ids
                    if pid <= len(self.project.cut_paths)
                ]

            self._log("정서 전환점 기반 배분 완료")
        else:
            # 폴백: 기존 균등 배분 방식
            scene_images = self.image_splitter.assign_to_scenes(
                cut_paths=self.project.cut_paths,
                scenes_dir=scenes_dir,
                duration_min=self.project.duration_min
            )
            self._log("균등 배분 방식 사용")

        # 씬에 이미지 경로 할당
        for scene in self.project.script.scenes:
            scene.image_paths = scene_images.get(scene.scene_id, [])

        self.project.current_step = 5

        self._log("씬별 이미지 배분 완료")
        return scene_images

    def step6_generate_subtitles(self, use_whisper: bool = False) -> str:
        """6단계: 자막 생성"""
        method = "Whisper" if use_whisper else "대본 기반"
        self._log(f"6단계: 자막 생성 중... ({method})")

        # Whisper 사용 시 새 SubtitleEngine 생성
        subtitle_engine = SubtitleEngine(use_whisper=use_whisper)
        subtitle_path = self._get_path("subtitles.srt")

        subtitle_engine.generate_srt(
            script=self.project.script,
            audio_segments=self.project.audio_segments,
            output_path=subtitle_path,
            audio_path=self.project.audio_path if use_whisper else None
        )

        self.project.subtitle_path = subtitle_path
        self.project.current_step = 6

        self._log("자막 생성 완료")
        return subtitle_path

    def step7_render_video(self, use_ken_burns: bool = True, use_bgm: bool = False) -> str:
        """7단계: 영상 렌더링"""
        effects = []
        if use_ken_burns:
            effects.append("Ken Burns")
        if use_bgm:
            effects.append("BGM")
        effect_str = " + ".join(effects) if effects else "기본"
        self._log(f"7단계: 영상 렌더링 중... ({effect_str})")

        clips_dir = self._get_path("clips")

        # 씬 이미지 매핑
        scene_images = {}
        for scene in self.project.script.scenes:
            scene_images[scene.scene_id] = scene.image_paths

        # 씬별 클립 생성 (Ken Burns 옵션)
        clip_paths = self.video_engine.render_scene_clips(
            scene_images=scene_images,
            audio_segments=self.project.audio_segments,
            output_dir=clips_dir,
            use_ken_burns=use_ken_burns
        )

        # BGM 경로 (사용 시)
        bgm_path = None
        if use_bgm:
            bgm_path = self.video_engine.get_random_bgm()
            if bgm_path:
                self._log(f"BGM 선택: {os.path.basename(bgm_path)}")

        # 클립 합치기 + 오디오 (+ BGM)
        video_path = self._get_path("video_no_sub.mp4")
        self.video_engine.concat_clips(
            clip_paths=clip_paths,
            audio_path=self.project.audio_path,
            output_path=video_path,
            bgm_path=bgm_path
        )

        self.project.video_path = video_path
        self.project.current_step = 7

        self._log("영상 렌더링 완료")
        return video_path

    def step8_burn_subtitles(self) -> str:
        """8단계: 자막 번인 → 최종 영상"""
        self._log("8단계: 자막 번인 중...")

        final_path = self._get_path("final_with_sub.mp4")

        self.video_engine.burn_subtitles(
            video_path=self.project.video_path,
            subtitle_path=self.project.subtitle_path,
            output_path=final_path
        )

        self.project.final_video_path = final_path
        self.project.status = "completed"
        self.project.current_step = 8

        self._log("최종 영상 생성 완료!")
        return final_path

    def run_all(
        self,
        topic: str,
        duration_min: int,
        tts_engine: str = "wavenet",
        style: str = "cinematic",
        use_emotional_analysis: bool = True,
        use_ken_burns: bool = True,
        use_bgm: bool = False
    ) -> str:
        """
        전체 파이프라인 실행

        Args:
            topic: 영상 주제
            duration_min: 영상 길이 (5, 10, 15, 20, 30, 40)
            tts_engine: TTS 엔진 (wavenet, elevenlabs, openai)
            style: 이미지 스타일 (cinematic, oil_painting, watercolor, anime, webtoon, realistic)
            use_emotional_analysis: 정서 전환점 분석 사용 여부
            use_ken_burns: Ken Burns 효과 사용 여부
            use_bgm: 배경음악 사용 여부

        Returns:
            최종 영상 경로
        """
        self.create_project(topic, duration_min)
        self.step1_generate_script()
        self.step2_generate_tts(tts_engine)

        # 정서 전환점 분석 (선택적)
        if use_emotional_analysis:
            self.step2b_analyze_transitions()

        self.step3_generate_images(style)
        self.step4_split_images()
        self.step5_assign_scenes()
        self.step6_generate_subtitles()
        self.step7_render_video(use_ken_burns=use_ken_burns, use_bgm=use_bgm)
        return self.step8_burn_subtitles()

    def _get_path(self, filename: str) -> str:
        """프로젝트 내 파일 경로 생성"""
        project_path = os.path.join(self.project_dir, self.project.project_id)
        return os.path.join(project_path, filename)

    def _log(self, message: str):
        """로그 출력 및 콜백 호출"""
        print(f"[Pipeline] {message}")
        if self.on_progress:
            self.on_progress(message)
