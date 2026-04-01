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


def _sanitize_json_control_chars(s: str) -> str:
    """JSON 문자열 값 안의 이스케이프되지 않은 제어문자를 이스케이프 처리."""
    result = []
    in_string = False
    i = 0
    length = len(s)
    while i < length:
        c = s[i]
        if c == '"':
            num_bs = 0
            j = i - 1
            while j >= 0 and s[j] == '\\':
                num_bs += 1
                j -= 1
            if num_bs % 2 == 0:
                in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


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
            "dramatic": "극적인 전개와 서스펜스",
            "자유모드": "사용자 입력 중심 - 논지 변질 금지, 극적 보강만"
        }.get(style, "감정적인 스토리텔링")

        # 자유모드 전용 지시사항
        free_mode_instruction = ""
        if style == "자유모드":
            free_mode_instruction = """
## ⚠️ 자유모드 - "살을 붙이는 작가" 스타일

당신은 **고스트라이터(대필작가)**입니다.
사용자가 준 간략한 이야기에 "살을 붙여서" 풍성한 대본으로 완성하세요.

### 핵심 원칙: 뼈대는 그대로, 살만 붙인다

**뼈대 (절대 건드리지 마세요):**
- 사용자가 전하려는 핵심 논지/메시지
- 사용자가 언급한 인물, 사건, 상황
- 이야기의 결론과 교훈

**살 (당신이 붙일 것):**
- 감정 묘사: "힘들었다" → "가슴이 먹먹해졌다"
- 상황 디테일: 시간, 장소, 날씨, 분위기
- 내면 독백: 인물의 속마음, 갈등
- 감각 묘사: 시각, 청각, 촉각으로 생생하게
- 극적 전환: "그런데 그 순간...", "하지만..."

### 작업 방식
1. 사용자 입력을 **정독**하고 핵심 논지 파악
2. 이야기 뼈대를 **그대로 유지**
3. 각 장면에 감정/상황 디테일을 **살처럼 붙임**
4. 이야기꾼처럼 **몰입감 있게** 풀어냄
5. 사용자의 메시지로 **자연스럽게 마무리**

### 말투 규칙 (필수)
- 화자는 독자/시청자에게 **친절한 존댓말**로 이야기합니다
- 나레이션은 반드시 "~습니다", "~했습니다", "~이었습니다", "~지요", "~셨습니다" 등 존댓말 어미 사용
- ❌ 반말 금지: "~했다", "~이었다", "~한다", "~일까"
- ✅ 올바른 예: "그렇습니다", "우리 마음은 이렇지요", "참 대단하셨습니다", "한번 들어보시겠습니까"
- 대사(직접 인용)는 상황에 맞게 반말/존댓말 혼용 가능하나, 나레이션은 항상 존댓말

### 금지사항
- 논지를 바꾸거나 다른 결론으로 유도 금지
- 사용자가 언급 안 한 새 인물/사건 창작 금지
- 불교/종교 등 특정 세계관 임의 삽입 금지
- 나레이션에서 반말 사용 금지

"""

        return f"""{HUMAN_TOUCH_PROMPT}

{locale_guide}
{free_mode_instruction}
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

        return json.loads(_sanitize_json_control_chars(json_str))

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
            # 뉴스
            "뉴스": {"format": "bracket", "tag": "뉴스"},
            # 일본텔링 (일본어 전용) - 리스트 앵커 포함
            "일본텔링": {"format": "japanese", "tag": "心の処方箋"},
            # 영어Saying전용 (English Only) - Christian Devotional
            "영어Saying전용": {"format": "english", "tag": "Morning Prayer"},
            # 자유모드 - 사용자 이야기 중심, 태그 없음
            "자유모드": {"format": "none", "tag": ""},
        }
        title_format_info = style_title_format.get(style, {"format": "none", "tag": ""})

        # 언어별 스타일 예시 추가
        language_specific_examples = ""
        if style == "일본텔링":
            language_specific_examples = """

