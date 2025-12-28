"""
대본 생성 엔진 - Claude API 사용
현지화(Localization) + 휴먼터치(Human Touch) 적용
"""
import os
import json
from typing import Optional, Dict
from anthropic import Anthropic

from models.types import Script, Scene
from config import DURATION_SPECS


# 휴먼터치 프롬프트 템플릿
HUMAN_TOUCH_PROMPT = """당신은 유튜브 감성 스토리 영상 전문 작가입니다.
시청자가 영상에 몰입하고 감정적으로 공감할 수 있도록 대본을 작성합니다.

## 휴먼터치 작성 원칙

1. **구체적인 감정 묘사**
   - ❌ "슬펐다" → ✅ "눈시울이 붉어졌다"
   - ❌ "기뻤다" → ✅ "입꼬리가 귀까지 올라갔다"
   - ❌ "힘들었다" → ✅ "두 다리가 천근만근이었다"

2. **감각적 디테일**
   - 시각: "낡은 냉장고 문을 열었다 닫으며..."
   - 청각: "한숨 소리가 방 안에 퍼졌다"
   - 촉각: "거칠어진 손등을 내려다보았다"

3. **내면 독백**
   - "이게 정말 내 인생인가... 싶었다"
   - "그 순간, 모든 것이 멈춘 것 같았다"

4. **극적 전환**
   - 갑작스러운 변화 전 잠시 멈춤
   - "그런데, 그날..."
   - "하지만 운명은 다른 계획을 갖고 있었다"

5. **공감 유발 문장**
   - "누구나 한 번쯤은 이런 순간이 있지 않을까요?"
   - "당신도 이런 경험 있으시죠?"
"""

# 현지화 가이드
LOCALIZATION_GUIDE = {
    "ko": """## 한국 시청자 현지화 가이드

1. **정서적 공감 포인트**
   - 효도, 가족애, 인내와 보상
   - 역경 극복 스토리
   - 작은 것에 감사하는 마음

2. **문화적 변환**
   - 일본 음식점 → 한국 식당 (국밥집, 분식집)
   - 외국 화폐 → 원화로 환산
   - 외국 관습 → 한국 문화로 치환

3. **말투**
   - 나레이션: "~했습니다", "~이었죠" (존댓말)
   - 대사: 상황에 맞는 반말/존댓말 혼용
   - 감탄: "아...", "정말...", "세상에..."

4. **금기사항**
   - 특정 정치 성향 언급
   - 종교적 편향
   - 지역 비하
""",
    "ja": """## 일본 시청자 현지화 가이드

1. **정서적 공감 포인트**
   - 노력과 인내 (努力)
   - 겸손과 배려
   - 장인 정신

2. **문화적 변환**
   - 한국 음식점 → 일본 음식점
   - 원화 → 엔화로 환산

3. **말투**
   - 정중하고 부드러운 표현
   - です/ます 체 기본
"""
}


