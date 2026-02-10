"""
Gradio UI - AI 콘텐츠 생성기
스타일: 불교강의/불교명상/스토리텔링(한국/중국/인도)/일본텔링/영어Saying전용
"""
import os
from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from PIL import Image
import json
import copy
import traceback

from pipeline import Pipeline


def _sanitize_json_control_chars(s: str) -> str:
    """JSON 문자열 값 안의 이스케이프되지 않은 제어문자(줄바꿈 등)를 이스케이프 처리.

    Claude가 JSON string 내부에 literal newline을 넣으면 json.loads()가 실패함.
    이 함수는 문자열 안팎을 추적하면서 string 내부의 제어문자만 이스케이프한다.
    """
    result = []
    in_string = False
    i = 0
    length = len(s)
    while i < length:
        c = s[i]
        if c == '"':
            # 앞의 연속 백슬래시 갯수를 세서 실제 이스케이프인지 판별
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
from engines import ScriptEngine, ImageEngine
from engines.thumbnail_engine import ThumbnailEngine
from styles import (
    STYLE_PROMPTS, BUDDHIST_LECTURE_EPISODE_TYPES, get_buddhist_lecture_prompt,
    # 일본텔링 전용
    JAPAN_SERIES_CONFIG, get_japan_prompt, get_japan_review_prompt, get_japan_image_prompt_with_prop,
    # 영어 디보셔널 전용
    ENGLISH_STYLE_CONFIG, get_english_prompt, get_english_review_prompt, get_english_image_prompt_with_prop,
)  # 스타일별 프롬프트 (파일 분리됨)
from config import (
    DURATION_SPECS, BGM_CONFIG,
    YOUTUBE_TITLE_TEMPLATES, YOUTUBE_DEFAULT_TAGS,
    YOUTUBE_DESCRIPTION_TEMPLATE, YOUTUBE_FORBIDDEN_WORDS,
    # 다국어 설정
    LANGUAGE_CONFIG, TRANSLATION_PROMPTS,
    YOUTUBE_DESCRIPTION_TEMPLATE_JA, YOUTUBE_DEFAULT_TAGS_JA,
    YOUTUBE_DESCRIPTION_TEMPLATE_EN, YOUTUBE_DEFAULT_TAGS_EN,
)

# 전역 파이프라인 인스턴스
pipeline = Pipeline()
thumbnail_engine = ThumbnailEngine()

# ═══════════════════════════════════════════════════════════════
# 스타일별 프롬프트 템플릿 → styles/ 폴더로 분리됨
# STYLE_PROMPTS는 styles/__init__.py에서 import
# ═══════════════════════════════════════════════════════════════

# JSON 출력 형식 + 이미지 프롬프트 통합
INTEGRATED_OUTPUT_FORMAT = """

## 출력 형식 (JSON) - 대본 + 이미지 프롬프트 통합
각 씬마다 나레이션과 이미지 프롬프트를 함께 작성하세요.

```json
{{
  "title": "영상 제목",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "씬 제목",
      "text": "나레이션 텍스트 (이 씬에서 읽을 내용)",
      "image_prompts": [
        "English image prompt 1 for this scene, detailed visual description, mood, lighting, composition",
        "English image prompt 2 for this scene (if needed)"
      ],
      "importance": 3
    }}
  ]
}}
```

## ⚠️⚠️⚠️ 분량 규칙 (절대 준수!) ⚠️⚠️⚠️
이 영상은 **정확히 {duration}분** 길이여야 합니다.

### 필수 요구사항:
1. **총 나레이션**: 최소 {total_chars}자 이상 (TTS 속도 0.9 기준, 분당 180자)
2. **씬 개수**: 정확히 {num_scenes}개
3. **씬당 글자 수**: 각 씬마다 최소 {chars_per_scene}자 이상

### 글자 수 체크리스트:
- 5분 = 900자 이상
- 10분 = 1,800자 이상
- 15분 = 2,700자 이상
- 20분 = 3,600자 이상

### 중요한 경고:
- 각 씬의 text가 200자 미만이면 **거부됩니다**
- 전체 글자 수가 {total_chars}자 미만이면 **거부됩니다**
- 각 씬에서 상황, 감정, 대화, 설명을 충분히 서술하세요
- 급하게 요약하지 말고, 천천히 자세하게 이야기하세요

## 이미지 프롬프트 규칙
- 영어로 작성
- 400자 이내
- 구체적인 시각적 묘사 (조명, 색감, 구도)
- **씬당 정확히 1개** (중요!)
- 전체 이미지: 씬 개수와 동일하게 {num_scenes}장"""

# 스타일별 이미지 스타일 가이드
STYLE_IMAGE_GUIDES = {
    "불교강의": "soft ink wash illustration, contemplative atmosphere, warm neutral tones, minimalist composition, meditative mood, wide negative space",
    "영어Saying전용": "warm spiritual illustration, peaceful sunrise, golden hour lighting, serene landscape, hopeful atmosphere, pastoral scene, soft natural light, gentle colors, no text, no dark themes",
    "스토리텔링": "Dark mysterious atmosphere, dramatic lighting, suspenseful mood, shadows",
    "스토리텔링:한국불교": "classical Korean ink-wash narrative painting, Joseon dynasty landscape painting style, soft mineral colors, traditional hanok and village scenery, wide negative space, storytelling composition, gentle brush texture, hand-painted feeling, no anime, no modern illustration, no bright digital colors, no cartoon style",
    "스토리텔링:중국불교": "buddhist icon narrative painting, flat symbolic composition, traditional temple painting style, strong primary colors, no perspective realism, spiritual sacred mood, storytelling iconography, no anime, no modern illustration",
    "스토리텔링:인도불교": "narrative concept art illustration, soft pencil sketch, desaturated muted colors, low contrast shading, wide negative space, storyboard composition, no cute, no anime gloss, no bright color",
    "불교명상": "ethereal Buddhist temple illustration, peaceful dawn atmosphere, soft moonlight on lotus pond, misty mountain monastery, gentle candlelight in dharma hall, serene meditation space, traditional Korean temple architecture, muted pastel colors, dreamy atmosphere, wide negative space, no text, no people close-up, no modern elements, no anime style",
    "일본텔링": "soft watercolor illustration, gentle muted colors, peaceful atmosphere, minimalist composition, Japanese aesthetic, middle-aged or senior Japanese person, contemplative mood, no anime, no cute style, no harsh contrast",
    "영어디보셔널": "warm spiritual illustration, peaceful sunrise, golden hour lighting, serene landscape, hopeful atmosphere, pastoral scene, soft natural light, gentle colors, soft sunlight streaming through window, no text, no dark themes"
}

# 스타일 → StoryMaker 설정 매핑
STYLE_TO_STORYMAKER = {
    "스토리텔링:한국불교": {
        "region": "korea",
        "world_style": "classical_inkwash",
        "character_type": "old_monk",
    },
    "스토리텔링:중국불교": {
        "region": "china",
        "world_style": "buddhist_icon",
        "character_type": "old_monk",
    },
    "스토리텔링:인도불교": {
        "region": "india",
        "world_style": "narrative_concept",
        "character_type": "old_monk",
    },
}

# 스타일별 입력 가이드
STYLE_GUIDES = {
    "불교강의": """**💡 불교강의 v2 (역사 미스터리형)**: 경전/선사/논쟁/수행/유물 주제를 입력하세요!

📚 **에피소드 타입 선택**:
- 경전 성립/전승: 금강경 32분, 현장법사 번역
- 선사 일화/공안: 조주 무, 달마 9년 벽관
- 전승 논쟁/해석: 돈오점수, 남북종 갈등
- 수행 이야기: 간화선 화두, 염불 수행
- 유물/장소: 목탁의 비밀, 사리의 행방

🎯 **핵심 구조**: 콜드오픈(15초 훅) → 역사적 문제 → 인물/사건 → 짧은 가르침 → 여운 회수
⚡ **초반 15초**: 구체 장면 + 미스터리 + 스테이크 + 약속
📌 **역사 핀**: 사실/전승/논쟁 라벨 필수 (최소 3개)
⚠️ **금지**: 반복 문장, 추상어 과다, 교리 30% 초과""",
    "스토리텔링:한국불교": """**💡 한국불교 스토리텔링**: 한국 불교/선종/경전/역사적 일화를 입력하세요.

🎨 **스타일**: 조선 수묵채색 정본화 (Classical Korean Ink-Wash)
📍 **배경**: 산사, 암자, 한옥마을, 조선 풍경
👤 **인물**: 스님, 선비, 백성 (한국인 이목구비)""",
    "스토리텔링:중국불교": """**💡 중국불교 스토리텔링**: 중국 불교 설화/선종 공안/역사적 일화를 입력하세요.

🎨 **스타일**: 불교 도상화 (Buddhist Icon Narrative)
📍 **배경**: 사찰 벽화, 당송명청 사원
👤 **인물**: 선사, 보살, 나한 (평면적 도상)""",
    "스토리텔링:인도불교": """**💡 인도불교 스토리텔링**: 붓다 시대/초기불교/자타카 이야기를 입력하세요.

🎨 **스타일**: 서사 콘셉트아트 (Narrative Concept Art)
📍 **배경**: 녹야원, 보리수, 간다라 풍경
👤 **인물**: 붓다, 제자, 수행자 (실루엣 스케치)""",
    "불교명상": """**💡 불교 수면명상**: '분위기/장소 키워드'를 입력하세요!

✅ 새벽 산사, 달빛 연못, 법당의 고요함, 대나무 숲
❌ 부처님 말씀, 교훈, 설교 (❌ 인용 없음!)

**구조**: 호흡 안내 → Body Scan → 시각화 여행 → 페이드아웃
**핵심**: 실제 명상 유도, 감각 묘사 중심, 교훈/설교 없음""",
    "일본텔링": """**💡 일본텔링 (日本語専用)**: Seed Line을 입력하세요!

예시: "나도 모르게 거짓말을 합니다" / "가족이 부담스럽습니다"

🎯 **대상**: 일본 40~70대, 인간관계에 지친 분들
🎨 **스타일**: 부드러운 수채화, 차분한 분위기
📝 **구조**: Hook → 共感 → 正体 → 仏教的視点 → 実践 → まとめ
⚠️ **주의**: 일본어로 직접 생성됨 (번역 아님)""",
    "영어Saying전용": """**💡 영어Saying전용 (English Only)**: Theme/Topic을 입력하세요!

예시: "Trusting God in difficult times" / "Finding peace in chaos"

🎯 **대상**: 글로벌 영어권, 40~70대
🎨 **스타일**: 따뜻한 영적 일러스트, 황금빛 일출/일몰
📝 **구조**: Hook → Teaching 1,2,3 → Prayer → CTA & Blessing
⚠️ **주의**: 영어로 직접 생성됨 (번역 아님)
🙏 **특징**: "My dear friends" 호칭, Anchor phrase 반복, 성경 레퍼런스""",
    "영어디보셔널": """**💡 영어 디보셔널 (English Devotional)**: Theme/Topic을 입력하세요!

예시: "When anxiety keeps you awake" / "Trusting God with your finances"

🎯 **대상**: 미국/영어권 35~70대 (tired, anxious, faith-seeking)
🎨 **스타일**: 따뜻한 영적 일러스트 + 창문으로 들어오는 햇살 (시그니처)
📝 **구조**: Hook → Teaching → Application → Bible Story → Reframe → Practice → Prayer → CTA
⚠️ **AI티 제거**: micro-scene + softener + 클리셰 블랙리스트 + 2패스 검수
🙏 **옵션**: 기도 톤 (gentle/warfare), CTA 강도 (soft/medium)"""
}

def update_style_guide(style: str):
    return STYLE_GUIDES.get(style, STYLE_GUIDES["불교강의"])


# ═══════════════════════════════════════════════════════════════
# 스크립트 번역 (현지화)
# ═══════════════════════════════════════════════════════════════