**일본텔링 콘텐츠 (日本語 - シニア相談形):**
- "優しすぎる人が壊れる本当の理由【心の処方箋】"
- "嫁姑問題で悩むあなたへ｜許さなくていい3つの理由"
- "熟年離婚を考えた時に知っておくべきこと"
- "人間関係で疲れた時に効く3つの考え方"

### 일본어 제목 규칙
1. **リスト앵커 권장**: "3つの〜", "5つの〜" 등 숫자 포함
2. **감정 후킹**: "〜なあなたへ", "〜の本当の理由"
3. **태그 형식**: "제목【心の処方箋】" 또는 "제목｜シニアの知恵"
4. **인기 주제**: 嫁姑問題, 熟年離婚, 老後の孤独, 娘との確執, 相続トラブル

### 일본어 썸네일 예시
- 상단: "本音" / 메인: "言えない人ほど\\n傷ついている"
- 상단: "嫁姑" / 메인: "許さなくていい\\nその理由"
- 상단: "3つ" / 메인: "心を守る\\n簡単な習慣"
"""
        elif style == "영어Saying전용":
            language_specific_examples = """

**영어Saying전용 콘텐츠 (English):**
- "The Prayer That Changes Everything | Morning Blessing"
- "God's Message For You Today [Daily Devotional]"
- "3 Ways to Find Peace When Life Gets Hard"

### English Title Rules
1. **Emotional Hook**: "The truth about...", "Why you need...", "What God wants you to know"
2. **Promise of Value**: "That changes everything", "You need to hear today"
3. **Tag Format**: "Title | Morning Prayer" or "Title [Daily Devotional]"

### English Thumbnail Examples
- Top: "PRAY THIS" / Main: "The Morning Prayer\\nThat Changes Everything"
- Top: "GOD SAYS" / Main: "This Message\\nIs For You Today"
- Top: "3 KEYS" / Main: "To Finding Peace\\nIn Difficult Times"
"""
        elif style == "자유모드":
            language_specific_examples = """

**자유모드 콘텐츠 (감동/교훈 스토리):**
- "이 이야기, 끝까지 들어보세요 (10분)"
- "듣고 나면 생각이 바뀝니다"
- "누구에게도 말 못한 이야기"
- "인생이 달라지는 깨달음"

### 자유모드 제목 규칙
1. **사용자 이야기 중심**: 입력된 내용의 핵심을 그대로 살림
2. **극적 전개 강조**: 갈등 → 절정 → 깨달음 구조
3. **교훈/깨달음 암시**: "듣고 나면...", "생각이 바뀝니다"
4. **태그 없음**: 순수 제목만 사용

### 자유모드 썸네일 예시
- 상단: "실화" / 메인: "듣고 나면\\n생각이 바뀝니다"
- 상단: "교훈" / 메인: "이 이야기\\n끝까지 들어보세요"
- 상단: "인생" / 메인: "이걸 몰랐다면\\n손해입니다"
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
{language_specific_examples}
---

## 🎨 3단계: 썸네일 문구 작성 (가장 중요!)

### 🎯 핵심 원칙: 감정을 건드려라!
썸네일은 **시청자의 감정**을 자극해야 합니다:
- **호기심**: "이게 뭐지? 뭔 소리야?" → 클릭 유도
- **놀람**: "설마 이게 진짜야?" → 확인 욕구
- **반박 심리**: "아니 그건 아니지 않나?" → 반론하고 싶어서 클릭
- **공감**: "어... 나도 그런데?" → 자기 이야기 같아서 클릭
- **불안/걱정**: "나도 해당되나?" → 확인하고 싶어서 클릭