class ScriptEngine:
    """Claude API를 사용한 대본 생성 (현지화 + 휴먼터치)"""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def generate(self, topic: str, duration_min: int) -> Script:
        """
        주제와 길이를 받아 새 대본 생성

        Args:
            topic: 영상 주제
            duration_min: 영상 길이 (5, 10, 15, 20)

        Returns:
            Script 객체
        """
        spec = DURATION_SPECS.get(duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {duration_min}분")

        num_scenes = spec["scenes"]

        prompt = self._build_prompt(topic, duration_min, num_scenes)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # JSON 파싱
        script_data = self._parse_response(content)

        return self._create_script(script_data, spec, duration_min)

    def rewrite_from_source(
        self,
        source_text: str,
        structure_analysis: Dict,
        duration_min: int,
        target_locale: str = "ko",
        style: str = "emotional"
    ) -> Script:
        """
        원본 대본을 현지화 + 휴먼터치로 재구성

        Args:
            source_text: 원본 대본 (번역된 텍스트)
            structure_analysis: GPT가 분석한 구조 정보
            duration_min: 영상 길이
            target_locale: 목표 지역 (ko, ja)
            style: 스타일 (emotional, informative, dramatic)

        Returns:
            재구성된 Script 객체
        """
        spec = DURATION_SPECS.get(duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {duration_min}분")

        num_scenes = spec["scenes"]

        # 현지화 가이드 가져오기
        locale_guide = LOCALIZATION_GUIDE.get(target_locale, LOCALIZATION_GUIDE["ko"])

        # 재구성 프롬프트
        prompt = self._build_rewrite_prompt(
            source_text=source_text,
            structure=structure_analysis,
            num_scenes=num_scenes,
            duration_min=duration_min,
            locale_guide=locale_guide,
            style=style
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        script_data = self._parse_response(content)

        print(f"[ScriptEngine] 대본 재구성 완료: {len(script_data.get('scenes', []))}개 씬")
        return self._create_script(script_data, spec, duration_min)

    def _build_prompt(self, topic: str, duration_min: int, num_scenes: int) -> str:
        """새 대본 생성 프롬프트"""
        return f"""{HUMAN_TOUCH_PROMPT}

{LOCALIZATION_GUIDE["ko"]}

---

다음 주제로 {duration_min}분 분량의 나레이션 대본을 작성해주세요.

주제: {topic}

요구사항:
1. 총 {num_scenes}개의 씬으로 구성
2. 각 씬은 자연스럽게 연결되어야 함
3. 나레이션 형식 (이야기체)
4. 휴먼터치 원칙을 반드시 적용
5. 각 씬은 약 {duration_min * 60 // num_scenes}초 분량
6. 첫 씬은 강력한 훅(Hook)으로 시작

JSON 형식으로 응답:
```json
{{
  "title": "영상 제목",
  "scenes": [
    {{"title": "씬 제목", "text": "나레이션 텍스트..."}},
    ...
  ]
}}
```"""

    def _build_rewrite_prompt(
        self,
        source_text: str,
        structure: Dict,
        num_scenes: int,
        duration_min: int,
        locale_guide: str,
        style: str
    ) -> str:
        """대본 재구성 프롬프트"""

        # 구조 정보 정리
        structure_info = ""
        if structure:
            if "hook" in structure:
                structure_info += f"- 훅(Hook): {structure['hook']}\n"
            if "emotional_points" in structure:
                structure_info += f"- 감정 고조점: {structure['emotional_points']}\n"
            if "plot_structure" in structure:
                structure_info += f"- 플롯 구조: {structure['plot_structure']}\n"
            if "key_message" in structure:
                structure_info += f"- 핵심 메시지: {structure['key_message']}\n"
            if "recommended_scenes" in structure:
                structure_info += f"- 추천 장면: {structure['recommended_scenes']}\n"

        style_guide = {
            "emotional": "감정을 자극하는 따뜻한 스토리텔링",
            "informative": "정보 전달 중심의 명확한 서술",
            "dramatic": "극적인 전개와 서스펜스"
        }.get(style, "감정적인 스토리텔링")

        return f"""{HUMAN_TOUCH_PROMPT}

{locale_guide}

---

## 원본 대본 (참고용)
{source_text[:3000]}

## 원본 분석 결과
{structure_info}

---

## 과제

위 원본을 바탕으로 **완전히 새로운 대본**을 작성해주세요.

### 요구사항
1. 총 {num_scenes}개의 씬으로 구성
2. 영상 길이: {duration_min}분
3. 스타일: {style_guide}
4. **휴먼터치 원칙 필수 적용**
5. **현지화 가이드 필수 적용**
6. 원본의 핵심 스토리라인은 유지하되, 표현은 완전히 새롭게

### 주의사항
- 원본을 그대로 번역하지 마세요
- 구체적인 감정 묘사를 넣으세요
- 시청자가 주인공에게 감정이입할 수 있게 하세요
- 첫 씬은 강력한 훅(Hook)으로 시작하세요

JSON 형식으로 응답:
```json
{{
  "title": "영상 제목",
  "scenes": [
    {{"title": "씬 제목", "text": "나레이션 텍스트 (휴먼터치 적용)..."}},
    ...
  ]
}}
```"""

    def _create_script(self, script_data: dict, spec: dict, duration_min: int) -> Script:
        """Script 객체 생성"""
        scenes = []
        for i, scene_data in enumerate(script_data["scenes"]):
            panel_start = i * spec["panels_per_scene"] + 1
            panel_end = panel_start + spec["panels_per_scene"]

            scene = Scene(
                scene_id=i + 1,
                title=scene_data.get("title", f"씬 {i + 1}"),
                text=scene_data["text"],
                panel_ids=list(range(panel_start, panel_end))
            )
            scenes.append(scene)

        return Script(
            title=script_data.get("title", ""),
            scenes=scenes,
            duration_min=duration_min,
            total_panels=spec["panels"]
        )

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

    def generate_youtube_metadata(
        self,
        script: Script,
        style: str = "정보",
        duration_min: int = 10
    ) -> dict:
        """
        AI 기반 유튜브 제목 및 썸네일 문구 생성

        Args:
            script: 대본 객체
            style: 콘텐츠 스타일 (불교종교, 뉴스, 정보 등)
            duration_min: 영상 길이 (분)

        Returns:
            {
                "title": "유튜브 제목",
                "thumbnail_text": "썸네일 문구 (1~2줄)",
                "title_alternatives": ["대안 제목1", "대안 제목2"],
                "thumbnail_alternatives": ["대안 썸네일1", "대안 썸네일2"]
            }
        """
        # 대본 내용 요약
        script_summary = f"제목: {script.title}\n\n"
        for scene in script.scenes:
            script_summary += f"[{scene.title}]\n{scene.text[:200]}...\n\n"

        prompt = f"""당신은 유튜브 SEO 전문가이자 썸네일 카피라이터입니다.
아래 대본을 분석하여 유튜브 제목과 썸네일 문구를 생성해주세요.

## 대본 내용
{script_summary}

## 콘텐츠 정보
- 스타일: {style}
- 영상 길이: {duration_min}분

## 유튜브 제목 작성 규칙
1. **후킹(Hooking)이 핵심** - 첫 5글자 내에 호기심/감정 유발
2. **길이**: 40~60자 (너무 길면 잘림)
3. **클릭 유도 패턴 활용**:
   - 경고형: "이것만은 하지 마세요", "절대 ~하면 안됩니다"
   - 상황저격: "오늘도 생각이 많은 분들께", "잠이 안 오는 밤"
   - 반전형: "놓아야 해결됩니다", "포기하니까 됐습니다"
   - 숫자형: "딱 3가지만", "5분만 투자하세요"
   - 질문형: "왜 항상 불안한가요?", "나만 이런가요?"
4. **금지어**: 치료, 완치, 100%, 기적, 무조건, 확실한
5. **대본 핵심 메시지**를 반드시 반영

## 썸네일 문구 작성 규칙
1. **초단문**: 6~12자 (1줄) 또는 10~18자 (2줄)
2. **임팩트 최우선**: 한눈에 들어오는 강렬한 메시지
3. **감정/행동 유발 단어**: 지금, 당장, 꼭, 반드시, 절대, 오늘
4. **2줄 패턴 예시**:
   - "오늘 밤\\n꼭 들으세요"
   - "이런 사람\\n피하세요"
   - "잠들기 전\\n{duration_min}분"
5. **대본의 핵심 키워드** 포함

## 출력 형식 (JSON)
```json
{{
  "title": "메인 유튜브 제목",
  "thumbnail_text": "썸네일 문구 (줄바꿈은 \\n으로)",
  "title_alternatives": ["대안 제목1", "대안 제목2"],
  "thumbnail_alternatives": ["대안 썸네일1", "대안 썸네일2"]
}}
```

대본의 핵심 메시지와 감정을 정확히 담아 유튜브에서 클릭을 유도하는 제목과 썸네일을 만들어주세요."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        try:
            result = self._parse_response(content)
        except json.JSONDecodeError:
            # 파싱 실패 시 기본값 반환
            result = {
                "title": f"{script.title} ({duration_min}분)",
                "thumbnail_text": f"오늘 밤\\n{duration_min}분",
                "title_alternatives": [],
                "thumbnail_alternatives": []
            }

        print(f"[ScriptEngine] 유튜브 메타데이터 생성 완료")
        print(f"  - 제목: {result.get('title', '')[:50]}...")
        print(f"  - 썸네일: {result.get('thumbnail_text', '')}")

        return result