def translate_script_to_language(script_data: dict, language: str) -> dict:
    """스크립트를 대상 언어로 현지화 번역"""
    if language == "ko":
        return script_data  # 한국어면 그대로 반환

    from anthropic import Anthropic
    client = Anthropic()

    # 번역할 텍스트 추출
    texts_to_translate = []
    texts_to_translate.append(f"TITLE: {script_data['title']}")

    for scene in script_data["scenes"]:
        texts_to_translate.append(f"SCENE_TITLE_{scene['scene_id']}: {scene['title']}")
        texts_to_translate.append(f"SCENE_TEXT_{scene['scene_id']}: {scene['text']}")

    combined_text = "\n---\n".join(texts_to_translate)

    # 번역 프롬프트 구성
    base_prompt = TRANSLATION_PROMPTS.get(language, "")
    if not base_prompt:
        return script_data

    prompt = f"""{base_prompt}

## 번역할 내용
{combined_text}

## 출력 형식
각 항목을 동일한 형식으로 번역하세요:
TITLE: [번역된 제목]
---
SCENE_TITLE_1: [번역된 씬 제목]
---
SCENE_TEXT_1: [번역된 나레이션]
---
... (모든 항목)

중요: 이미지 프롬프트는 번역하지 마세요 (이미 영어입니다)."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    translated_text = response.content[0].text

    # 번역 결과 파싱
    translated_data = script_data.copy()
    translated_data["scenes"] = [scene.copy() for scene in script_data["scenes"]]

    for line in translated_text.split("---"):
        line = line.strip()
        if line.startswith("TITLE:"):
            translated_data["title"] = line.replace("TITLE:", "").strip()
        elif line.startswith("SCENE_TITLE_"):
            try:
                parts = line.split(":", 1)
                scene_id = int(parts[0].replace("SCENE_TITLE_", ""))
                for scene in translated_data["scenes"]:
                    if scene["scene_id"] == scene_id:
                        scene["title"] = parts[1].strip()
            except:
                pass
        elif line.startswith("SCENE_TEXT_"):
            try:
                parts = line.split(":", 1)
                scene_id = int(parts[0].replace("SCENE_TEXT_", ""))
                for scene in translated_data["scenes"]:
                    if scene["scene_id"] == scene_id:
                        scene["text"] = parts[1].strip()
            except:
                pass

    return translated_data


def _translate_existing_script(language: str):
    """기존 원본 스크립트를 새 언어로 번역 (새로 생성하지 않음)"""
    if not pipeline.project or not hasattr(pipeline.project, 'original_script_data'):
        return "❌ 원본 스크립트가 없습니다. 한국어로 먼저 생성하세요.", "", "", "", ""

    original_data = pipeline.project.original_script_data

    # 이미지 프롬프트 추출 (원본에서)
    all_image_prompts = []
    for s in original_data["scenes"]:
        image_prompts = s.get("image_prompts", [])
        all_image_prompts.extend(image_prompts)

    # 언어 설정
    lang_info = LANGUAGE_CONFIG.get(language, {})
    lang_name = lang_info.get("name", language)

    # 번역 수행 (항상 원본에서)
    print(f"[번역] 원본 한국어 → {lang_name}로 현지화 중...")
    data = translate_script_to_language(copy.deepcopy(original_data), language)

    # 언어 설정 저장
    pipeline.project.language = language

    # Script 객체 생성
    from models.types import Script, Scene
    scenes = []

    for i, s in enumerate(data["scenes"]):
        original_prompts = original_data["scenes"][i].get("image_prompts", []) if i < len(original_data["scenes"]) else []

        scenes.append(Scene(
            scene_id=s["scene_id"],
            title=s["title"],
            text=s["text"],
            image_count=len(original_prompts) if original_prompts else 0,
            importance=s.get("importance", 3)
        ))

    duration = pipeline.project.duration if hasattr(pipeline.project, 'duration') else 10

    script = Script(
        title=data["title"],
        scenes=scenes,
        duration_min=duration,
        total_panels=len(all_image_prompts)
    )
    pipeline.project.script = script

    # 스크립트 미리보기
    preview = f"# {script.title}\n\n"
    preview += f"**{lang_name} | {len(scenes)}개 씬 | 이미지 {len(all_image_prompts)}장**\n\n"

    for i, scene in enumerate(script.scenes):
        preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
        preview += f"🖼️ {scene.image_count}장\n\n"
        preview += f"{scene.text}\n\n---\n\n"

    # 이미지 프롬프트 포맷팅
    prompts_text = ""
    for i, prompt in enumerate(all_image_prompts, 1):
        prompts_text += f"이미지 {i}: {prompt}\n\n"

    # AI 기반 유튜브 제목/썸네일 생성 (새 언어로)
    try:
        yt_metadata = pipeline.generate_youtube_metadata(language=language)
        yt_title = yt_metadata.get("title", script.title)
        yt_thumbnail = yt_metadata.get("thumbnail_text", "")

        title_info = f"**AI 추천 제목**: {yt_title}"
        thumb_info = f"**AI 추천 썸네일**: {yt_thumbnail}"
    except Exception as e:
        print(f"[YouTube 메타데이터] 생성 실패: {e}")
        yt_title = script.title
        title_info = f"**기본 제목**: {yt_title}"
        thumb_info = ""

    return (
        f"✅ {lang_name} 번역 완료! (원본에서 번역)",
        preview,
        prompts_text,
        yt_title,
        thumb_info
    )


# ═══════════════════════════════════════════════════════════════
# 통합 스크립트 + 이미지 프롬프트 생성
# ═══════════════════════════════════════════════════════════════

def generate_script_and_images(topic: str, duration: int, style: str, language: str = "ko", episode_type: str = "sutra_origin", japan_series: str = "senior", japan_twopass: bool = True, english_prayer_style: str = "gentle", english_cta_strength: str = "soft", english_twopass: bool = True):
    """주제 입력 → 스크립트 + 이미지 프롬프트 한번에 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", "", ""

    try:
        # 기존 프로젝트가 있고 원본 스크립트가 있으면 번역만 수행
        if (pipeline.project and
            hasattr(pipeline.project, 'original_script_data') and
            pipeline.project.original_script_data and
            language != "ko"):

            print(f"[스크립트] 기존 원본 발견 - 번역만 수행 ({language})")
            return _translate_existing_script(language)

        # 프로젝트 생성 (스타일 저장)
        project = pipeline.create_project(topic, duration)
        project.style = style  # 스타일 저장
        project.episode_type = episode_type  # 에피소드 타입 저장 (불교강의용)

        # 일본텔링 전용 옵션 저장
        if style == "일본텔링":
            project.japan_series = japan_series
            project.japan_twopass = japan_twopass

        # 영어 디보셔널 전용 옵션 저장
        if style == "영어디보셔널":
            project.english_prayer_style = english_prayer_style
            project.english_cta_strength = english_cta_strength
            project.english_twopass = english_twopass

        # 스타일에 따른 언어 자동 설정 (썸네일 폰트 선택에 사용)
        if style == "일본텔링":
            project.language = "ja"
        elif style in ["영어Saying전용", "영어디보셔널"]:
            project.language = "en"
        else:
            project.language = "ko"

        # 분량에 따른 글자 수 계산 (TTS 속도 0.9 기준, 분당 약 180자)
        from config import DURATION_SPECS
        spec = DURATION_SPECS.get(duration, DURATION_SPECS[10])
        num_scenes = spec["scenes"]
        total_chars = duration * 180  # 분당 약 180자
        chars_per_scene = total_chars // num_scenes

        # 스타일별 프롬프트 구성
        # 불교강의: v2 역사 미스터리형 (에피소드 타입 적용)
        if style == "불교강의":
            base_prompt = get_buddhist_lecture_prompt(topic, duration, episode_type)
            print(f"[스크립트] 불교강의 v2 사용 - 에피소드 타입: {episode_type}")
        # 일본텔링: 시리즈별 프롬프트 (Senior/Adult)
        elif style == "일본텔링":
            base_prompt = get_japan_prompt(topic, duration, japan_series)
            series_name = JAPAN_SERIES_CONFIG.get(japan_series, {}).get("name", japan_series)
            print(f"[스크립트] 일본텔링 사용 - 시리즈: {series_name}, 2패스: {japan_twopass}")
        # 영어 디보셔널: prayer_style + cta_strength 옵션
        elif style == "영어디보셔널":
            base_prompt = get_english_prompt(topic, english_prayer_style, english_cta_strength, duration)
            prayer_name = ENGLISH_STYLE_CONFIG["prayer_style"].get(english_prayer_style, {}).get("name", english_prayer_style)
            cta_name = ENGLISH_STYLE_CONFIG["cta_strength"].get(english_cta_strength, {}).get("name", english_cta_strength)
            print(f"[스크립트] 영어디보셔널 사용 - 기도톤: {prayer_name}, CTA: {cta_name}, 2패스: {english_twopass}, 분량: {duration}분")
        # 자유모드: 완전 독립 - 다른 스타일과 절대 섞이지 않음
        elif style == "자유모드":
            # 자유모드 전용 프롬프트 (출력 형식 포함)
            prompt = f"""# 자유모드 - 살을 붙이는 작가

당신은 **고스트라이터(대필작가)**입니다.
사용자가 준 이야기에 "살을 붙여서" 풍성한 대본으로 완성하세요.

## 핵심 원칙 (절대 준수!)
1. **뼈대(논지) 100% 유지**: 사용자가 준 핵심 메시지, 주제, 결론은 단 한 글자도 바꾸지 마세요
2. **살(디테일)만 추가**: 감정 묘사, 상황 설명, 장면 전환 등 극적 요소만 보강
3. **창작 절대 금지**: 새로운 사건, 인물, 결론, 교훈을 추가하지 마세요
4. **원문 존중**: 사용자 글의 어투와 분위기를 유지하세요

## 사용자 입력 내용
{topic}

## 분량 규칙
- **{duration}분** 분량 = 최소 **{total_chars}자** 이상
- **씬 개수**: {num_scenes}개
- **씬당 글자 수**: 각 씬 최소 {chars_per_scene}자 이상

## 출력 형식 (JSON)
```json
{{
  "title": "사용자 이야기에서 추출한 제목",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "씬 제목",
      "text": "나레이션 텍스트 (살을 붙인 내용)",
      "image_prompts": ["English image prompt, visual description of scene"],
      "importance": 3
    }}
  ]
}}
```

## 이미지 프롬프트 규칙
- 영어로 작성, 400자 이내
- 씬당 정확히 1개
- 이야기 내용에 맞는 자연스러운 장면 묘사
- 스타일: warm illustration, soft lighting, emotional atmosphere
"""
            print(f"[스크립트] 자유모드 사용 - 살을 붙이는 작가 스타일 (독립 모드)")

            # 자유모드는 여기서 바로 API 호출 (다른 스타일과 섞이지 않음)
            from anthropic import Anthropic
            client = Anthropic()

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # JSON 파싱
            try:
                json_str = None
                if "```json" in result_text:
                    start = result_text.find("```json") + 7
                    end = result_text.find("```", start)
                    json_str = result_text[start:end].strip()
                elif "```" in result_text and "{" in result_text:
                    start = result_text.find("```") + 3
                    end = result_text.find("```", start)
                    if end > start:
                        json_str = result_text[start:end].strip()
                if not json_str or not json_str.startswith("{"):
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    if start != -1 and end > start:
                        json_str = result_text[start:end]

                data = json.loads(_sanitize_json_control_chars(json_str))

                # 결과 저장
                pipeline.project.script_data = data
                pipeline.project.original_script_data = copy.deepcopy(data)

                # 이미지 프롬프트 추출
                all_image_prompts = []
                for scene in data.get("scenes", []):
                    prompts = scene.get("image_prompts", [])
                    if isinstance(prompts, list):
                        all_image_prompts.extend(prompts)
                    elif prompts:
                        all_image_prompts.append(prompts)

                # Script 객체 생성
                from models.types import Script, Scene
                scenes = []
                for s in data.get("scenes", []):
                    scenes.append(Scene(
                        scene_id=s.get("scene_id", 0),
                        title=s.get("title", ""),
                        text=s.get("text", ""),
                        image_count=len(s.get("image_prompts", [])),
                        importance=s.get("importance", 3)
                    ))

                script = Script(
                    title=data.get("title", topic[:20]),
                    scenes=scenes,
                    duration_min=duration,
                    total_panels=len(all_image_prompts)
                )
                pipeline.project.script = script

                # 스크립트 미리보기 (markdown 형식)
                preview = f"# {script.title}\n\n"
                preview += f"**🇰🇷 한국어 | {len(scenes)}개 씬 | 이미지 {len(all_image_prompts)}장**\n\n"
                for scene in scenes:
                    preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
                    preview += f"🖼️ {scene.image_count}장\n\n"
                    preview += f"{scene.text}\n\n---\n\n"

                # 이미지 프롬프트 포맷팅
                prompts_text = ""
                for i, prompt in enumerate(all_image_prompts, 1):
                    prompts_text += f"이미지 {i}: {prompt}\n\n"

                # 유튜브 메타데이터 생성
                try:
                    yt_metadata = pipeline.generate_youtube_metadata()
                    yt_title = yt_metadata.get("title", script.title)
                    yt_thumbnail = yt_metadata.get("thumbnail_text", "")
                except Exception as e:
                    print(f"[자유모드] YouTube 메타데이터 생성 실패: {e}")
                    yt_title = script.title
                    yt_thumbnail = f"오늘의 이야기\n{duration}분"

                return (
                    f"✅ 자유모드 완료! {len(scenes)}개 씬, {len(all_image_prompts)}장 이미지",
                    preview,
                    prompts_text,
                    yt_title,
                    yt_thumbnail.replace("\\n", "\n")
                )

            except Exception as e:
                return f"❌ JSON 파싱 오류: {str(e)}", result_text[:500], "", "", ""
        # 불교명상: 완전 독립 - 사용자 글을 불교적 관점에서 확장
        elif style == "불교명상":
            prompt = f"""# 불교명상 - 불교적 관점의 고스트라이터

당신은 **불교적 관점에서 글을 확장하는 고스트라이터**입니다.
사용자가 준 이야기에 불교적 지혜와 위로를 더해 풍성한 대본으로 완성하세요.

## 핵심 원칙 (절대 준수!)
1. **뼈대(논지) 100% 유지**: 사용자가 준 핵심 메시지, 주제, 결론은 단 한 글자도 바꾸지 마세요
2. **불교적 살 추가**: 무상(無常), 인연, 업보, 자비, 집착, 마음 다스림 등 불교적 관점으로 해석
3. **새로운 경전/일화 날조 금지**: 사용자가 언급하지 않은 경전 구절, 부처님 일화를 지어내지 마세요
4. **원문 존중**: 사용자 글의 핵심 감정과 상황을 유지하세요

## 불교적 확장 방법
- 사용자의 고통/상황을 무상(無常)의 관점에서 바라보기
- 집착을 내려놓는 지혜로 위로하기
- 인연의 소중함으로 관계 해석하기
- 마음의 평화를 찾는 명상적 분위기 조성
- **단, 모든 불교적 해석은 사용자 글에서 출발해야 함**

## 톤과 문체
- 명상적이고 차분한 어조
- "~입니다", "~합니다" 경어체
- 60세 이상 시니어 대상 - 어려운 불교 용어는 쉽게 풀어서

## 사용자 입력 내용
{topic}

## 분량 규칙
- **{duration}분** 분량 = 최소 **{total_chars}자** 이상
- **씬 개수**: {num_scenes}개
- **씬당 글자 수**: 각 씬 최소 {chars_per_scene}자 이상

## 출력 형식 (JSON)
```json
{{
  "title": "사용자 이야기에서 추출한 제목",
  "scenes": [
    {{
      "scene_id": 1,
      "title": "씬 제목",
      "text": "나레이션 텍스트 (불교적 관점으로 확장된 내용)",
      "image_prompts": ["English image prompt, visual description of scene"],
      "importance": 3
    }}
  ]
}}
```

## 이미지 프롬프트 규칙
- 영어로 작성, 400자 이내
- 씬당 정확히 1개
- 스타일: ethereal Buddhist temple illustration, peaceful dawn atmosphere, soft moonlight, misty mountain monastery, meditative mood, muted pastel colors
"""
            print(f"[스크립트] 불교명상 사용 - 불교적 고스트라이터 스타일 (독립 모드)")

            # 불교명상도 독립 API 호출 (다른 스타일과 섞이지 않음)
            from anthropic import Anthropic
            client = Anthropic()

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # JSON 파싱
            try:
                json_str = None
                if "```json" in result_text:
                    start = result_text.find("```json") + 7
                    end = result_text.find("```", start)
                    json_str = result_text[start:end].strip()
                elif "```" in result_text and "{" in result_text:
                    start = result_text.find("```") + 3
                    end = result_text.find("```", start)
                    if end > start:
                        json_str = result_text[start:end].strip()
                if not json_str or not json_str.startswith("{"):
                    start = result_text.find("{")
                    end = result_text.rfind("}") + 1
                    if start != -1 and end > start:
                        json_str = result_text[start:end]

                data = json.loads(_sanitize_json_control_chars(json_str))

                # 결과 저장
                pipeline.project.script_data = data
                pipeline.project.original_script_data = copy.deepcopy(data)

                # 이미지 프롬프트 추출
                all_image_prompts = []
                for scene in data.get("scenes", []):
                    prompts = scene.get("image_prompts", [])
                    if isinstance(prompts, list):
                        all_image_prompts.extend(prompts)
                    elif prompts:
                        all_image_prompts.append(prompts)

                # Script 객체 생성
                from models.types import Script, Scene
                scenes = []
                for s in data.get("scenes", []):
                    scenes.append(Scene(
                        scene_id=s.get("scene_id", 0),
                        title=s.get("title", ""),
                        text=s.get("text", ""),
                        image_count=len(s.get("image_prompts", [])),
                        importance=s.get("importance", 3)
                    ))

                script = Script(
                    title=data.get("title", topic[:20]),
                    scenes=scenes,
                    duration_min=duration,
                    total_panels=len(all_image_prompts)
                )
                pipeline.project.script = script

                # 스크립트 미리보기 (markdown 형식)
                preview = f"# {script.title}\n\n"
                preview += f"**🇰🇷 한국어 | {len(scenes)}개 씬 | 이미지 {len(all_image_prompts)}장**\n\n"
                for scene in scenes:
                    preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
                    preview += f"🖼️ {scene.image_count}장\n\n"
                    preview += f"{scene.text}\n\n---\n\n"

                # 이미지 프롬프트 포맷팅
                prompts_text = ""
                for i, prompt in enumerate(all_image_prompts, 1):
                    prompts_text += f"이미지 {i}: {prompt}\n\n"

                # 유튜브 메타데이터 생성
                try:
                    yt_metadata = pipeline.generate_youtube_metadata()
                    yt_title = yt_metadata.get("title", script.title)
                    yt_thumbnail = yt_metadata.get("thumbnail_text", "")
                except Exception as e:
                    print(f"[불교명상] YouTube 메타데이터 생성 실패: {e}")
                    yt_title = script.title
                    yt_thumbnail = f"마음의 평화\n{duration}분"

                return (
                    f"✅ 불교명상 완료! {len(scenes)}개 씬, {len(all_image_prompts)}장 이미지",
                    preview,
                    prompts_text,
                    yt_title,
                    yt_thumbnail.replace("\\n", "\n")
                )

            except Exception as e:
                return f"❌ JSON 파싱 오류: {str(e)}", result_text[:500], "", "", ""
        else:
            base_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["불교강의"])
            base_prompt = base_prompt.format(topic=topic, duration=duration)

        image_style = STYLE_IMAGE_GUIDES.get(style, "")

        prompt = base_prompt
        # 영어디보셔널/일본텔링은 자체 프롬프트에 출력 형식이 있으므로 INTEGRATED_OUTPUT_FORMAT 추가 안 함
        if style not in ("영어디보셔널", "일본텔링"):
            prompt += INTEGRATED_OUTPUT_FORMAT.format(
                duration=duration,
                total_chars=total_chars,
                num_scenes=num_scenes,
                chars_per_scene=chars_per_scene
            )
            prompt += f"\n\n## 이미지 스타일\n{image_style}"

        # Claude API 호출
        from anthropic import Anthropic
        client = Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        # JSON 파싱 (더 robust하게)
        try:
            json_str = None

            # 방법 1: ```json 코드 블록에서 추출
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                json_str = result_text[start:end].strip()
            # 방법 2: ``` 코드 블록에서 추출 (json 태그 없이)
            elif "```" in result_text and "{" in result_text:
                start = result_text.find("```") + 3
                end = result_text.find("```", start)
                if end > start:
                    json_str = result_text[start:end].strip()

            # 방법 3: { } 사이에서 JSON 추출
            if not json_str or not json_str.startswith("{"):
                first_brace = result_text.find("{")
                last_brace = result_text.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = result_text[first_brace:last_brace + 1]

            if not json_str:
                raise json.JSONDecodeError("No JSON found", result_text, 0)

            data = json.loads(_sanitize_json_control_chars(json_str))

            # ═══════════════════════════════════════════════════════════════
            # 일본텔링 2패스 검수 (선택된 경우만)
            # ═══════════════════════════════════════════════════════════════
            if style == "일본텔링" and japan_twopass:
                print(f"[일본텔링] 2패스 검수 시작...")
                review_prompt = get_japan_review_prompt()
                review_input = review_prompt + "\n\n" + json.dumps(data, ensure_ascii=False, indent=2)

                review_response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": review_input}]
                )

                review_result = review_response.content[0].text

                # 검수된 JSON 파싱
                try:
                    if "```json" in review_result:
                        rev_start = review_result.find("```json") + 7
                        rev_end = review_result.find("```", rev_start)
                        review_json_str = review_result[rev_start:rev_end].strip()
                    elif "```" in review_result and "{" in review_result:
                        rev_start = review_result.find("```") + 3
                        rev_end = review_result.find("```", rev_start)
                        if rev_end > rev_start:
                            review_json_str = review_result[rev_start:rev_end].strip()
                        else:
                            review_json_str = None
                    else:
                        first_brace = review_result.find("{")
                        last_brace = review_result.rfind("}")
                        if first_brace != -1 and last_brace != -1:
                            review_json_str = review_result[first_brace:last_brace + 1]
                        else:
                            review_json_str = None

                    if review_json_str:
                        reviewed_data = json.loads(_sanitize_json_control_chars(review_json_str))
                        data = reviewed_data
                        print(f"[일본텔링] 2패스 검수 완료 - 수정 적용됨")
                    else:
                        print(f"[일본텔링] 2패스 검수 - JSON 추출 실패, 원본 유지")
                except json.JSONDecodeError as e:
                    print(f"[일본텔링] 2패스 검수 JSON 파싱 실패: {e}, 원본 유지")

            # ═══════════════════════════════════════════════════════════════
            # 영어 디보셔널 2패스 검수 (선택된 경우만)
            # ═══════════════════════════════════════════════════════════════
            if style == "영어디보셔널" and english_twopass:
                print(f"[영어디보셔널] 2패스 검수 시작...")
                review_prompt = get_english_review_prompt()
                review_input = review_prompt + "\n\n" + json.dumps(data, ensure_ascii=False, indent=2)

                review_response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8192,
                    messages=[{"role": "user", "content": review_input}]
                )

                review_result = review_response.content[0].text

                # 검수된 JSON 파싱
                try:
                    if "```json" in review_result:
                        rev_start = review_result.find("```json") + 7
                        rev_end = review_result.find("```", rev_start)
                        review_json_str = review_result[rev_start:rev_end].strip()
                    elif "```" in review_result and "{" in review_result:
                        rev_start = review_result.find("```") + 3
                        rev_end = review_result.find("```", rev_start)
                        if rev_end > rev_start:
                            review_json_str = review_result[rev_start:rev_end].strip()
                        else:
                            review_json_str = None
                    else:
                        first_brace = review_result.find("{")
                        last_brace = review_result.rfind("}")
                        if first_brace != -1 and last_brace != -1:
                            review_json_str = review_result[first_brace:last_brace + 1]
                        else:
                            review_json_str = None

                    if review_json_str:
                        reviewed_data = json.loads(_sanitize_json_control_chars(review_json_str))
                        data = reviewed_data
                        print(f"[영어디보셔널] 2패스 검수 완료 - 수정 적용됨")
                    else:
                        print(f"[영어디보셔널] 2패스 검수 - JSON 추출 실패, 원본 유지")
                except json.JSONDecodeError as e:
                    print(f"[영어디보셔널] 2패스 검수 JSON 파싱 실패: {e}, 원본 유지")

            # 원본 스크립트 저장 (다국어 번역용)
            # 항상 원본에서 번역해야 일본어→영어 같은 문제 방지
            pipeline.project.original_script_data = copy.deepcopy(data)
            print(f"[스크립트] 스크립트 저장 완료")

            # 이미지 프롬프트 먼저 추출 (번역 전에)
            all_image_prompts = []
            for s in data.get("scenes", []):
                image_prompts = s.get("image_prompts", [])
                # 일본텔링: signature prop (スマホ通知) 추가
                if style == "일본텔링":
                    image_prompts = [get_japan_image_prompt_with_prop(p) for p in image_prompts]
                # 영어디보셔널: signature prop (window sunlight) 추가
                elif style == "영어디보셔널":
                    image_prompts = [get_english_image_prompt_with_prop(p) for p in image_prompts]
                all_image_prompts.extend(image_prompts)

            # 번역 (한국어가 아닌 경우) - 항상 원본에서 번역
            # 단, 영어디보셔널/일본텔링은 이미 해당 언어로 생성되므로 번역 불필요
            lang_info = LANGUAGE_CONFIG.get(language, {})
            lang_name = lang_info.get("name", "🇰🇷 한국어")

            if language != "ko" and style not in ("영어디보셔널", "일본텔링"):
                print(f"[번역] 원본 한국어 → {lang_name}로 현지화 중...")
                data = translate_script_to_language(pipeline.project.original_script_data, language)

            # 언어 설정 저장
            pipeline.project.language = language

            # Script 객체 생성
            from models.types import Script, Scene
            scenes = []

            for i, s in enumerate(data.get("scenes", [])):
                original_prompts = s.get("image_prompts", [])

                # 영어Saying전용 / 영어디보셔널: key_sentence 추출
                key_sentence = ""
                if style in ("영어Saying전용", "영어디보셔널"):
                    key_sentence = s.get("key_sentence", "")

                scenes.append(Scene(
                    scene_id=s.get("scene_id", i + 1),
                    title=s.get("title", ""),
                    text=s.get("text", ""),
                    image_count=len(original_prompts) if original_prompts else 0,
                    importance=s.get("importance", 3),
                    key_sentence=key_sentence
                ))

            script = Script(
                title=data.get("title", topic[:30]),
                scenes=scenes,
                duration_min=duration,
                total_panels=len(all_image_prompts)
            )
            pipeline.project.script = script

            # 스크립트 미리보기
            preview = f"# {script.title}\n\n"
            preview += f"**{lang_name} | {len(scenes)}개 씬 | 이미지 {len(all_image_prompts)}장**\n\n"

            for i, scene in enumerate(script.scenes):
                preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
                preview += f"🖼️ {scene.image_count}장\n\n"
                # 영어Saying전용: key_sentence 표시
                if scene.key_sentence:
                    preview += f"**📺 KEY: {scene.key_sentence}**\n\n"
                preview += f"{scene.text}\n\n---\n\n"

            # 이미지 프롬프트 포맷팅
            prompts_text = ""
            for i, prompt in enumerate(all_image_prompts, 1):
                prompts_text += f"이미지 {i}: {prompt}\n\n"

            # AI 기반 유튜브 제목/썸네일 생성
            try:
                yt_metadata = pipeline.generate_youtube_metadata()
                yt_title = yt_metadata.get("title", script.title)
                yt_thumbnail = yt_metadata.get("thumbnail_text", "")
                # 대안들도 포함
                title_alts = yt_metadata.get("title_alternatives", [])
                thumb_alts = yt_metadata.get("thumbnail_alternatives", [])

                title_info = f"**AI 추천 제목**: {yt_title}"
                if title_alts:
                    title_info += f"\n\n**대안**: " + " | ".join(title_alts[:2])

                thumb_info = f"**AI 추천 썸네일**: {yt_thumbnail}"
                if thumb_alts:
                    thumb_info += f"\n\n**대안**: " + " | ".join(thumb_alts[:2])
            except Exception as e:
                print(f"[YouTube Metadata] 생성 실패: {e}")
                yt_title = script.title
                yt_thumbnail = f"오늘 밤\n{duration}분"
                title_info = f"**기본 제목**: {yt_title}"
                thumb_info = f"**기본 썸네일**: {yt_thumbnail}"

            return (
                f"✅ 생성 완료! {lang_name} | {len(scenes)}개 씬, {len(all_image_prompts)}장 이미지",
                preview,
                prompts_text,
                yt_title,
                yt_thumbnail.replace("\\n", "\n")
            )

        except json.JSONDecodeError:
            return "⚠️ JSON 파싱 실패 - 원본 확인", result_text, "", "", ""

    except Exception as e:
        traceback.print_exc()
        return f"❌ 오류: {type(e).__name__}: {e}", "", "", "", ""


