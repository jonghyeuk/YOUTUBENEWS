"""
대본 생성 엔진 - Claude API 사용
현지화(Localization) + 휴먼터치(Human Touch) 적용
"""
import os
import json
from typing import Optional, Dict
from anthropic import Anthropic

from models.types import Script, Scene
from config import DURATION_SPECS, TRANSLATION_PROMPTS, LANGUAGE_CONFIG


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
        duration_min: int = 10,
        language: str = "ko"
    ) -> dict:
        """
        AI 기반 유튜브 제목, 썸네일 문구, 태그 생성 (다국어 지원)

        Args:
            script: 대본 객체
            style: 콘텐츠 스타일 (불교종교, 뉴스, 정보 등)
            duration_min: 영상 길이 (분)
            language: 출력 언어 (ko, ja, en)

        Returns:
            {
                "title": "유튜브 제목",
                "thumbnail_top_text": "썸네일 상단 텍스트",
                "thumbnail_main_text": "썸네일 메인 텍스트",
                "thumbnail_text": "썸네일 문구 (레거시 호환)",
                "tags": ["태그1", "태그2", ...],
                "title_alternatives": ["대안 제목1", "대안 제목2"],
                "thumbnail_alternatives": ["대안 썸네일1", "대안 썸네일2"]
            }
        """
        # 대본 전체 내용 (최대 6000자까지 - 핵심 메시지 파악을 위해)
        full_script = f"제목: {script.title}\n\n"
        for scene in script.scenes:
            full_script += f"[씬 {scene.scene_id}: {scene.title}]\n{scene.text}\n\n"

        # 너무 길면 잘라냄 (API 토큰 제한 고려)
        if len(full_script) > 6000:
            full_script = full_script[:6000] + "\n...(이하 생략)"

        # 언어별 설정
        lang_config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["ko"])
        lang_name = lang_config.get("name", "한국어")

        # 스타일별 제목 형식 가이드 (태그 형식이 다름)
        style_title_format = {
            # 스토리텔링: [카테고리] 형식
            "스토리텔링:한국불교": {"format": "bracket", "tag": "불교설화/야담"},
            "스토리텔링:중국불교": {"format": "bracket", "tag": "불교설화/야담"},
            "스토리텔링:인도불교": {"format": "bracket", "tag": "불교설화/야담"},
            # 불교 철학/경전: | 출처 형식 (경전 이름은 대본에서 추출)
            "불교종교": {"format": "pipe", "tag": ""},  # 대본에서 경전명 추출
            "불교명상": {"format": "none", "tag": ""},  # 태그 없음
            # 일반 정보: 태그 없음 또는 간단히
            "정보": {"format": "none", "tag": ""},
            "뉴스": {"format": "bracket", "tag": "뉴스"},
            # 일본텔링 (일본어 전용) - 리스트 앵커 포함
            "일본텔링": {"format": "japanese", "tag": "心の処方箋"},
        }
        title_format_info = style_title_format.get(style, {"format": "none", "tag": ""})

        # 일본텔링 스타일일 때 일본어 예시 추가
        japanese_examples = ""
        if style == "일본텔링":
            japanese_examples = """

**일본텔링 콘텐츠 (日本語):**
- "優しすぎる人が壊れる本当の理由【心の処方箋】"
- "嘘をつく自分が嫌いなあなたへ｜仏教的視点"
- "人間関係で疲れた時に効く3つの考え方"

### 일본어 제목 규칙
1. **リスト앵커 권장**: "3つの〜", "5つの〜" 등 숫자 포함
2. **감정 후킹**: "〜なあなたへ", "〜の本当の理由"
3. **태그 형식**: "제목【心の処方箋】" 또는 "제목｜仏教的視点"

### 일본어 썸네일 예시
- 상단: "本音" / 메인: "言えない人ほど\\n傷ついている"
- 상단: "執着" / 메인: "手放した瞬間\\n楽になれる"
- 상단: "3つ" / 메인: "心を守る\\n簡単な習慣"
"""

        prompt = f"""당신은 유튜브 SEO 전문가이자 썸네일 카피라이터입니다.
아래 대본을 **정독**하고, 유튜브용 후킹 제목과 썸네일에 넣을 문구를 만들어주세요.

## 전체 대본
{full_script}

## 콘텐츠 정보
- 스타일: {style}
- 영상 길이: {duration_min}분
- **출력 언어: {lang_name}**
- **제목 태그 형식**: {title_format_info.get('format', 'none')} ({title_format_info.get('tag', '대본에서 추출')})

---

## 🎯 1단계: 대본 핵심 분석 (내부적으로 수행)
먼저 대본을 읽고 다음을 파악하세요:
- 이 영상의 **핵심 메시지/깨달음**은 무엇인가?
- 시청자가 **"어? 이게 뭐지?"** 하고 궁금해할 만한 포인트는?
- 가장 **충격적이거나 반전이 되는 순간**은?
- 이 내용을 **한 문장**으로 압축한다면?

---

## 📺 2단계: 유튜브 제목 작성

### 작성 규칙
1. **후킹(Hooking)이 핵심** - 대본의 핵심 인사이트를 호기심 유발 형태로 변환
2. **제목 형식** (스타일에 따라 다름):
   - 스토리텔링/야담: "제목 [불교설화/야담]" (대괄호 형식)
   - 불교 철학/경전: "제목 | 경전명" (파이프 형식, 능엄경/금강경/법화경 등)
   - 명상/힐링: 제목만 (태그 없음)
3. **클릭 유도 패턴 선택**:
   - 직설적+호기심형: "당신이 보고 있는 이것, 진짜 당신이 아닙니다"
   - 질문+깨달음형: "지금 이 글을 보는 '그것'은 대체 뭘까?"
   - 미스터리+권위형: "2500년 전 부처님이 증명한 '나는 없다'"
4. **금지어**: 치료, 완치, 100%, 기적, 무조건

### 좋은 예시 (스타일별)
**불교 철학/경전 콘텐츠:**
- "당신이 보고 있는 이것, 진짜 당신이 아닙니다 | 능엄경"
- "지금 이 글을 보는 '그것'은 대체 뭘까? | 능엄경 팔환변견"
- "2500년 전 부처님이 증명한 '나는 없다' | 능엄경"

**스토리텔링/야담 콘텐츠:**
- "어머니를 버린 아들과 아들을 살린 어머니 [불교설화]"
- "고요한 새벽 내 방에 든 낯선 여인 [야담]"
{japanese_examples}
---

## 🎨 3단계: 썸네일 문구 작성 (가장 중요!)

### 상단 텍스트 (thumbnail_top_text)
- 2~6자의 **핵심 키워드**
- 대본의 주제/감정을 압축한 단어
- 예: "진짜 나", "깨달음", "능엄경", "그날 밤", "반전"
- ❌ 피해야 할 예: "충격", "대박" (너무 일반적)

### 메인 텍스트 (thumbnail_main_text) ⭐ 가장 중요!
- 10~20자 정도, 줄바꿈 1회 권장 (\\n 사용)
- **대본의 핵심 메시지를 후킹 형태로 변환**
- 시청자가 "이게 무슨 말이지? 클릭해봐야겠다" 하게 만들기

### 좋은 썸네일 예시 (대본 내용 기반)
불교/철학 콘텐츠:
- 상단: "진짜 나" / 메인: "지금 보고 있는\\n이것은 당신이 아닙니다"
- 상단: "깨달음" / 메인: "'보는 것'은 사라져도\\n'보는 성품'은 남는다"
- 상단: "능엄경" / 메인: "돌아갈 곳 없는\\n진짜 '나'"

감동/스토리 콘텐츠:
- 상단: "마지막 편지" / 메인: "아들에게\\n차마 못한 말"
- 상단: "그 순간" / 메인: "엄마가 쓰러진 날\\n알게 된 것"

### ❌ 피해야 할 예시
- "충격" + "아무도 몰랐던 진실" (너무 일반적, 대본과 무관)
- "반전" + "결국 이렇게 됐다" (구체성 없음)

---

## 🏷️ 4단계: 태그 작성
- **정확히 7개** 태그 생성
- 대본 내용과 연관된 검색 키워드

---

## 출력 형식 (JSON)
```json
{{
  "title": "유튜브 제목 (스타일에 맞는 태그 형식 적용)",
  "thumbnail_top_text": "상단 텍스트 (대본 기반 핵심어, 2~6자)",
  "thumbnail_main_text": "메인 텍스트\\n(대본 핵심 메시지 기반, 10~20자)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5", "태그6", "태그7"],
  "title_alternatives": ["대안 제목1", "대안 제목2"],
  "thumbnail_alternatives": ["대안 썸네일1\\n문구", "대안 썸네일2\\n문구"]
}}
```

**핵심**: 썸네일 문구는 **대본 내용에서 추출한 핵심 메시지**를 기반으로 작성하세요!
일반적인 "충격", "반전" 같은 문구 대신, **이 대본만의 고유한 인사이트**를 담으세요."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        try:
            result = self._parse_response(content)
            # 레거시 호환: thumbnail_text 생성
            top = result.get("thumbnail_top_text", "")
            main = result.get("thumbnail_main_text", "")
            if top and main:
                result["thumbnail_text"] = f"{top}\\n{main}"
            elif main:
                result["thumbnail_text"] = main
            else:
                result["thumbnail_text"] = result.get("thumbnail_text", f"오늘 밤\\n{duration_min}분")

            # 태그 기본값 보장
            if "tags" not in result or not result["tags"]:
                result["tags"] = ["옛날이야기", "민담", "설화", "잠잘때듣는", "감동실화"]

        except json.JSONDecodeError:
            # 파싱 실패 시 기본값 반환
            result = {
                "title": f"{script.title}",
                "thumbnail_top_text": "충격",
                "thumbnail_main_text": f"아무도 몰랐던\\n진실",
                "thumbnail_text": f"충격\\n아무도 몰랐던 진실",
                "tags": ["옛날이야기", "민담", "설화", "잠잘때듣는", "감동실화"],
                "title_alternatives": [],
                "thumbnail_alternatives": []
            }

        print(f"[ScriptEngine] 유튜브 메타데이터 생성 완료 ({lang_name})")
        print(f"  - 제목: {result.get('title', '')[:50]}...")
        print(f"  - 썸네일: {result.get('thumbnail_top_text', '')} / {result.get('thumbnail_main_text', '')}")
        print(f"  - 태그: {', '.join(result.get('tags', []))}")

        return result

    def translate_script(
        self,
        script: Script,
        target_language: str,
        style: str = "불교종교"
    ) -> Script:
        """
        대본을 다른 언어로 번역

        Args:
            script: 원본 Script 객체 (한국어)
            target_language: 목표 언어 (ja, en)
            style: 콘텐츠 스타일

        Returns:
            번역된 Script 객체
        """
        if target_language == "ko":
            return script  # 한국어면 그대로 반환

        if target_language not in TRANSLATION_PROMPTS:
            raise ValueError(f"지원하지 않는 언어: {target_language}. 사용 가능: {list(TRANSLATION_PROMPTS.keys())}")

        lang_config = LANGUAGE_CONFIG.get(target_language, {})
        lang_name = lang_config.get("name", target_language)

        # 번역 프롬프트
        translation_guide = TRANSLATION_PROMPTS[target_language]

        # 씬별로 번역
        translated_scenes = []

        for scene in script.scenes:
            prompt = f"""{translation_guide}

