"""
정서 단락 전환점 분석 엔진
- 장소 변화 (집 → 산길)
- 분위기 변화 (평화 → 긴장)
- 사건 전환 (대화 → 추격)
- 이미지 배치 계획 생성
- DALL-E용 상세 프롬프트 생성 (공통 스타일 프리픽스 + 장면별 상세 설명)
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
    description_ko: str   # 한국어 설명 (짧은 요약)
    description_en: str   # 영어 설명 (DALL-E용 상세 프롬프트, 스타일 프리픽스 포함)
    scene_id: int = 0     # 해당 씬 ID


@dataclass
class ImagePlacementPlan:
    """이미지 배치 계획"""
    total_panels: int
    duration_seconds: float
    style_prefix: str = ""  # 공통 스타일 프리픽스
    transitions: List[TransitionPoint] = field(default_factory=list)

    def to_beats_list(self) -> str:
        """DALL-E 프롬프트용 비트 리스트 생성 (공통 프리픽스 포함)"""
        beats = []
        for i, t in enumerate(self.transitions, 1):
            # description_en에 이미 스타일 프리픽스가 포함되어 있음
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

        # 공통 스타일 프리픽스 추출
        style_prefix = transitions_data.get("style_prefix", "")

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
            style_prefix=style_prefix,
            transitions=transitions
        )

        print(f"[EmotionalEngine] 이미지 프롬프트 생성 완료: {len(transitions)}개")
        print(f"[EmotionalEngine] 스타일 프리픽스: {style_prefix[:50]}...")
        return plan

    def generate_image_prompts(
        self,
        script: Script,
        num_panels: int,
        style_hint: str = ""
    ) -> ImagePlacementPlan:
        """
        대본에서 직접 이미지 프롬프트 생성 (TTS 없이)

        Args:
            script: Script 객체
            num_panels: 생성할 패널 수
            style_hint: 스타일 힌트 (예: "조선시대", "현대 도시", "판타지")

        Returns:
            ImagePlacementPlan 객체
        """
        print(f"[EmotionalEngine] 대본에서 {num_panels}개 이미지 프롬프트 생성 중...")

        # 전체 대본 텍스트 추출
        full_script = f"제목: {script.title}\n\n"
        for scene in script.scenes:
            full_script += f"[{scene.title}]\n{scene.text}\n\n"

        prompt = self._build_direct_prompt(full_script, num_panels, style_hint)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        data = self._parse_response(content)

        style_prefix = data.get("style_prefix", "")
        transitions = []

        for i, t_data in enumerate(data.get("transitions", [])):
            transition = TransitionPoint(
                time_start=0,
                time_end=0,
                panel_id=i + 1,
                transition_type=t_data.get("type", "event"),
                description_ko=t_data.get("description_ko", ""),
                description_en=t_data.get("description_en", ""),
                scene_id=t_data.get("scene_id", 1)
            )
            transitions.append(transition)

        plan = ImagePlacementPlan(
            total_panels=num_panels,
            duration_seconds=0,
            style_prefix=style_prefix,
            transitions=transitions
        )

        print(f"[EmotionalEngine] 프롬프트 생성 완료: {len(transitions)}개")
        return plan

    def _build_direct_prompt(
        self,
        full_script: str,
        num_panels: int,
        style_hint: str
    ) -> str:
        """대본에서 직접 이미지 프롬프트 생성용 프롬프트"""

        style_instruction = ""
        if style_hint:
            style_instruction = f"\n스타일 힌트: {style_hint}"

        return f"""당신은 DALL-E 이미지 프롬프트 전문가입니다.
아래 대본을 읽고, 서사 구조에 맞게 {num_panels}장의 스토리보드 이미지 프롬프트를 생성해주세요.
{style_instruction}

## 대본
{full_script}

## 프롬프트 작성 규칙

### 1. 공통 스타일 프리픽스 (style_prefix)
대본의 시대/배경/분위기에 맞는 공통 스타일을 정의하세요.
예: "Late Joseon Dynasty era setting, traditional Korean hanok architecture, people wearing hanbok, classical Korean painting style, warm color tones, cinematic composition, historical accuracy, atmospheric lighting, emotional visual narrative"

### 2. 서사 구조에 맞는 패널 배분
- 발단 (1-5): 상황 소개, 인물 등장
- 전개 (6-10): 사건 진행, 갈등 시작
- 위기 (11-15): 긴장 고조, 도전
- 절정 (16-20): 최대 위기, 감정 폭발
- 결말 (21-25): 해결, 마무리