# ═══════════════════════════════════════════════════════════════
# TTS 생성
# ═══════════════════════════════════════════════════════════════

def get_elevenlabs_usage_info():
    """ElevenLabs 사용량 정보 가져오기 (모든 계정)"""
    import os
    from engines.tts_engine import TTSEngine
    results = []

    # 메인 계정 사용량
    try:
        tts = TTSEngine(engine="elevenlabs", style=None)
        usage = tts.get_elevenlabs_usage()
        if usage:
            results.append(
                f"📊 **ElevenLabs (기본)**: "
                f"{usage['used']:,} / {usage['limit']:,} 문자 "
                f"({usage['percent']}%) | "
                f"리셋: {usage['reset_date']} | {usage['tier']}"
            )
    except Exception as e:
        print(f"[ElevenLabs] 기본 계정 조회 오류: {e}")

    # limkony 계정 사용량
    if os.getenv("ELEVENLABS_API_KEY_LIMKONY"):
        try:
            tts_limkony = TTSEngine(engine="elevenlabs2.5_limkony", style=None)
            usage_limkony = tts_limkony.get_elevenlabs_usage()
            if usage_limkony:
                results.append(
                    f"🔵 **ElevenLabs (limkony)**: "
                    f"{usage_limkony['used']:,} / {usage_limkony['limit']:,} 문자 "
                    f"({usage_limkony['percent']}%) | "
                    f"리셋: {usage_limkony['reset_date']} | {usage_limkony['tier']}"
                )
        except Exception as e:
            results.append(f"🔵 **ElevenLabs (limkony)**: ⚠️ 조회 실패 - {e}")
    else:
        results.append("🔵 **ElevenLabs (limkony)**: ⚠️ API 키 미설정 (.env에 ELEVENLABS_API_KEY_LIMKONY 추가)")

    return "\n\n".join(results) if results else ""


