"""
정서 단락 전환점 분석 엔진
- 장소 변화 (집 → 산길)
- 분위기 변화 (평화 → 긴장)
- 사건 전환 (대화 → 추격)
- 이미지 배치 계획 생성
"""
import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from anthropic import Anthropic

from models.types import Script, AudioSegment
from config import DURATION_SPECS


@dataclass
class TransitionPoint:
    """전환점 정보"""
    time_start: float  # 시작 시간 (초)
    time_end: float    # 종료 시간 (초)
    panel_id: int      # 할당된 이미지 패널 번호
    transition_type: str  # 전환 유형: location, mood, event
    description_ko: str   # 한국어 설명
    description_en: str   # 영어 설명 (DALL-E 프롬프트용)
    scene_id: int = 0     # 해당 씬 ID


@dataclass
class ImagePlacementPlan:
    """이미지 배치 계획"""
    total_panels: int
    duration_seconds: float
    transitions: List[TransitionPoint] = field(default_factory=list)

    def to_beats_list(self) -> str:
        """DALL-E 프롬프트용 비트 리스트 생성"""
        beats = []
        for i, t in enumerate(self.transitions, 1):
            beats.append(f"{i}. {t.description_en}")
        return "\n".join(beats)

    def get_panel_timings(self) -> Dict[int, tuple]:
        """패널별 시간 정보 {panel_id: (start, end)}"""
        timings = {}
        for t in self.transitions:
            timings[t.panel_id] = (t.time_start, t.time_end)
        return timings