## 원본 (한국어)
제목: {scene.title}
내용:
{scene.text}

## 번역 지침
- 콘텐츠 스타일: {style}
- 감정과 분위기를 유지하면서 자연스럽게 번역
- 현지 문화에 맞게 표현 조정

JSON 형식으로 응답:
```json
{{
  "title": "번역된 제목",
  "text": "번역된 내용"
}}
```"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            try:
                translated = self._parse_response(content)
                translated_scenes.append(Scene(
                    scene_id=scene.scene_id,
                    title=translated.get("title", scene.title),
                    text=translated.get("text", scene.text),
                    panel_ids=scene.panel_ids
                ))
            except json.JSONDecodeError:
                # 파싱 실패 시 원본 유지
                print(f"[ScriptEngine] 씬 {scene.scene_id} 번역 파싱 실패, 원본 유지")
                translated_scenes.append(scene)

        # 제목 번역
        title_prompt = f"""{translation_guide}

## 원본 제목 (한국어)
{script.title}

간결하게 번역해주세요. 번역된 제목만 텍스트로 응답:"""

        title_response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": title_prompt}]
        )

        translated_title = title_response.content[0].text.strip()

        print(f"[ScriptEngine] 대본 번역 완료: {lang_name}")
        print(f"  - 원본 제목: {script.title}")
        print(f"  - 번역 제목: {translated_title}")
        print(f"  - 씬 수: {len(translated_scenes)}개")

        return Script(
            title=translated_title,
            scenes=translated_scenes,
            duration_min=script.duration_min,
            total_panels=script.total_panels
        )

    def translate_text(
        self,
        text: str,
        target_language: str,
        context: str = "일반"
    ) -> str:
        """
        단일 텍스트 번역 (제목, 설명 등)

        Args:
            text: 원본 텍스트 (한국어)
            target_language: 목표 언어 (ja, en)
            context: 번역 컨텍스트 (제목, 설명, 태그 등)

        Returns:
            번역된 텍스트
        """
        if target_language == "ko":
            return text

        if target_language not in TRANSLATION_PROMPTS:
            return text

        translation_guide = TRANSLATION_PROMPTS[target_language]

        prompt = f"""{translation_guide}

## 번역 컨텍스트
{context}

## 원본 (한국어)
{text}

번역된 텍스트만 응답 (추가 설명 없이):"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