def preview_tts_script(engine: str):
    """TTS에 입력될 대사 미리보기"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트를 먼저 생성하세요"

    script = pipeline.project.script
    style = getattr(pipeline.project, 'style', None)
    total_scenes = len(script.scenes)

    # ElevenLabs 사용량 표시
    usage_info = ""
    if engine in ("elevenlabs", "elevenlabs2.5", "elevenlabs2.5_limkony"):
        usage_info = get_elevenlabs_usage_info()
        if usage_info:
            usage_info = f"\n\n{usage_info}\n\n---\n"

    # EMOTION_TAGS 가져오기
    from config import EMOTION_TAGS
    from engines.tts_engine import STYLE_DEFAULT_EMOTIONS_V25, convert_to_tts_text

    preview = f"## 🎙️ TTS 입력 대사 미리보기\n"
    preview += f"**엔진**: {engine} | **스타일**: {style or '없음'} | **씬**: {total_scenes}개\n"
    if usage_info:
        preview += usage_info
    preview += "\n---\n\n"

    # TTS 변환 규칙 안내
    preview += "### 📝 TTS 전처리 규칙\n"
    preview += "- 한자 병기 제거: `임(林)` → `임`\n"
    preview += "- 년도 변환: `501년` → `오백일년`\n"
    preview += "- 특수 괄호 제거: `<<금강경>>` → `금강경`\n"
    preview += "- 특수 따옴표 정규화\n\n---\n\n"

    for i, scene in enumerate(script.scenes):
        position = i / total_scenes

        # 감정 태그 결정 (ElevenLabs v3 + 스타일일 때만)
        tag = ""
        emotion_info = ""
        if engine == "elevenlabs" and style and style in EMOTION_TAGS:
            tags = EMOTION_TAGS[style]
            if position < 0.15:
                tag = tags.get("intro", "")
            elif position < 0.5:
                tag = tags.get("body_sad", tags.get("body", ""))
            elif position < 0.75:
                tag = tags.get("body_hope", tags.get("climax", ""))
            elif position < 0.9:
                tag = tags.get("climax", "")
            else:
                tag = tags.get("ending", "")
        # ElevenLabs Turbo v2.5 감정 흉내 표시 (limkony 포함)
        elif engine in ("elevenlabs2.5", "elevenlabs2.5_limkony") and style and style in STYLE_DEFAULT_EMOTIONS_V25:
            emotions = STYLE_DEFAULT_EMOTIONS_V25[style]
            if position < 0.15:
                emotion_info = emotions.get("intro", "neutral")
            elif position < 0.4:
                emotion_info = emotions.get("body_early", "neutral")
            elif position < 0.7:
                emotion_info = emotions.get("body_late", "neutral")
            elif position < 0.9:
                emotion_info = emotions.get("climax", "neutral")
            else:
                emotion_info = emotions.get("ending", "calm")

        # TTS 전처리 적용
        original_text = scene.text
        tts_text = convert_to_tts_text(original_text)
        has_changes = original_text.strip() != tts_text.strip()

        preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
        if tag:
            preview += f"🎭 **감정태그 (v3)**: `{tag}`\n\n"
        elif emotion_info:
            preview += f"🎭 **감정흉내 (v2.5)**: `{emotion_info}` → voice_settings 자동 조정\n\n"

        # 변환 전/후 비교 표시
        if has_changes:
            preview += f"**📄 원본:**\n```\n{original_text}\n```\n\n"
            preview += f"**🔊 TTS용 (변환됨):**\n```\n{tts_text}\n```\n\n"
        else:
            preview += f"**🔊 TTS 입력:**\n```\n{tts_text}\n```\n\n"

    return preview


def generate_tts(engine: str, speed: float = 0.9, language: str = None):
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", None, ""
    try:
        # 프로젝트에 저장된 스타일 가져오기
        style = getattr(pipeline.project, 'style', None)

        # 언어: 파라미터로 전달된 값 우선, 없으면 프로젝트 저장값 사용
        if language:
            pipeline.project.language = language  # 프로젝트 언어 업데이트
        else:
            language = getattr(pipeline.project, 'language', 'ko')
        lang_name = LANGUAGE_CONFIG.get(language, {}).get("name", "🇰🇷 한국어")

        audio_path = pipeline.step3_generate_tts(engine, style=style, speed=speed)
        total = sum(s.duration for s in pipeline.project.audio_segments)

        # TTS 입력 대사 로그
        tts_log = preview_tts_script(engine)

        # ElevenLabs 사용량 표시
        usage_info = ""
        if engine in ("elevenlabs", "elevenlabs2.5", "elevenlabs2.5_limkony"):
            from engines.tts_engine import TTSEngine
            tts = TTSEngine(engine=engine, style=style, language=language)
            usage = tts.get_elevenlabs_usage()
            if usage:
                if engine == "elevenlabs":
                    model_name = "v3"
                elif engine == "elevenlabs2.5":
                    model_name = "Turbo v2.5"
                else:
                    model_name = "Turbo v2.5 limkony"
                usage_info = (
                    f"\n\n📊 ElevenLabs ({model_name}) 사용량: "
                    f"{usage['used']:,} / {usage['limit']:,} 문자 "
                    f"({usage['percent']}%) | "
                    f"리셋: {usage['reset_date']} | "
                    f"플랜: {usage['tier']}"
                )

        return f"✅ TTS 완료 ({lang_name}, {total:.1f}초, 속도 {speed}x){usage_info}", audio_path, tts_log
    except Exception as e:
        return f"❌ 오류: {e}", None, ""


# ═══════════════════════════════════════════════════════════════
# 이미지 생성
# ═══════════════════════════════════════════════════════════════

def parse_image_prompts(prompts_text: str):
    lines = prompts_text.strip().split("\n")
    parsed = []
    for line in lines:
        line = line.strip()
        if line.startswith("이미지") or line.startswith("Image"):
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[1].strip():
                    parsed.append(parts[1].strip())
    if not parsed:
        parsed = [l.strip() for l in lines if l.strip() and not l.startswith("#") and len(l.strip()) > 20]
    return parsed


def generate_images_from_text(prompts_text: str, engine: str, model: str, style: str = "불교강의", image_style: str = "korea"):
    if not pipeline.project:
        return "❌ 스크립트 먼저 생성하세요", []
    try:
        prompts = parse_image_prompts(prompts_text)
        if not prompts:
            return "❌ 프롬프트 파싱 실패", []

        # 스토리텔링 스타일일 때 StoryMaker 설정 전달
        storymaker_config = None
        if style in STYLE_TO_STORYMAKER:
            # 기존 스토리텔링 스타일: 고정된 region 사용
            storymaker_config = STYLE_TO_STORYMAKER[style]
            print(f"[App] 스토리텔링 스타일 감지: {style} → {storymaker_config}")
        elif style in ("불교강의", "불교명상"):
            # 불교강의/불교명상: 사용자가 선택한 image_style 적용
            storymaker_config = {"region": image_style}
            print(f"[App] {style} 이미지 스타일 적용: region={image_style}")

        image_paths = pipeline.step4_generate_images_from_prompts(
            prompts=prompts,
            engine=engine,
            model=model,
            storymaker_config=storymaker_config
        )
        images = [Image.open(p) for p in image_paths]
        return f"✅ 이미지 생성 완료 ({len(images)}장, 모델: {model}, 스타일: {style})", images
    except Exception as e:
        return f"❌ 오류: {e}", []


def apply_existing_images():
    """현재 프로젝트의 기존 이미지를 그대로 적용 (다국어 버전용)"""
    if not pipeline.project:
        return "❌ 프로젝트가 없습니다", []

    try:
        project_dir = os.path.join("projects", pipeline.project.project_id)
        images_dir = os.path.join(project_dir, "images")

        if not os.path.exists(images_dir):
            return "❌ images 폴더가 없습니다. 먼저 이미지를 생성하세요.", []

        # 이미지 파일 찾기 (정렬해서 순서 유지)
        image_files = sorted([
            f for f in os.listdir(images_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        ])

        if not image_files:
            return "❌ 이미지 파일이 없습니다", []

        # 전체 경로로 변환
        image_paths = [os.path.join(images_dir, f) for f in image_files]

        # pipeline에 이미지 경로 설정
        pipeline.project.cut_paths = image_paths

        # 씬별 이미지 할당 (씬 수에 맞게 분배)
        if pipeline.project.script and pipeline.project.script.scenes:
            scenes = pipeline.project.script.scenes
            if len(image_paths) == len(scenes):
                # 1:1 매핑
                for i, scene in enumerate(scenes):
                    scene.image_paths = [image_paths[i]]
            else:
                # 균등 분배
                images_per_scene = max(1, len(image_paths) // len(scenes))
                for i, scene in enumerate(scenes):
                    start_idx = i * images_per_scene
                    scene.image_paths = image_paths[start_idx:start_idx + images_per_scene]

        # 갤러리 표시용 이미지 로드
        images = [Image.open(p) for p in image_paths]

        return f"✅ 기존 이미지 적용 완료 ({len(images)}장)", images

    except Exception as e:
        return f"❌ 오류: {e}", []


# 엔진별 모델 옵션
IMAGE_MODEL_OPTIONS = {
    "fal-anime": [
        ("flux-schnell (빠름/$0.003)", "flux-schnell"),
        ("flux-dev (균형/$0.025)", "flux-dev"),
        ("flux-pro (고품질/$0.05)", "flux-pro"),
        ("flux-pro-v1.1 (최신/$0.05)", "flux-pro-v1.1"),
        ("flux-ultra (최고품질/$0.06)", "flux-ultra"),
    ],
    "fal-realistic": [
        ("flux-schnell (빠름/$0.003)", "flux-schnell"),
        ("flux-dev (균형/$0.025)", "flux-dev"),
        ("flux-pro (고품질/$0.05)", "flux-pro"),
        ("flux-pro-v1.1 (최신/$0.05)", "flux-pro-v1.1"),
        ("flux-ultra (최고품질/$0.06)", "flux-ultra"),
    ],
    "imagen": [
        ("imagen-3-fast (빠름/저렴)", "imagen-3-fast"),
        ("imagen-3 (고품질)", "imagen-3"),
    ],
    "dalle": [
        ("DALL-E 3", "dall-e-3"),
    ],
    "storymaker": [
        ("GPT Image 1.5 (스토리텔링전용)", "gpt-image-1.5"),
    ],
}


def update_model_choices(engine: str):
    """엔진 변경시 모델 선택 옵션 업데이트"""
    choices = IMAGE_MODEL_OPTIONS.get(engine, IMAGE_MODEL_OPTIONS["fal-anime"])
    default_value = choices[0][1] if choices else None
    return gr.update(choices=choices, value=default_value)


# ═══════════════════════════════════════════════════════════════
# 영상 렌더링
# ═══════════════════════════════════════════════════════════════

def generate_subtitles(use_whisper: bool):
    if not pipeline.project or not pipeline.project.audio_segments:
        return "❌ TTS 생성 필요", ""
    try:
        path = pipeline.step5_generate_subtitles(use_whisper)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return "✅ 자막 생성 완료", content[:2000]
    except Exception as e:
        return f"❌ 오류: {e}", ""


def get_bgm_list():
    """BGM 폴더에서 사용 가능한 파일 목록 가져오기"""
    bgm_folder = BGM_CONFIG.get("folder", "assets/bgm")
    if not os.path.exists(bgm_folder):
        os.makedirs(bgm_folder, exist_ok=True)
        return []

    bgm_files = []
    for f in os.listdir(bgm_folder):
        if f.endswith((".mp3", ".wav", ".m4a")):
            bgm_files.append(f)
    return sorted(bgm_files)


def refresh_bgm_list():
    """BGM 목록 새로고침"""
    bgm_files = get_bgm_list()
    if not bgm_files:
        return gr.update(choices=["(BGM 없음 - assets/bgm 폴더에 추가)"], value=None), None
    choices = ["(BGM 없음)"] + bgm_files
    return gr.update(choices=choices, value=None), None


def preview_bgm(selected_bgm: str):
    """BGM 미리듣기"""
    if not selected_bgm or selected_bgm.startswith("("):
        return None
    bgm_folder = BGM_CONFIG.get("folder", "assets/bgm")
    bgm_path = os.path.join(bgm_folder, selected_bgm)
    if os.path.exists(bgm_path):
        return bgm_path
    return None


def render_video(use_ken_burns: bool, selected_bgm: str, bgm_volume: float):
    if not pipeline.project or not pipeline.project.cut_paths:
        return "❌ 이미지 생성 필요", None
    try:
        # BGM 경로 결정
        bgm_path = None
        style = getattr(pipeline.project, 'style', 'unknown')
        print(f"[렌더링] 스타일: {style}, 선택된 BGM: {selected_bgm}, 볼륨: {bgm_volume}")

        if selected_bgm and not selected_bgm.startswith("("):
            bgm_folder = BGM_CONFIG.get("folder", "assets/bgm")
            bgm_path = os.path.join(bgm_folder, selected_bgm)
            print(f"[렌더링] BGM 경로: {bgm_path}, 존재: {os.path.exists(bgm_path)}")
            if not os.path.exists(bgm_path):
                print(f"[렌더링] ⚠️ BGM 파일 없음! 경로: {bgm_path}")
                bgm_path = None
        else:
            print(f"[렌더링] BGM 미선택 (selected_bgm={selected_bgm})")

        video_path = pipeline.step6_render_video(
            use_ken_burns,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume
        )

        if bgm_path:
            bgm_status = f" + BGM: {selected_bgm} (볼륨 {int(bgm_volume*100)}%)"
        else:
            bgm_status = " (BGM 없음 - 드롭다운에서 선택하세요)"
        return f"✅ 렌더링 완료{bgm_status}", video_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def finalize_video():
    if not pipeline.project or not pipeline.project.video_path:
        return "❌ 렌더링 필요", None
    try:
        # 자막이 없으면 자동 생성
        if not pipeline.project.subtitle_path:
            print("[finalize_video] 자막 없음 - 자동 생성 중...")
            pipeline.step5_generate_subtitles(use_whisper=False)

        final_path = pipeline.step7_burn_subtitles()
        # 프로젝트 자동 저장
        pipeline.save_project()
        return "✅ 최종 영상 완료!", final_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# 트렌드 분석 (참고용)
# ═══════════════════════════════════════════════════════════════

def analyze_trend(keyword: str):
    if not keyword.strip():
        return "❌ 키워드 입력 필요", "", []
    try:
        videos = pipeline.step1_analyze_trend(keyword)
        result = "## 🔥 인기 영상\n\n"
        choices = []
        for i, v in enumerate(videos[:10], 1):
            result += f"**{i}. {v.title}**\n"
            result += f"- 조회수: {v.view_count:,} | 댓글: {v.comment_count:,}\n\n"
            choices.append(f"{i}. {v.title[:40]}... ({v.video_id})")
        return "✅ 분석 완료", result, gr.update(choices=choices, value=None)
    except Exception as e:
        return f"❌ 오류: {e}", "", []


def extract_transcript_and_comments(selection: str):
    if not selection:
        return "❌ 영상을 선택해주세요", "", ""
    try:
        video_id = selection.split("(")[-1].replace(")", "").strip()
    except:
        return "❌ 영상 ID 파싱 실패", "", ""

    transcript_text = ""
    comments_text = ""
    status_msg = []

    try:
        data = pipeline.step1b_extract_transcript(video_id)
        transcript_text = data["transcript"].original_text
        status_msg.append(f"✅ 자막: {len(transcript_text)}자")
    except Exception as e:
        if "disabled" in str(e).lower():
            transcript_text = "[자막 비활성화됨]"
            status_msg.append("⚠️ 자막 없음")
        else:
            status_msg.append("❌ 자막 실패")

    try:
        from engines.trend_engine import TrendEngine
        trend_engine = TrendEngine()
        comments = trend_engine.get_top_comments(video_id, max_results=15)
        if comments:
            comments_text = "## 💬 인기 댓글\n\n"
            for i, c in enumerate(comments[:10], 1):
                text = c.get("text", "").replace("\n", " ")[:150]
                comments_text += f"**{i}.** 👍{c.get('like_count', 0)} {text}\n\n"
            status_msg.append(f"✅ 댓글: {len(comments)}개")
    except:
        status_msg.append("❌ 댓글 실패")

    return " | ".join(status_msg), transcript_text, comments_text


# ═══════════════════════════════════════════════════════════════
# 썸네일 생성
# ═══════════════════════════════════════════════════════════════

def get_background_images():
    """프로젝트 이미지 목록 가져오기"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return []
    return pipeline.project.cut_paths