### ⚠️ 핵심: 상단과 메인은 하나의 문장처럼 연결되어야 함!
- 상단 텍스트는 메인 텍스트의 **도입부/키워드** 역할
- 둘을 합치면 **하나의 완성된 메시지**가 되어야 함
- ❌ 나쁜 예: 상단 "돈이 당신을 바꾼다" + 메인 "재물운이 터지는 시기" (각각 따로 노는 느낌)
- ✅ 좋은 예: 상단 "재물운" + 메인 "당신의 삶을 바꾸는\\n그 날이 옵니다" (연결됨)
- ✅ 좋은 예: 상단 "그날 밤" + 메인 "엄마가 쓰러진 날\\n알게 된 것" (상단이 메인의 시작)

### 상단 텍스트 (thumbnail_top_text)
- 2~6자의 **감정 유발 키워드**
- 메인 텍스트와 **자연스럽게 연결**되는 도입부
- 예: "진짜 나", "그날 밤", "이건 아닌데", "왜 나만", "설마"
- ❌ 피해야 할 예: "충격", "대박" (너무 일반적, 감정 없음)
- ❌ 피해야 할 예: 메인과 관계없는 독립적인 문장

### 메인 텍스트 (thumbnail_main_text) ⭐ 가장 중요!
- 10~20자 정도, 줄바꿈 1회 권장 (\\n 사용)
- **"이게 뭐지?" 반응을 유도**하는 문구
- 패턴 예시:
  - 반전형: "~인 줄 알았는데\\n아니었습니다"
  - 질문형: "왜 ~하면\\n~할까요?"
  - 단정형: "~는 사실\\n~입니다" (반박 심리 유발)
  - 공감형: "~하는 사람들의\\n공통점"

### 좋은 썸네일 예시 (감정 유발)
불교/철학 콘텐츠:
- 상단: "진짜 나" / 메인: "지금 보고 있는\\n이것은 당신이 아닙니다" (호기심+놀람)
- 상단: "이건 아닌데" / 메인: "'나'라고 믿던 것이\\n환상이었습니다" (반박 심리)
- 상단: "왜 나만" / 메인: "불안한 사람들의\\n공통점 하나" (공감+불안)

감동/스토리 콘텐츠:
- 상단: "그날 밤" / 메인: "엄마가 쓰러진 날\\n알게 된 것" (호기심+공감)
- 상단: "설마" / 메인: "아버지의 유품에서\\n나온 편지" (놀람+호기심)

영어 콘텐츠:
- Top: "WAIT" / Main: "This changes\\nEVERYTHING" (호기심)
- Top: "NOT TRUE" / Main: "What you believed\\nwas a lie" (반박 심리)

### ❌ 피해야 할 예시
- "충격" + "아무도 몰랐던 진실" (감정 없음, 너무 일반적)
- "반전" + "결국 이렇게 됐다" (구체성 없음, 호기심 유발 안 됨)
- 대본 내용과 무관한 자극적 문구 (낚시 = 신뢰 하락)

---

## 🏷️ 4단계: 태그 작성
- **정확히 7개** 태그 생성
- 대본 내용과 연관된 검색 키워드

---

## 출력 형식 (JSON)
```json
{{
  "title": "유튜브 제목 (스타일에 맞는 태그 형식 적용)",
  "thumbnail_top_text": "상단 키워드 (메인과 연결되는 도입부, 2~6자)",
  "thumbnail_main_text": "메인 텍스트\\n(상단과 합쳐서 하나의 메시지, 10~20자)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5", "태그6", "태그7"],
  "title_alternatives": ["대안 제목1", "대안 제목2"],
  "thumbnail_alternatives": ["대안 썸네일1\\n문구", "대안 썸네일2\\n문구"]
}}
```

**핵심 1**: 썸네일은 **감정을 건드려야** 합니다!
**핵심 2**: 상단과 메인은 **하나의 연결된 메시지**여야 합니다!
- 상단 "재물운" + 메인 "당신에게 찾아오는\\n그 날" = 연결됨 ✅
- 상단 "돈이 삶을 바꾼다" + 메인 "재물운이 터지는 시기" = 따로 놀음 ❌"""

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