### 3. 각 패널 description_en 형식
"[공통 스타일 프리픽스]. [구체적 장면], [인물 묘사], [행동], [조명/분위기], [감정]"

- 최소 50단어 이상 상세하게
- 등장인물 외모/의상 일관성 유지
- 구체적인 행동과 포즈 포함

## 출력 형식 (JSON)

```json
{{
  "style_prefix": "[공통 스타일 프리픽스]",
  "transitions": [
    {{
      "scene_id": 1,
      "type": "location",
      "description_ko": "장면 요약 (한국어, 짧게)",
      "description_en": "[전체 상세 프롬프트 - 스타일 프리픽스 포함]"
    }},
    ...
  ]
}}
```

정확히 {num_panels}개의 패널 프롬프트를 생성하세요."""

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
        """전환점 분석 프롬프트 구성 - 상세 DALL-E 프롬프트 생성"""

        # 씬 정보 텍스트 (전체 텍스트 포함)
        scene_info = ""
        full_script_text = ""
        for scene_id, timing in scene_timings.items():
            scene_info += f"""
씬 {scene_id}: {timing['title']}
- 시간: {timing['start']:.1f}초 ~ {timing['end']:.1f}초 (길이: {timing['duration']:.1f}초)
- 내용: {timing['text']}
"""
            full_script_text += f"{timing['text']}\n\n"

        return f"""당신은 DALL-E 이미지 프롬프트 전문가입니다.
주어진 대본을 분석하여 {total_panels}개의 스토리보드 패널을 위한 상세 이미지 프롬프트를 생성해주세요.

## 대본 정보
제목: {script.title}
총 길이: {total_duration:.1f}초
필요한 이미지 패널 수: {total_panels}장

{scene_info}

## 프롬프트 작성 규칙

### 1. 공통 스타일 프리픽스 (style_prefix)
모든 패널에 공통으로 적용될 스타일 문장을 먼저 정의하세요.
대본의 시대/배경/분위기에 맞게 작성합니다.

예시:
- 조선시대: "Late Joseon Dynasty era setting, traditional Korean hanok architecture, people wearing hanbok, classical Korean painting style, warm color tones, cinematic composition, historical accuracy, atmospheric lighting, emotional visual narrative"
- 현대 도시: "Modern urban setting, contemporary architecture, realistic photographic style, natural lighting, cinematic composition, emotional depth"
- 판타지: "Fantasy world setting, magical atmosphere, vibrant colors, detailed illustration style, dramatic lighting, epic composition"

### 2. 개별 패널 설명 (description_en)
각 패널의 description_en은 다음 형식을 따릅니다:
"[공통 스타일 프리픽스]. [구체적인 장면 설명], [등장인물 묘사], [행동/포즈], [조명/분위기], [감정적 톤]"

예시 (조선시대 이야기):
"Late Joseon Dynasty era setting, traditional Korean hanok architecture, people wearing hanbok, classical Korean painting style, warm color tones, cinematic composition, historical accuracy, atmospheric lighting, emotional visual narrative. Majestic exterior view of a noble family's grand mansion in Bukchon Hanyang, imposing tiled roofs, beautiful traditional garden, aristocratic yangban estate, golden sunset glow"

### 3. 전환점 유형
- location: 장소 변화 (집 → 산길, 실내 → 실외)
- mood: 분위기 변화 (평화 → 긴장, 슬픔 → 희망)
- event: 사건 전환 (대화 → 추격, 일상 → 위기)

### 4. 중요 원칙
1. 정확히 {total_panels}개의 전환점을 생성하세요
2. 감정이 고조되는 장면에 더 많은 패널을 배치하세요
3. description_en은 반드시 영어로, 매우 상세하게 작성하세요
4. 등장인물의 외모/의상은 일관성 있게 묘사하세요
5. 각 패널에서 일어나는 구체적인 행동을 포함하세요

## 출력 형식

JSON으로 응답해주세요:
```json
{{
  "style_prefix": "[대본에 맞는 공통 스타일 프리픽스]",
  "transitions": [
    {{
      "time_start": 0.0,
      "time_end": 15.5,
      "scene_id": 1,
      "type": "location",
      "description_ko": "한씨 가문의 위엄있는 대저택 전경",
      "description_en": "[전체 프롬프트: 스타일 프리픽스 + 상세 장면 설명]"
    }},
    ...
  ]
}}
```

정확히 {total_panels}개의 전환점을 찾아주세요. 각 description_en은 최소 50단어 이상으로 상세하게 작성하세요."""

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