def generate_thumbnail(
    bg_image,
    main_text: str,
    sub_text: str,
    bottom_text: str,
    darken: float
):
    """썸네일 생성"""
    if not main_text.strip():
        return "❌ 메인 텍스트를 입력하세요", None

    # 배경 이미지 결정
    if bg_image is not None:
        # 업로드된 이미지 사용
        bg_path = bg_image
    elif pipeline.project and pipeline.project.cut_paths:
        # 프로젝트 첫 번째 이미지
        bg_path = pipeline.project.cut_paths[0]
    else:
        return "❌ 배경 이미지를 업로드하거나 이미지를 먼저 생성하세요", None

    try:
        style = getattr(pipeline.project, 'style', '불교강의') if pipeline.project else '불교강의'
        language = getattr(pipeline.project, 'language', 'ko') if pipeline.project else 'ko'

        # 출력 경로
        if pipeline.project:
            output_path = pipeline._get_path("thumbnail.jpg")
        else:
            output_path = "thumbnail_output.jpg"

        thumbnail_path = thumbnail_engine.create_thumbnail(
            background_image=bg_path,
            main_text=main_text,
            sub_text=sub_text,
            bottom_text=bottom_text,
            style=style,
            darken=darken,
            output_path=output_path,
            language=language
        )

        return f"✅ 썸네일 생성 완료!", thumbnail_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def use_project_image(img_index: int):
    """프로젝트 이미지 선택"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return None
    if 0 <= img_index < len(pipeline.project.cut_paths):
        return pipeline.project.cut_paths[img_index]
    return None


def get_thumbnail_gallery_images():
    """썸네일용 이미지 갤러리 가져오기"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return []
    return pipeline.project.cut_paths