class EmotionalTransitionEngine:
    """정서 전환점 분석 및 이미지 배치 계획 생성"""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def analyze_transitions(
        self,
        script: Script,
        audio_segments: List[AudioSegment],
        duration_min: int
    ) -> ImagePlacementPlan:
        """
        대본과 오디오 세그먼트를 분석하여 정서 전환점 추출

        Args:
            script: Script 객체
            audio_segments: TTS 생성된 오디오 세그먼트 리스트
            duration_min: 영상 길이 (분)

        Returns:
            ImagePlacementPlan 객체
        """
        spec = DURATION_SPECS.get(duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {duration_min}분")

        total_panels = spec["panels"]
        total_duration = sum(seg.duration for seg in audio_segments)

        # 씬별 시간 정보 정리
        scene_timings = self._build_scene_timings(script, audio_segments)

        # Claude에게 전환점 분석 요청
        prompt = self._build_analysis_prompt(
            script=script,
            scene_timings=scene_timings,
            total_panels=total_panels,
            total_duration=total_duration
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # JSON 파싱
        transitions_data = self._parse_response(content)

        # TransitionPoint 객체로 변환
        transitions = []
        for i, t_data in enumerate(transitions_data.get("transitions", [])):
            transition = TransitionPoint(
                time_start=t_data.get("time_start", 0),
                time_end=t_data.get("time_end", 0),
                panel_id=i + 1,
                transition_type=t_data.get("type", "event"),
                description_ko=t_data.get("description_ko", ""),
                description_en=t_data.get("description_en", ""),
                scene_id=t_data.get("scene_id", 0)
            )
            transitions.append(transition)

        plan = ImagePlacementPlan(
            total_panels=total_panels,
            duration_seconds=total_duration,
            transitions=transitions
        )

        print(f"[EmotionalEngine] 전환점 분석 완료: {len(transitions)}개 전환점")
        return plan

    def _build_scene_timings(
        self,
        script: Script,
        audio_segments: List[AudioSegment]
    ) -> Dict[int, dict]:
        """씬별 시간 정보 구성"""
        scene_timings = {}

        for scene in script.scenes:
            # 해당 씬의 오디오 세그먼트 찾기
            seg = next(
                (s for s in audio_segments if s.scene_id == scene.scene_id),
                None
            )
            if seg:
                scene_timings[scene.scene_id] = {
                    "title": scene.title,
                    "text": scene.text,
                    "start": seg.start_time,
                    "end": seg.end_time,
                    "duration": seg.duration
                }

        return scene_timings

    def _build_analysis_prompt(
        self,
        script: Script,
        scene_timings: Dict[int, dict],
        total_panels: int,
        total_duration: float
    ) -> str:
        """전환점 분석 프롬프트 구성"""

        # 씬 정보 텍스트
        scene_info = ""
        for scene_id, timing in scene_timings.items():
            scene_info += f"""
씬 {scene_id}: {timing['title']}
- 시간: {timing['start']:.1f}초 ~ {timing['end']:.1f}초 (길이: {timing['duration']:.1f}초)
- 내용: {timing['text'][:200]}...
"""

        return f"""당신은 스토리 영상 제작 전문가입니다.
주어진 대본을 분석하여 정서적 전환점을 찾고, 이미지 배치 계획을 수립해주세요.

## 대본 정보
제목: {script.title}
총 길이: {total_duration:.1f}초
필요한 이미지 패널 수: {total_panels}장

{scene_info}

## 분석 기준

전환점은 다음 3가지 유형으로 구분합니다:
1. **location** (장소 변화): 집 → 산길, 실내 → 실외 등
2. **mood** (분위기 변화): 평화 → 긴장, 슬픔 → 희망 등
3. **event** (사건 전환): 대화 → 추격, 일상 → 사건 발생 등

## 중요 원칙

1. 정확히 {total_panels}개의 전환점을 찾아야 합니다
2. 각 전환점은 겹치지 않는 시간 구간을 가져야 합니다
3. 전환점은 시간순으로 정렬되어야 합니다
4. 감정이 고조되는 장면에는 더 많은 이미지를 배치합니다
5. 각 이미지의 영어 설명은 DALL-E 이미지 생성에 사용됩니다

## 출력 형식

JSON으로 응답해주세요:
```json
{{
  "transitions": [
    {{
      "time_start": 0.0,
      "time_end": 15.5,
      "scene_id": 1,
      "type": "location",
      "description_ko": "평화로운 시골 마을의 아침",
      "description_en": "Peaceful morning in a rural village, warm sunlight through windows"
    }},
    {{
      "time_start": 15.5,
      "time_end": 28.0,
      "scene_id": 1,
      "type": "event",
      "description_ko": "주인공이 문을 열고 나가는 장면",
      "description_en": "Main character opening the door and stepping outside"
    }},
    ...
  ]
}}
```

정확히 {total_panels}개의 전환점을 찾아주세요."""

    def generate_dalle_beats(
        self,
        plan: ImagePlacementPlan,
        style: str = "cinematic"
    ) -> str:
        """
        배치 계획에서 DALL-E 프롬프트용 비트 리스트 생성

        Args:
            plan: ImagePlacementPlan 객체
            style: 이미지 스타일

        Returns:
            DALL-E 비트 리스트 문자열
        """
        from config import IMAGE_STYLE_GUIDES

        style_guide = IMAGE_STYLE_GUIDES.get(style, IMAGE_STYLE_GUIDES["cinematic"])

        beats = []
        for i, t in enumerate(plan.transitions, 1):
            # 영어 설명에 스타일 가이드 포함
            beat_desc = f"{t.description_en}"
            beats.append(f"{i}. {beat_desc}")

        beats_text = "\n".join(beats)

        return f"""Style for all panels: {style_guide}

STORY BEATS (one beat per panel, reading order left-to-right, top-to-bottom):
{beats_text}"""

    def assign_panels_to_scenes(
        self,
        plan: ImagePlacementPlan,
        script: Script
    ) -> Dict[int, List[int]]:
        """
        패널을 씬에 할당 (정서 전환 기반)

        Args:
            plan: ImagePlacementPlan 객체
            script: Script 객체

        Returns:
            {scene_id: [panel_ids]} 딕셔너리
        """
        scene_panels = {scene.scene_id: [] for scene in script.scenes}

        for transition in plan.transitions:
            scene_id = transition.scene_id
            if scene_id in scene_panels:
                scene_panels[scene_id].append(transition.panel_id)

        # 검증 로그
        for scene_id, panels in scene_panels.items():
            print(f"[EmotionalEngine] 씬 {scene_id}: {len(panels)}개 패널 할당")

        return scene_panels

    def _parse_response(self, content: str) -> dict:
        """Claude 응답에서 JSON 추출"""
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            json_str = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            json_str = content[start:end].strip()
        else:
            json_str = content.strip()

        return json.loads(json_str)