def generate_thumbnail_texts():
    """AI 생성 썸네일 텍스트 가져오기 (상단/메인 분리)"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 프로젝트/스크립트 없음", "", "", ""

    # AI 생성 메타데이터가 있으면 사용
    youtube_metadata = getattr(pipeline.project, 'youtube_metadata', None)
    if youtube_metadata:
        # 새 필드 우선 사용 (thumbnail_top_text, thumbnail_main_text)
        top_text = youtube_metadata.get("thumbnail_top_text", "")
        main_text = youtube_metadata.get("thumbnail_main_text", "")

        # 새 필드가 없으면 레거시 필드 사용
        if not top_text and not main_text:
            legacy_text = youtube_metadata.get("thumbnail_text", "")
            if legacy_text:
                parts = legacy_text.replace("\\n", "\n").split("\n", 1)
                if len(parts) >= 2:
                    top_text = parts[0]
                    main_text = parts[1]
                else:
                    main_text = parts[0]

        # 줄바꿈 처리
        top_text = top_text.replace("\\n", "\n")
        main_text = main_text.replace("\\n", "\n")

        if top_text or main_text:
            return "✅ AI 생성 썸네일 텍스트 적용!", top_text, main_text, ""

    # AI 메타데이터 없으면 기존 방식으로 생성
    script = pipeline.project.script
    title = script.title or ""
    style = getattr(pipeline.project, 'style', '불교강의')

    # 스타일별 텍스트 생성
    if style == "불교명상":
        sub_text = "수면 명상"
        if len(title) > 20:
            main_text = title[:20] + "..."
        else:
            main_text = title
        bottom_text = "깊은 잠으로"
    elif style == "불교강의":
        sub_text = "함께 읽는"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = "마음의 여운"
    elif "스토리텔링" in style:
        sub_text = "그날 밤"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = ""
    elif style == "일본텔링":
        # 일본어 썸네일 텍스트
        sub_text = "心の処方箋"
        main_text = title[:20] if len(title) > 20 else title
        bottom_text = ""
    elif style == "영어Saying전용":
        # 영어 썸네일 텍스트
        sub_text = "PRAY THIS"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = ""
    else:  # 기본 스타일
        sub_text = "함께 읽는"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = "마음의 여운"

    return "✅ 텍스트 생성 완료!", sub_text, main_text, bottom_text


def on_gallery_select(evt: gr.SelectData):
    """갤러리에서 이미지 선택 시"""
    if not pipeline.project or not pipeline.project.cut_paths:
        return None, "❌ 이미지 없음"

    idx = evt.index
    if 0 <= idx < len(pipeline.project.cut_paths):
        selected_path = pipeline.project.cut_paths[idx]
        return selected_path, f"✅ 이미지 {idx + 1} 선택됨"
    return None, "❌ 선택 오류"


def preview_thumbnail(bg_path, main_text, sub_text, bottom_text, darken):
    """썸네일 미리보기 생성"""
    if not bg_path:
        return "❌ 배경 이미지를 선택하세요", None
    if not main_text.strip():
        return "❌ 메인 텍스트를 입력하세요", None

    try:
        style = getattr(pipeline.project, 'style', '불교강의') if pipeline.project else '불교강의'
        language = getattr(pipeline.project, 'language', 'ko') if pipeline.project else 'ko'

        # 미리보기 경로 (임시)
        if pipeline.project:
            preview_path = pipeline._get_path("thumbnail_preview.jpg")
        else:
            preview_path = "thumbnail_preview.jpg"

        thumbnail_path = thumbnail_engine.create_thumbnail(
            background_image=bg_path,
            main_text=main_text,
            sub_text=sub_text,
            bottom_text=bottom_text,
            style=style,
            darken=darken,
            output_path=preview_path,
            language=language
        )

        return "👁️ 미리보기 생성됨 (확정하려면 '✅ 확정' 버튼 클릭)", thumbnail_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def confirm_thumbnail(bg_path, main_text, sub_text, bottom_text, darken):
    """썸네일 확정 저장"""
    if not bg_path:
        return "❌ 배경 이미지를 선택하세요", None, None
    if not main_text.strip():
        return "❌ 메인 텍스트를 입력하세요", None, None

    try:
        style = getattr(pipeline.project, 'style', '불교강의') if pipeline.project else '불교강의'
        language = getattr(pipeline.project, 'language', 'ko') if pipeline.project else 'ko'

        # 최종 경로
        if pipeline.project:
            output_path = pipeline._get_path("thumbnail.jpg")
        else:
            output_path = "thumbnail_output.jpg"

        thumbnail_path = thumbnail_engine.create_thumbnail(
            background_image=bg_path,
            main_text=main_text,
            sub_text=sub_text,
            bottom_text=bottom_text,
            style=style,
            darken=darken,
            output_path=output_path,
            language=language
        )

        return f"✅ 썸네일 확정 저장: {output_path}", thumbnail_path, thumbnail_path
    except Exception as e:
        return f"❌ 오류: {e}", None, None


def reset_thumbnail():
    """썸네일 설정 리셋"""
    return None, "", "", "", 0.4, None, "🔄 리셋 완료 - 이미지를 다시 선택하세요"


def reset_project():
    """새 프로젝트 시작 - 전체 상태 초기화"""
    global pipeline
    pipeline = Pipeline()  # 새 파이프라인 인스턴스

    return (
        "🔄 새 프로젝트 시작! 주제를 입력하세요.",  # status
        "",  # topic_input
        10,  # duration_input
        "불교강의",  # style_input
        STYLE_GUIDES["불교강의"],  # style_guide
        "ko",  # script_language (한국어 기본값)
        "*주제를 입력하고 생성 버튼을 누르세요*",  # script_preview
        "",  # image_prompts
        "",  # yt_title_input
        "",  # yt_thumbnail_input
        None,  # audio_preview
        "*TTS 엔진 선택 후 '대사 미리보기' 클릭*",  # tts_script_preview
        [],  # images_gallery
        "",  # subtitle_preview
        None,  # video_preview
        None,  # final_video
        "",  # final_prompts (Tab 3)
    )


# ═══════════════════════════════════════════════════════════════
# YouTube 업로드
# ═══════════════════════════════════════════════════════════════

# YouTube 업로드 엔진 인스턴스 (언어별)
youtube_engines = {}


def get_youtube_engine(language: str = "ko"):
    """YouTube 엔진 (언어별 인스턴스)"""
    global youtube_engines
    if language not in youtube_engines:
        from engines.youtube_upload_engine import YouTubeUploadEngine
        youtube_engines[language] = YouTubeUploadEngine(language=language)
    return youtube_engines[language]


def reset_youtube_engine(language: str = "ko"):
    """YouTube 엔진 리셋 (재인증용)"""
    global youtube_engines
    if language in youtube_engines:
        del youtube_engines[language]


def check_youtube_auth(language: str = "ko"):
    """YouTube 인증 상태 확인 (언어별)"""
    lang_names = {"ko": "🇰🇷 한국어", "ja": "🇯🇵 일본어", "en": "🇺🇸 영어"}

    try:
        engine = get_youtube_engine(language)
        status = engine.check_auth_status()

        if not status["has_client_secrets"]:
            return (
                "⚠️ **인증 필요**: `client_secrets.json` 파일이 없습니다.",
                "### 설정 방법\n"
                "1. [Google Cloud Console](https://console.cloud.google.com) 접속\n"
                "2. YouTube Data API v3 활성화\n"
                "3. OAuth 클라이언트 ID 생성 (데스크톱 앱)\n"
                "4. JSON 다운로드 → `client_secrets.json`으로 저장",
                gr.update(interactive=False),
            )

        if status["authenticated"] and status["channel"]:
            channel = status["channel"]
            return (
                f"✅ **{lang_names.get(language, language)} 채널 연결됨**",
                f"### 📺 현재 연결된 채널\n"
                f"## 🎬 {channel['title']}\n"
                f"- **구독자**: {channel['subscribers']}명\n"
                f"- **영상 수**: {channel['videos']}개\n\n"
                f"⚠️ 다른 채널에 올리려면 **다른 채널로 변경** 버튼 클릭!",
                gr.update(interactive=True),
            )
        else:
            return (
                f"🔐 **{lang_names.get(language, language)} 채널 미연결**: 아래에서 인증하세요",
                f"**{lang_names.get(language, language)}** 채널에 업로드하려면 인증이 필요합니다.\n"
                "해당 언어 채널의 Google 계정으로 로그인하세요.",
                gr.update(interactive=False),
            )

    except Exception as e:
        return (
            f"❌ 오류: {e}",
            "",
            gr.update(interactive=False),
        )


def check_all_youtube_channels():
    """모든 언어의 YouTube 채널 상태 확인"""
    from engines.youtube_upload_engine import YouTubeUploadEngine
    lang_names = {"ko": "🇰🇷 한국어", "ja": "🇯🇵 일본어", "en": "🇺🇸 영어"}

    try:
        all_status = YouTubeUploadEngine.get_all_channels_status()

        lines = ["### 📺 채널 연결 상태"]
        any_connected = False

        for lang, status in all_status.items():
            if status["authenticated"] and status["channel"]:
                lines.append(f"- {lang_names.get(lang, lang)}: ✅ **{status['channel']['title']}**")
                any_connected = True
            else:
                lines.append(f"- {lang_names.get(lang, lang)}: ⚪ 미연결")

        return "\n".join(lines), gr.update(interactive=any_connected)

    except Exception as e:
        return f"❌ 오류: {e}", gr.update(interactive=False)


def authenticate_youtube(language: str = "ko"):
    """YouTube 인증 수행 (언어별, 진행 상태 표시)"""
    lang_names = {"ko": "🇰🇷 한국어", "ja": "🇯🇵 일본어", "en": "🇺🇸 영어"}
    lang_name = lang_names.get(language, language)

    # 기존 엔진 리셋 (새 인증 강제)
    reset_youtube_engine(language)

    # 즉시 진행 상태 표시
    yield (
        f"🔐 **{lang_name} 채널 인증 중...**",
        f"### ⏳ 인증 진행 중\n**{lang_name}** 채널의 Google 계정으로 로그인하세요.\n\n브라우저 창에서 로그인 후 완료될 때까지 기다려주세요...",
        gr.update(interactive=False),
    )

    try:
        engine = get_youtube_engine(language)
        engine.authenticate()
        channel = engine.get_channel_info()

        if channel:
            yield (
                f"✅ **{lang_name} 채널 연결 완료!** {channel['title']}",
                f"### 📺 {lang_name} 채널 정보\n"
                f"- **채널명**: {channel['title']}\n"
                f"- **구독자**: {channel['subscribers']}\n"
                f"- **영상 수**: {channel['videos']}개",
                gr.update(interactive=True),
            )
        else:
            yield (
                "⚠️ 채널 정보를 가져올 수 없습니다",
                "",
                gr.update(interactive=False),
            )

    except FileNotFoundError as e:
        yield (
            f"❌ {e}",
            "### 설정 방법\n"
            "1. [Google Cloud Console](https://console.cloud.google.com) 접속\n"
            "2. YouTube Data API v3 활성화\n"
            "3. OAuth 클라이언트 ID 생성\n"
            "4. JSON 다운로드 → `client_secrets.json`으로 저장",
            gr.update(interactive=False),
        )
    except Exception as e:
        yield (
            f"❌ 인증 실패: {e}",
            "",
            gr.update(interactive=False),
        )


def change_youtube_channel(language: str = "ko"):
    """YouTube 채널 변경 (기존 연결 해제 후 새로 인증)"""
    lang_names = {"ko": "🇰🇷 한국어", "ja": "🇯🇵 일본어", "en": "🇺🇸 영어"}
    lang_name = lang_names.get(language, language)

    # 기존 엔진 리셋
    reset_youtube_engine(language)

    yield (
        f"🔄 **{lang_name} 채널 연결 해제 중...**",
        "기존 연결을 해제하고 새 채널에 연결합니다...",
        gr.update(interactive=False),
    )

    try:
        engine = get_youtube_engine(language)
        # 기존 토큰 삭제
        engine.disconnect_channel()

        yield (
            f"🔐 **{lang_name} 새 채널 인증 중...**",
            "브라우저에서 연결할 Google 계정으로 로그인하세요...",
            gr.update(interactive=False),
        )

        # 새로 인증
        engine.authenticate()
        channel = engine.get_channel_info()

        if channel:
            yield (
                f"✅ **{lang_name} 채널 변경 완료!**",
                f"### 📺 새로 연결된 채널\n"
                f"- **채널명**: {channel['title']}\n"
                f"- **구독자**: {channel.get('subscribers', '비공개')}명\n"
                f"- **영상 수**: {channel.get('videos', 0)}개\n\n"
                f"이제 이 채널에 업로드할 수 있습니다!",
                gr.update(interactive=True),
            )
        else:
            yield (
                f"⚠️ 채널 정보를 가져올 수 없습니다",
                "",
                gr.update(interactive=False),
            )
    except Exception as e:
        yield (
            f"❌ 채널 변경 실패: {e}",
            "",
            gr.update(interactive=False),
        )


def upload_to_youtube(title: str, description: str, tags: str, privacy: str, language: str = "ko"):
    """YouTube에 영상 업로드 (언어별 채널, 진행 상태 표시)"""
    lang_names = {"ko": "🇰🇷 한국어", "ja": "🇯🇵 일본어", "en": "🇺🇸 영어"}
    lang_name = lang_names.get(language, language)

    if not pipeline.project:
        yield "❌ 프로젝트가 없습니다", ""
        return

    # 영상 파일 확인
    video_path = getattr(pipeline.project, 'final_video_path', None)
    if not video_path:
        video_path = getattr(pipeline.project, 'video_path', None)

    if not video_path or not os.path.exists(video_path):
        yield "❌ 영상 파일이 없습니다. 먼저 영상을 렌더링하세요.", ""
        return

    # 썸네일 확인
    thumbnail_path = pipeline._get_path("thumbnail.jpg")
    if not os.path.exists(thumbnail_path):
        thumbnail_path = None

    # 즉시 진행 상태 표시
    yield f"⏳ **{lang_name} 채널에 업로드 준비 중...**", "YouTube 서버에 연결 중입니다..."

    try:
        engine = get_youtube_engine(language)

        # 공개 상태 매핑
        privacy_map = {
            "비공개": "private",
            "미등록": "unlisted",
            "공개": "public",
        }
        privacy_status = privacy_map.get(privacy, "private")

        # 파일 크기 표시
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        yield f"⏳ **{lang_name} 채널에 업로드 중...** ({file_size_mb:.1f}MB)", f"### 📤 {lang_name} 채널에 업로드 진행 중\n- **파일**: {file_size_mb:.1f}MB\n- **제목**: {title[:50]}...\n\n⏳ 잠시만 기다려주세요..."

        # 업로드 실행
        result = engine.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            thumbnail_path=thumbnail_path,
        )

        # 결과 메시지
        status_korean = {"private": "비공개", "unlisted": "미등록", "public": "공개"}.get(result["status"], result["status"])

        # 썸네일 상태 확인
        thumb_status = "✅"
        thumb_note = ""
        if not result.get("thumbnail_uploaded"):
            thumb_status = "⚠️"
            thumb_error = result.get("thumbnail_error", "")
            if "forbidden" in str(thumb_error).lower():
                thumb_note = "\n\n⚠️ **썸네일 업로드 실패**: YouTube 채널 전화번호 인증이 필요합니다.\n[YouTube 스튜디오 → 설정 → 채널 → 기능 사용 자격 요건](https://studio.youtube.com)"
            elif "존재하지 않음" in str(thumb_error) or "생성되지 않음" in str(thumb_error):
                thumb_note = f"\n\n⚠️ **썸네일 업로드 실패**: 썸네일 이미지가 없습니다.\n업로드 전에 '썸네일 생성' 탭에서 썸네일을 먼저 생성하세요."
            elif thumb_error:
                thumb_note = f"\n\n⚠️ 썸네일 업로드 실패: {thumb_error}"
            else:
                thumb_note = "\n\n⚠️ 썸네일 업로드 실패: 원인을 확인할 수 없습니다."

        yield (
            f"🎉 **{lang_name} 채널에 업로드 완료!**",
            f"### 📺 업로드 결과 ({lang_name})\n"
            f"- **제목**: {result['title']}\n"
            f"- **상태**: {status_korean}\n"
            f"- **썸네일**: {thumb_status}\n"
            f"- **URL**: [{result['video_id']}]({result['url']})\n\n"
            f"👆 링크를 클릭하여 YouTube에서 확인하세요!{thumb_note}",
        )

    except Exception as e:
        yield f"❌ 업로드 실패: {e}", ""


def prepare_youtube_upload(language: str = "ko"):
    """YouTube 업로드용 정보 생성 - 언어별 템플릿 사용"""
    import random
    import re

    def contains_korean(text: str) -> bool:
        """텍스트에 한글이 포함되어 있는지 확인"""
        if not text:
            return False
        return bool(re.search(r'[가-힣]', text))

    def tags_to_hashtags(tags_str: str) -> str:
        """쉼표 구분 태그를 해시태그 형식으로 변환"""
        if not tags_str:
            return ""
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        # 공백 제거하고 해시태그 형식으로
        hashtags = ["#" + t.replace(" ", "") for t in tags[:10]]  # 최대 10개
        return " ".join(hashtags)

    if not pipeline.project:
        return "❌ 프로젝트 없음", "", "", "", "", None, None

    project = pipeline.project
    script = project.script
    style = getattr(project, 'style', '불교강의')

    # 영상 길이 계산 (분)
    duration = getattr(project, 'duration', 10)

    # 언어별 설정 먼저 로드
    if language == "ja":
        desc_templates = YOUTUBE_DESCRIPTION_TEMPLATE_JA
        tags_dict = YOUTUBE_DEFAULT_TAGS_JA
        lang_name = "🇯🇵 日本語"
    elif language == "en":
        desc_templates = YOUTUBE_DESCRIPTION_TEMPLATE_EN
        tags_dict = YOUTUBE_DEFAULT_TAGS_EN
        lang_name = "🇺🇸 English"
    else:  # ko (기본값)
        desc_templates = YOUTUBE_DESCRIPTION_TEMPLATE
        tags_dict = YOUTUBE_DEFAULT_TAGS
        lang_name = "🇰🇷 한국어"

    # AI 생성 메타데이터 확인
    youtube_metadata = getattr(project, 'youtube_metadata', None)

    # 제목 결정 - 언어에 맞는지 확인
    title = None
    if youtube_metadata and youtube_metadata.get("title"):
        ai_title = youtube_metadata["title"]
        # 한국어가 아닌 언어인데 한국어가 포함되면 사용 안 함
        if language != "ko" and contains_korean(ai_title):
            print(f"[YouTube] AI 제목에 한국어 포함 - 기본 제목 사용 (언어: {language})")
            title = None
        else:
            title = ai_title

    if not title:
        # 폴백: 대본 제목 사용 (번역된 대본이면 해당 언어)
        if script and script.title:
            if language != "ko" and contains_korean(script.title):
                # 한국어 제목이면 기본 템플릿 사용
                title_templates = YOUTUBE_TITLE_TEMPLATES.get(style, YOUTUBE_TITLE_TEMPLATES.get("불교강의", []))
                if title_templates:
                    title = random.choice(title_templates).format(duration=duration)
                else:
                    title = f"Buddhist Story {duration}min" if language == "en" else f"仏教物語 {duration}分"
            else:
                title = script.title
        else:
            title = f"Buddhist Story {duration}min" if language == "en" else (f"仏教物語 {duration}分" if language == "ja" else f"불교 이야기 {duration}분")

    # 금지어 체크 및 제거
    for forbidden in YOUTUBE_FORBIDDEN_WORDS:
        if forbidden in title:
            title = title.replace(forbidden, "")

    # 씬 요약 생성 - 언어 확인
    scene_summaries = ""
    if script:
        for i, scene in enumerate(script.scenes[:5], 1):
            scene_title = scene.title
            # 한국어가 아닌 언어인데 씬 제목에 한글이 있으면 번호만 표시
            if language != "ko" and contains_korean(scene_title):
                if language == "ja":
                    scene_summaries += f"📌 パート{i}\n"
                else:
                    scene_summaries += f"📌 Part {i}\n"
            else:
                scene_summaries += f"📌 {scene_title}\n"

    # 설명 생성 - 언어별 템플릿 사용
    desc_template = desc_templates.get(style, desc_templates.get("default", ""))
    description = desc_template.format(
        title=title,
        scene_summaries=scene_summaries
    )

    # 태그 결정 - 언어에 맞는지 확인
    tags = None
    if youtube_metadata and youtube_metadata.get("tags"):
        ai_tags = youtube_metadata["tags"]
        if isinstance(ai_tags, list):
            ai_tags_str = ", ".join(ai_tags)
        else:
            ai_tags_str = ai_tags

        # 한국어가 아닌 언어인데 한국어 태그가 포함되면 기본 태그 사용
        if language != "ko" and contains_korean(ai_tags_str):
            print(f"[YouTube] AI 태그에 한국어 포함 - 기본 태그 사용 (언어: {language})")
            tags = None
        else:
            tags = ai_tags_str

    if not tags:
        # 폴백: 언어별 기본 태그
        tags = tags_dict.get(style, tags_dict.get("불교종교", ""))

    # 해시태그 형식으로 설명에 추가
    hashtags = tags_to_hashtags(tags)
    if hashtags and hashtags not in description:
        description = description.rstrip() + f"\n\n{hashtags}"

    # 파일 경로
    video_path = getattr(project, 'final_video_path', None) or getattr(project, 'video_path', None)
    thumbnail_path = pipeline._get_path("thumbnail.jpg") if os.path.exists(pipeline._get_path("thumbnail.jpg")) else None

    # 언어별 채널 정보 추가
    channel_info = LANGUAGE_CONFIG.get(language, {}).get("youtube_channel", "")

    return (
        f"✅ 업로드 정보 준비 완료 ({lang_name} | {channel_info})",
        title,
        description,
        tags,
        f"📁 {project.project_id}" if project else "",
        video_path,
        thumbnail_path
    )


# ═══════════════════════════════════════════════════════════════
# Gradio UI - 간소화된 버전
# ═══════════════════════════════════════════════════════════════

with gr.Blocks(title="AI 콘텐츠 생성기") as app:
    gr.Markdown("# 🎬 AI 콘텐츠 생성기")
    gr.Markdown("주제 입력 → 스타일 선택 → 스크립트/이미지/영상 자동 생성")

    with gr.Row():
        status = gr.Textbox(label="📊 상태", lines=1, interactive=False, scale=5)
        reset_btn = gr.Button("🔄 새 프로젝트", variant="secondary", scale=1)

    with gr.Tabs():
        # ─────────────────────────────────────────────
        # Tab 1: 스크립트 생성 (통합)
        # ─────────────────────────────────────────────
        with gr.Tab("1️⃣ 스크립트 생성"):
            with gr.Row():
                with gr.Column(scale=1):
                    topic_input = gr.Textbox(
                        label="📝 주제 / 내용",
                        placeholder="짧게: 삶이 힘들 때\n\n또는 길게: 요즘 직장에서 스트레스 받고 집에서도 힘들고 남편은 게임만 하고...\n\n또는 스토리: 어떤 여자가 있었는데 10년간 모은 돈을 사기당해서...",
                        lines=10
                    )

                    with gr.Row():
                        duration_input = gr.Radio(
                            [5, 10, 15, 20],
                            value=10,
                            label="영상 길이 (분)"
                        )

                    style_input = gr.Radio(
                        ["불교강의",
                         "스토리텔링:한국불교", "스토리텔링:중국불교", "스토리텔링:인도불교",
                         "불교명상", "일본텔링", "영어Saying전용", "영어디보셔널", "자유모드"],
                        value="불교강의",
                        label="스타일"
                    )

                    # 불교강의 에피소드 타입 (불교강의 선택시만 표시)
                    episode_type_choices = [
                        (v["name"], k) for k, v in BUDDHIST_LECTURE_EPISODE_TYPES.items()
                    ]
                    episode_type_input = gr.Dropdown(
                        choices=episode_type_choices,
                        value="sutra_origin",
                        label="📚 에피소드 타입 (불교강의 전용)",
                        info="경전/선사일화/논쟁/수행/유물 중 선택",
                        visible=True
                    )

                    # 이미지 스타일 선택 (불교강의/불교명상 전용)
                    image_style_input = gr.Dropdown(
                        choices=[
                            ("🇰🇷 한국불교 (수묵담채)", "korea"),
                            ("🇨🇳 중국불교 (도상화)", "china"),
                            ("🇮🇳 인도불교 (콘셉트아트)", "india"),
                        ],
                        value="korea",
                        label="🎨 이미지 스타일 (불교강의/불교명상 전용)",
                        info="한국: 수묵담채 | 중국: 강렬한 원색 | 인도: 연필 스케치",
                        visible=True
                    )

                    # ═══════════════════════════════════════════════════════════════
                    # 일본텔링 전용 옵션 (일본텔링 선택시만 표시)
                    # ═══════════════════════════════════════════════════════════════
                    japan_series_choices = [
                        (v["name"], k) for k, v in JAPAN_SERIES_CONFIG.items()
                    ]
                    japan_series_input = gr.Dropdown(
                        choices=japan_series_choices,
                        value="senior",
                        label="🇯🇵 시리즈 선택 (일본텔링 전용)",
                        info="Senior(40-70): 따뜻한 안심 톤 | Adult(20-40): 쿨하고 담백",
                        visible=False
                    )

                    japan_twopass_input = gr.Checkbox(
                        label="🔄 2패스 검수 활성화",
                        value=True,
                        info="AI가 생성 후 자체 검수로 금지어/패턴 수정 (일본텔링 전용)",
                        visible=False
                    )

                    # ═══════════════════════════════════════════════════════════════
                    # 영어 디보셔널 전용 옵션 (영어디보셔널 선택시만 표시)
                    # ═══════════════════════════════════════════════════════════════
                    english_prayer_choices = [
                        (v["name"], k) for k, v in ENGLISH_STYLE_CONFIG["prayer_style"].items()
                    ]
                    english_prayer_input = gr.Dropdown(
                        choices=english_prayer_choices,
                        value="gentle",
                        label="🙏 기도 톤 (영어디보셔널 전용)",
                        info="Gentle: 부드럽고 평화로운 | Warfare: 영적 전쟁 스타일",
                        visible=False
                    )

                    english_cta_choices = [
                        (v["name"], k) for k, v in ENGLISH_STYLE_CONFIG["cta_strength"].items()
                    ]
                    english_cta_input = gr.Dropdown(
                        choices=english_cta_choices,
                        value="soft",
                        label="📢 CTA 강도 (영어디보셔널 전용)",
                        info="Soft: 한 줄만 | Medium: 두 줄까지",
                        visible=False
                    )

                    english_twopass_input = gr.Checkbox(
                        label="🔄 2패스 검수 활성화",
                        value=True,
                        info="AI가 생성 후 자체 검수로 클리셰/패턴 수정 (영어디보셔널 전용)",
                        visible=False
                    )

                    def toggle_style_options(style):
                        """스타일에 따라 에피소드 타입과 이미지 스타일 드롭다운 표시/숨김"""
                        show_episode = (style == "불교강의")
                        show_image_style = (style in ("불교강의", "불교명상"))
                        show_japan_options = (style == "일본텔링")
                        show_english_options = (style == "영어디보셔널")
                        return (
                            gr.update(visible=show_episode),
                            gr.update(visible=show_image_style),
                            gr.update(visible=show_japan_options),
                            gr.update(visible=show_japan_options),
                            gr.update(visible=show_english_options),
                            gr.update(visible=show_english_options),
                            gr.update(visible=show_english_options)
                        )

                    style_guide = gr.Markdown(STYLE_GUIDES["불교강의"])

                    # 언어 선택 (스크립트 번역용)
                    gr.Markdown("### 🌍 출력 언어")
                    script_language = gr.Radio(
                        choices=[
                            ("🇰🇷 한국어", "ko"),
                            ("🇯🇵 日本語", "ja"),
                            ("🇺🇸 English", "en"),
                        ],
                        value="ko",
                        label="스크립트 언어",
                        info="한글로 입력 → 선택한 언어로 현지화 번역"
                    )

                    generate_btn = gr.Button("🚀 스크립트 생성", variant="primary", size="lg")

                with gr.Column(scale=2):
                    script_preview = gr.Markdown(label="📖 스크립트", value="*주제를 입력하고 생성 버튼을 누르세요*")

                    gr.Markdown("---")
                    gr.Markdown("### 🎨 이미지 프롬프트")
                    image_prompts = gr.Textbox(
                        label="생성된 이미지 프롬프트 (수정 가능)",
                        lines=10,
                        placeholder="스크립트 생성 후 자동으로 채워집니다"
                    )

                    gr.Markdown("---")
                    gr.Markdown("### 📺 유튜브 제목 / 썸네일 (AI 자동 생성)")
                    with gr.Row():
                        yt_title_input = gr.Textbox(
                            label="📌 유튜브 제목 (수정 가능)",
                            lines=2,
                            placeholder="스크립트 생성 후 AI가 자동으로 제목을 만듭니다"
                        )
                    with gr.Row():
                        yt_thumbnail_input = gr.Textbox(
                            label="🖼️ 썸네일 문구 (수정 가능, 줄바꿈 허용)",
                            lines=2,
                            placeholder="예: 오늘 밤\n꼭 들으세요"
                        )
                    gr.Markdown("*💡 AI가 대본 내용을 분석해 제목과 썸네일을 추천합니다. 직접 수정도 가능합니다.*")

        # ─────────────────────────────────────────────
        # Tab 2: TTS
        # ─────────────────────────────────────────────
        with gr.Tab("2️⃣ TTS") as tts_tab:
            with gr.Row():
                with gr.Column(scale=1):
                    tts_engine = gr.Radio(
                        ["wavenet", "elevenlabs", "elevenlabs2.5", "elevenlabs2.5_limkony", "openai"],
                        value="wavenet",
                        label="TTS 엔진"
                    )
                    tts_speed = gr.Slider(
                        minimum=0.5,
                        maximum=1.5,
                        value=0.9,
                        step=0.05,
                        label="🎚️ 음성 속도 (0.5=느리게, 1.0=보통, 1.5=빠르게)"
                    )
                    gr.Markdown("""
                    **엔진 설명**:
                    - `wavenet`: Google Cloud TTS (자연스러움)
                    - `elevenlabs`: v3 Audio Tags 감정 표현 ⭐
                    - `elevenlabs2.5`: Turbo v2.5 감정 흉내 🚀
                    - `elevenlabs2.5_limkony`: Turbo v2.5 감정 흉내 (limkony) 🔵
                    - `openai`: OpenAI TTS
                    """)
                    # ElevenLabs 사용량 표시 (엔진 설명 아래)
                    elevenlabs_usage_display = gr.Markdown(
                        value="",
                        visible=True
                    )
                    tts_preview_btn = gr.Button("👁️ 대사 미리보기")
                    tts_btn = gr.Button("🔊 TTS 생성", variant="primary")

                with gr.Column(scale=1):
                    audio_preview = gr.Audio(label="생성된 오디오")

            gr.Markdown("---")
            tts_script_preview = gr.Markdown(
                label="TTS 입력 대사",
                value="*TTS 엔진 선택 후 '대사 미리보기' 클릭*"
            )

        # ─────────────────────────────────────────────
        # Tab 3: 이미지 생성
        # ─────────────────────────────────────────────
        with gr.Tab("3️⃣ 이미지 생성"):
            with gr.Row():
                with gr.Column():
                    image_engine = gr.Radio(
                        [
                            ("fal.ai (애니)", "fal-anime"),
                            ("fal.ai (실사)", "fal-realistic"),
                            ("DALL-E", "dalle"),
                            ("Imagen", "imagen"),
                            ("스토리텔링전용", "storymaker"),
                        ],
                        value="fal-anime",
                        label="이미지 엔진"
                    )

                    # 엔진별 모델 선택
                    image_model = gr.Dropdown(
                        label="모델 선택",
                        choices=[
                            ("flux-schnell (빠름/$0.003)", "flux-schnell"),
                            ("flux-dev (균형/$0.025)", "flux-dev"),
                            ("flux-pro (고품질/$0.05)", "flux-pro"),
                            ("flux-pro-v1.1 (최신/$0.05)", "flux-pro-v1.1"),
                            ("flux-ultra (최고품질/$0.06)", "flux-ultra"),
                        ],
                        value="flux-schnell",
                        info="엔진 변경 시 자동 변경됩니다"
                    )

                    final_prompts = gr.Textbox(
                        label="이미지 프롬프트",
                        lines=8,
                        info="Tab 1에서 생성된 프롬프트가 자동으로 복사됩니다"
                    )
                    with gr.Row():
                        gen_images_btn = gr.Button("🎨 이미지 생성", variant="primary")
                        apply_images_btn = gr.Button("📂 현재 그림 적용", variant="secondary")
                    gr.Markdown("*💡 다국어 버전: '현재 그림 적용' 클릭 → 기존 이미지 재사용*", elem_classes="info-text")
                with gr.Column():
                    images_gallery = gr.Gallery(label="생성된 이미지", columns=3)

        # ─────────────────────────────────────────────
        # Tab 4: 영상 렌더링
        # ─────────────────────────────────────────────
        with gr.Tab("4️⃣ 영상"):
            with gr.Row():
                with gr.Column():
                    use_whisper = gr.Checkbox(label="Whisper 자막", value=False)
                    subtitle_btn = gr.Button("📄 자막 생성")

                    gr.Markdown("---")
                    use_ken_burns = gr.Checkbox(label="🎬 이미지 줌 효과 (부드러운 확대/축소)", value=True)

                    gr.Markdown("### 🎵 BGM 선택")
                    with gr.Row():
                        bgm_selector = gr.Dropdown(
                            label="배경음악",
                            choices=["(BGM 없음)"] + get_bgm_list(),
                            value=None,
                            info="assets/bgm 폴더에 mp3/wav 파일 추가"
                        )
                        bgm_refresh_btn = gr.Button("🔄", scale=0)

                    bgm_volume = gr.Slider(
                        minimum=0.0,
                        maximum=0.5,
                        value=0.15,
                        step=0.05,
                        label="🔊 BGM 볼륨",
                        info="TTS 대비 음량 (0.15 권장)"
                    )

                    bgm_preview = gr.Audio(label="🎧 BGM 미리듣기", interactive=False)

                    render_btn = gr.Button("🎬 렌더링", variant="primary")
                    final_btn = gr.Button("✅ 최종 영상", variant="primary")

                with gr.Column():
                    subtitle_preview = gr.Textbox(label="자막 (SRT)", lines=6)
                    video_preview = gr.Video(label="영상")
                    final_video = gr.Video(label="최종 영상")

        # ─────────────────────────────────────────────
        # Tab 5: 썸네일 생성
        # ─────────────────────────────────────────────
        with gr.Tab("5️⃣ 썸네일") as thumb_tab:
            gr.Markdown("### 🖼️ 썸네일 생성")
            gr.Markdown("*이미지 선택 → 텍스트 생성 → 미리보기 → 확정*")

            with gr.Row():
                with gr.Column(scale=1):
                    # 이미지 갤러리
                    gr.Markdown("#### 📸 배경 이미지 선택")
                    thumb_gallery = gr.Gallery(
                        label="클릭해서 배경 선택",
                        columns=4,
                        rows=2,
                        height=200,
                        object_fit="cover",
                        allow_preview=False
                    )
                    thumb_refresh_btn = gr.Button("🔄 이미지 새로고침", size="sm")

                    # 선택된 이미지 경로 (숨김)
                    thumb_selected_path = gr.Textbox(visible=False)

                    gr.Markdown("#### ✏️ 텍스트 설정")
                    thumb_auto_btn = gr.Button("🎯 텍스트 자동 생성", variant="secondary")

                    thumb_sub = gr.Textbox(
                        label="상단 텍스트 (작은 글씨)",
                        placeholder="예: 잠자면서 듣는",
                        lines=1
                    )

                    thumb_main = gr.Textbox(
                        label="메인 텍스트 (큰 글씨) ⭐",
                        placeholder="예: 부처님말씀 2시간",
                        lines=2
                    )

                    thumb_bottom = gr.Textbox(
                        label="하단 텍스트",
                        placeholder="예: 노후에는 다 부질없다",
                        lines=1
                    )

                    thumb_darken = gr.Slider(
                        minimum=0.0,
                        maximum=0.8,
                        value=0.4,
                        step=0.1,
                        label="배경 어둡게"
                    )

                    with gr.Row():
                        thumb_preview_btn = gr.Button("👁️ 미리보기", variant="secondary")
                        thumb_reset_btn = gr.Button("🔄 리셋", variant="secondary")
                        thumb_confirm_btn = gr.Button("✅ 확정", variant="primary")

                with gr.Column(scale=1):
                    thumb_preview = gr.Image(label="썸네일 미리보기", height=400)
                    thumb_download = gr.File(label="📥 다운로드")

        # ─────────────────────────────────────────────
        # Tab 6: YouTube 업로드
        # ─────────────────────────────────────────────
        with gr.Tab("6️⃣ YouTube 업로드") as youtube_tab:
            gr.Markdown("### 📤 YouTube 자동 업로드 (언어별 채널)")

            # 언어 선택 섹션 (먼저 배치)
            gr.Markdown("### 🌍 업로드 채널 선택")
            with gr.Row():
                yt_language = gr.Radio(
                    choices=[
                        ("🇰🇷 한국어", "ko"),
                        ("🇯🇵 日本語", "ja"),
                        ("🇺🇸 English", "en"),
                    ],
                    value="ko",
                    label="업로드 채널",
                    info="각 언어별로 다른 YouTube 채널에 업로드됩니다"
                )

            # 인증 상태 섹션
            with gr.Row():
                with gr.Column(scale=2):
                    yt_auth_status = gr.Markdown("*인증 상태 확인 중...*")
                with gr.Column(scale=1):
                    yt_auth_btn = gr.Button("🔐 선택한 채널 연결", variant="secondary")
                    yt_change_btn = gr.Button("🔄 다른 채널로 변경", variant="stop", size="sm")

            yt_channel_info = gr.Markdown("")

            gr.Markdown("---")

            # 업로드 정보 섹션
            prepare_btn = gr.Button("📋 업로드 정보 준비", variant="secondary")

            with gr.Row():
                with gr.Column():
                    yt_title = gr.Textbox(
                        label="📌 제목",
                        lines=2,
                        interactive=True,
                    )

                    yt_description = gr.Textbox(
                        label="📝 설명",
                        lines=8,
                        interactive=True
                    )

                    yt_tags = gr.Textbox(
                        label="🏷️ 태그",
                        lines=2,
                        interactive=True,
                        info="쉼표로 구분"
                    )

                    with gr.Row():
                        yt_privacy = gr.Radio(
                            ["비공개", "미등록", "공개"],
                            value="비공개",
                            label="🔒 공개 설정",
                            info="비공개로 먼저 올리고 확인 후 공개 권장"
                        )

                    yt_project = gr.Textbox(
                        label="📁 프로젝트",
                        interactive=False
                    )

                with gr.Column():
                    yt_video = gr.Video(label="🎬 영상 파일")
                    yt_thumb = gr.Image(label="🖼️ 썸네일")

            gr.Markdown("---")

            # 업로드 버튼
            with gr.Row():
                yt_upload_btn = gr.Button(
                    "🚀 YouTube 업로드",
                    variant="primary",
                    size="lg",
                    interactive=False,  # 인증 후 활성화
                )

            yt_upload_result = gr.Markdown("")

            gr.Markdown("""
            ---
            ### 💡 사용 방법
            1. **업로드 채널 선택** → 🇰🇷 한국어 / 🇯🇵 일본어 / 🇺🇸 영어 중 선택
            2. **선택한 채널 연결** 클릭 → 해당 언어 채널의 Google 계정으로 로그인
            3. **업로드 정보 준비** 클릭 → 언어별 제목/설명/태그 자동 생성
            4. 필요시 수정 후 **YouTube 업로드** 클릭
            5. 다른 언어 채널에도 업로드하려면 1~4 반복!

            ⚠️ **각 언어 채널마다 별도 인증이 필요합니다**
            """)

        # ─────────────────────────────────────────────
        # Tab 7: 트렌드 분석 (참고용)
        # ─────────────────────────────────────────────
        with gr.Tab("📊 트렌드 (참고)"):
            gr.Markdown("### 🔍 YouTube 트렌드 분석")
            gr.Markdown("*아이디어 참고용 - 인기 영상 검색*")

            with gr.Row():
                with gr.Column(scale=1):
                    trend_keyword = gr.Textbox(label="검색 키워드", placeholder="예: 삶이 힘들 때")
                    trend_btn = gr.Button("🔍 검색", variant="primary")

                    video_selector = gr.Dropdown(label="📺 영상 선택", choices=[], interactive=True)
                    extract_btn = gr.Button("📥 자막/댓글 추출")

                with gr.Column(scale=2):
                    trend_result = gr.Markdown()
                    with gr.Row():
                        transcript_result = gr.Textbox(label="자막", lines=8)
                        comments_result = gr.Markdown(label="댓글")

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 연결
    # ═══════════════════════════════════════════════════════════════

    # 새 프로젝트 리셋
    reset_btn.click(
        reset_project,
        [],
        [
            status,
            topic_input,
            duration_input,
            style_input,
            style_guide,
            script_language,
            script_preview,
            image_prompts,
            yt_title_input,
            yt_thumbnail_input,
            audio_preview,
            tts_script_preview,
            images_gallery,
            subtitle_preview,
            video_preview,
            final_video,
            final_prompts,
        ]
    )

    # 스타일 변경시 가이드 업데이트 + 에피소드 타입 토글
    style_input.change(update_style_guide, [style_input], [style_guide])
    style_input.change(toggle_style_options, [style_input], [episode_type_input, image_style_input, japan_series_input, japan_twopass_input, english_prayer_input, english_cta_input, english_twopass_input])

    # Tab 1: 스크립트 생성 + AI 제목/썸네일 (언어 파라미터 + 에피소드 타입 + 일본텔링/영어디보셔널 옵션 추가)
    generate_btn.click(
        generate_script_and_images,
        [topic_input, duration_input, style_input, script_language, episode_type_input, japan_series_input, japan_twopass_input, english_prayer_input, english_cta_input, english_twopass_input],
        [status, script_preview, image_prompts, yt_title_input, yt_thumbnail_input]
    )

    # 이미지 프롬프트 자동 복사
    image_prompts.change(lambda x: x, [image_prompts], [final_prompts])

    # Tab 2: TTS
    # 탭 선택 시 ElevenLabs 사용량 로드
    tts_tab.select(get_elevenlabs_usage_info, [], [elevenlabs_usage_display])
    tts_preview_btn.click(preview_tts_script, [tts_engine], [tts_script_preview])
    tts_btn.click(generate_tts, [tts_engine, tts_speed, script_language], [status, audio_preview, tts_script_preview])

    # Tab 3: 이미지 생성
    image_engine.change(update_model_choices, [image_engine], [image_model])
    gen_images_btn.click(
        generate_images_from_text,
        [final_prompts, image_engine, image_model, style_input, image_style_input],
        [status, images_gallery]
    )
    apply_images_btn.click(
        apply_existing_images,
        [],
        [status, images_gallery]
    )

    # Tab 4: 영상
    subtitle_btn.click(generate_subtitles, [use_whisper], [status, subtitle_preview])

    # BGM 관련 이벤트
    bgm_refresh_btn.click(refresh_bgm_list, [], [bgm_selector, bgm_preview])
    bgm_selector.change(preview_bgm, [bgm_selector], [bgm_preview])

    render_btn.click(render_video, [use_ken_burns, bgm_selector, bgm_volume], [status, video_preview])
    final_btn.click(finalize_video, [], [status, final_video])

    # Tab 5: 썸네일
    # 탭 선택시 갤러리 자동 로드
    thumb_tab.select(
        get_thumbnail_gallery_images,
        [],
        [thumb_gallery]
    )

    # 갤러리 새로고침
    thumb_refresh_btn.click(
        get_thumbnail_gallery_images,
        [],
        [thumb_gallery]
    )

    # 갤러리에서 이미지 선택
    thumb_gallery.select(
        on_gallery_select,
        [],
        [thumb_selected_path, status]
    )

    # 텍스트 자동 생성
    thumb_auto_btn.click(
        generate_thumbnail_texts,
        [],
        [status, thumb_sub, thumb_main, thumb_bottom]
    )

    # 미리보기
    thumb_preview_btn.click(
        preview_thumbnail,
        [thumb_selected_path, thumb_main, thumb_sub, thumb_bottom, thumb_darken],
        [status, thumb_preview]
    )

    # 리셋
    thumb_reset_btn.click(
        reset_thumbnail,
        [],
        [thumb_selected_path, thumb_sub, thumb_main, thumb_bottom, thumb_darken, thumb_preview, status]
    )

    # 확정
    thumb_confirm_btn.click(
        confirm_thumbnail,
        [thumb_selected_path, thumb_main, thumb_sub, thumb_bottom, thumb_darken],
        [status, thumb_preview, thumb_download]
    )

    # Tab 6: YouTube 업로드
    # 탭 선택 시 인증 상태 확인 (선택된 언어 기준)
    youtube_tab.select(
        check_youtube_auth,
        [yt_language],
        [yt_auth_status, yt_channel_info, yt_upload_btn]
    )

    # 언어 선택 변경 시 인증 상태 갱신
    yt_language.change(
        check_youtube_auth,
        [yt_language],
        [yt_auth_status, yt_channel_info, yt_upload_btn]
    )

    # 인증 버튼 (선택된 언어 채널 인증)
    yt_auth_btn.click(
        authenticate_youtube,
        [yt_language],
        [yt_auth_status, yt_channel_info, yt_upload_btn]
    )

    # 채널 변경 버튼 (다른 채널로 연결)
    yt_change_btn.click(
        change_youtube_channel,
        [yt_language],
        [yt_auth_status, yt_channel_info, yt_upload_btn]
    )

    # 업로드 정보 준비 (언어 파라미터 전달)
    prepare_btn.click(
        prepare_youtube_upload,
        [yt_language],
        [status, yt_title, yt_description, yt_tags, yt_project, yt_video, yt_thumb]
    )

    # 업로드 실행 (선택된 언어 채널로 업로드)
    yt_upload_btn.click(
        upload_to_youtube,
        [yt_title, yt_description, yt_tags, yt_privacy, yt_language],
        [status, yt_upload_result]
    )


    # Tab 7: 트렌드
    trend_btn.click(analyze_trend, [trend_keyword], [status, trend_result, video_selector])
    extract_btn.click(extract_transcript_and_comments, [video_selector], [status, transcript_result, comments_result])


if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_SERVER_PORT", 7861))
    app.launch(server_name="0.0.0.0", server_port=port, share=False)
