"""
Gradio UI - AI 콘텐츠 생성기
스타일: 뉴스/정보/스토리텔링/불교명상
"""
import os
from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from PIL import Image
import json

from pipeline import Pipeline
from engines import ScriptEngine, ImageEngine
from engines.thumbnail_engine import ThumbnailEngine
from styles import STYLE_PROMPTS  # 스타일별 프롬프트 (파일 분리됨)
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

## 이미지 프롬프트 규칙
- 영어로 작성
- 400자 이내
- 구체적인 시각적 묘사 (조명, 색감, 구도)
- 씬당 1~4개 (중요도에 따라)
- 전체 이미지 총합: {duration}분 영상 기준 약 {total_images}장"""

# 스타일별 이미지 스타일 가이드
STYLE_IMAGE_GUIDES = {
    "뉴스": "Professional news broadcast style, clean composition, neutral lighting",
    "정보": "Bright, friendly infographic style, clear visuals, warm colors",
    "스토리텔링": "Dark mysterious atmosphere, dramatic lighting, suspenseful mood, shadows",
    "스토리텔링:한국불교": "classical Korean ink-wash narrative painting, Joseon dynasty landscape painting style, soft mineral colors, traditional hanok and village scenery, wide negative space, storytelling composition, gentle brush texture, hand-painted feeling, no anime, no modern illustration, no bright digital colors, no cartoon style",
    "스토리텔링:중국불교": "buddhist icon narrative painting, flat symbolic composition, traditional temple painting style, strong primary colors, no perspective realism, spiritual sacred mood, storytelling iconography, no anime, no modern illustration",
    "스토리텔링:인도불교": "narrative concept art illustration, soft pencil sketch, desaturated muted colors, low contrast shading, wide negative space, storyboard composition, no cute, no anime gloss, no bright color",
    "불교명상": "Serene meditation style, golden dawn light, lotus flowers, misty mountains, peaceful temple, soft glow, silhouette meditation pose"
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
    "뉴스": "**💡 뉴스**: 사실 기반 내용을 입력하세요.",
    "정보": "**💡 정보**: 설명할 주제를 입력하세요. (예: 항산화 물질 5가지)",
    "스토리텔링": "**💡 스토리텔링**: 역사/종교/흥미로운 이야기 주제를 입력하세요.",
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
    "불교명상": """**💡 불교명상**: '사람의 상태'로 입력하세요!

❌ 불교 업보, 기도하면 돈 벌까
✅ 삶이 힘들 때, 돈이 안 풀릴 때, 관계가 자꾸 깨질 때

**감정 코드**: 불안 / 죄책감 / 후회 / 구원욕구 / 희망 / 분노 / 고립"""
}

def update_style_guide(style: str):
    return STYLE_GUIDES.get(style, STYLE_GUIDES["정보"])


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


# ═══════════════════════════════════════════════════════════════
# 통합 스크립트 + 이미지 프롬프트 생성
# ═══════════════════════════════════════════════════════════════

def generate_script_and_images(topic: str, duration: int, style: str, language: str = "ko"):
    """주제 입력 → 스크립트 + 이미지 프롬프트 한번에 생성"""
    if not topic.strip():
        return "❌ 주제를 입력해주세요", "", ""

    try:
        # 프로젝트 생성 (스타일 저장)
        project = pipeline.create_project(topic, duration)
        project.style = style  # 스타일 저장

        # 분량에 따른 이미지 수 계산
        total_images = duration * 2  # 분당 약 2장

        # 스타일별 프롬프트 구성
        base_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS["정보"])
        image_style = STYLE_IMAGE_GUIDES.get(style, "")

        prompt = base_prompt.format(topic=topic, duration=duration)
        prompt += INTEGRATED_OUTPUT_FORMAT.format(duration=duration, total_images=total_images)
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

        # JSON 파싱
        try:
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                json_str = result_text[start:end]
            else:
                json_str = result_text

            data = json.loads(json_str)

            # 이미지 프롬프트 먼저 추출 (번역 전에)
            all_image_prompts = []
            for s in data["scenes"]:
                image_prompts = s.get("image_prompts", [])
                all_image_prompts.extend(image_prompts)

            # 번역 (한국어가 아닌 경우)
            lang_info = LANGUAGE_CONFIG.get(language, {})
            lang_name = lang_info.get("name", "🇰🇷 한국어")

            if language != "ko":
                print(f"[번역] {lang_name}로 현지화 중...")
                data = translate_script_to_language(data, language)

            # 언어 설정 저장
            pipeline.project.language = language

            # Script 객체 생성
            from models.types import Script, Scene
            scenes = []

            for i, s in enumerate(data["scenes"]):
                original_prompts = data["scenes"][i].get("image_prompts", []) if i < len(data["scenes"]) else []

                scenes.append(Scene(
                    scene_id=s["scene_id"],
                    title=s["title"],
                    text=s["text"],
                    image_count=len(original_prompts) if original_prompts else 0,
                    importance=s.get("importance", 3)
                ))

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
        return f"❌ 오류: {e}", "", "", "", ""


# ═══════════════════════════════════════════════════════════════
# TTS 생성
# ═══════════════════════════════════════════════════════════════

def get_elevenlabs_usage_info():
    """ElevenLabs 사용량 정보 가져오기"""
    try:
        from engines.tts_engine import TTSEngine
        tts = TTSEngine(engine="elevenlabs", style=None)
        usage = tts.get_elevenlabs_usage()
        if usage:
            return (
                f"📊 **ElevenLabs 사용량**: "
                f"{usage['used']:,} / {usage['limit']:,} 문자 "
                f"({usage['percent']}%) | "
                f"리셋: {usage['reset_date']} | "
                f"플랜: {usage['tier']}"
            )
        else:
            print("[ElevenLabs] usage 반환값 없음")
            return ""
    except Exception as e:
        print(f"[ElevenLabs] 사용량 조회 오류: {e}")
        return f"⚠️ ElevenLabs 사용량 조회 실패: {e}"


def preview_tts_script(engine: str):
    """TTS에 입력될 대사 미리보기"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트를 먼저 생성하세요"

    script = pipeline.project.script
    style = getattr(pipeline.project, 'style', None)
    total_scenes = len(script.scenes)

    # ElevenLabs 사용량 표시
    usage_info = ""
    if engine in ("elevenlabs", "elevenlabs2.5"):
        usage_info = get_elevenlabs_usage_info()
        if usage_info:
            usage_info = f"\n\n{usage_info}\n\n---\n"

    # EMOTION_TAGS 가져오기
    from config import EMOTION_TAGS
    from engines.tts_engine import STYLE_DEFAULT_EMOTIONS_V25

    preview = f"## 🎙️ TTS 입력 대사 미리보기\n"
    preview += f"**엔진**: {engine} | **스타일**: {style or '없음'} | **씬**: {total_scenes}개\n"
    if usage_info:
        preview += usage_info
    preview += "\n---\n\n"

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
        # ElevenLabs Turbo v2.5 감정 흉내 표시
        elif engine == "elevenlabs2.5" and style and style in STYLE_DEFAULT_EMOTIONS_V25:
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

        preview += f"### 씬 {scene.scene_id}: {scene.title}\n"
        if tag:
            preview += f"🎭 **감정태그 (v3)**: `{tag}`\n\n"
            preview += f"```\n{tag} {scene.text}\n```\n\n"
        elif emotion_info:
            preview += f"🎭 **감정흉내 (v2.5)**: `{emotion_info}` → voice_settings 자동 조정\n\n"
            preview += f"```\n{scene.text}\n```\n\n"
        else:
            preview += f"```\n{scene.text}\n```\n\n"

    return preview


def generate_tts(engine: str, speed: float = 0.9):
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트 생성 필요", None, ""
    try:
        # 프로젝트에 저장된 스타일과 언어 가져오기
        style = getattr(pipeline.project, 'style', None)
        language = getattr(pipeline.project, 'language', 'ko')
        lang_name = LANGUAGE_CONFIG.get(language, {}).get("name", "🇰🇷 한국어")

        audio_path = pipeline.step3_generate_tts(engine, style=style, speed=speed)
        total = sum(s.duration for s in pipeline.project.audio_segments)

        # TTS 입력 대사 로그
        tts_log = preview_tts_script(engine)

        # ElevenLabs 사용량 표시
        usage_info = ""
        if engine in ("elevenlabs", "elevenlabs2.5"):
            from engines.tts_engine import TTSEngine
            tts = TTSEngine(engine=engine, style=style, language=language)
            usage = tts.get_elevenlabs_usage()
            if usage:
                model_name = "v3" if engine == "elevenlabs" else "Turbo v2.5"
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


def generate_images_from_text(prompts_text: str, engine: str, model: str, style: str = "정보"):
    if not pipeline.project:
        return "❌ 스크립트 먼저 생성하세요", []
    try:
        prompts = parse_image_prompts(prompts_text)
        if not prompts:
            return "❌ 프롬프트 파싱 실패", []

        # 스토리텔링 스타일일 때 StoryMaker 설정 전달
        storymaker_config = None
        if style in STYLE_TO_STORYMAKER:
            storymaker_config = STYLE_TO_STORYMAKER[style]
            print(f"[App] 스토리텔링 스타일 감지: {style} → {storymaker_config}")

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


# 엔진별 모델 옵션
IMAGE_MODEL_OPTIONS = {
    "fal": [
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
        ("GPT Image (스토리텔링전용)", "gpt-image-1"),
    ],
}


def update_model_choices(engine: str):
    """엔진 변경시 모델 선택 옵션 업데이트"""
    choices = IMAGE_MODEL_OPTIONS.get(engine, IMAGE_MODEL_OPTIONS["fal"])
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
        if selected_bgm and not selected_bgm.startswith("("):
            bgm_folder = BGM_CONFIG.get("folder", "assets/bgm")
            bgm_path = os.path.join(bgm_folder, selected_bgm)
            if not os.path.exists(bgm_path):
                bgm_path = None

        video_path = pipeline.step6_render_video(
            use_ken_burns,
            bgm_path=bgm_path,
            bgm_volume=bgm_volume
        )

        bgm_status = f" + BGM: {selected_bgm} (볼륨 {int(bgm_volume*100)}%)" if bgm_path else ""
        return f"✅ 렌더링 완료{bgm_status}", video_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def finalize_video():
    if not pipeline.project or not pipeline.project.video_path:
        return "❌ 렌더링 필요", None
    try:
        final_path = pipeline.step7_burn_subtitles()
        # 프로젝트 자동 저장
        pipeline.save_project()
        return "✅ 최종 영상 완료!", final_path
    except Exception as e:
        return f"❌ 오류: {e}", None


# ═══════════════════════════════════════════════════════════════
# 프로젝트 재활용 (다른 채널용)
# ═══════════════════════════════════════════════════════════════

def get_project_list():
    """저장된 프로젝트 목록 가져오기"""
    try:
        projects = pipeline.list_projects()
        if not projects:
            return [["(저장된 프로젝트 없음)", "", 0, "", "", ""]]

        data = []
        for p in projects:
            data.append([
                p["project_id"],
                p["title"][:30] + "..." if len(p["title"]) > 30 else p["title"],
                p["duration_min"],
                "✅" if p["has_images"] else "❌",
                "✅" if p["has_audio"] else "❌",
                "✅" if p["has_video"] else "❌",
            ])
        return data
    except Exception as e:
        return [[f"오류: {e}", "", 0, "", "", ""]]


def on_project_select(evt: gr.SelectData, data):
    """테이블에서 프로젝트 선택 시 ID 자동 입력"""
    try:
        if evt.index is not None and data is not None:
            row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            # pandas DataFrame인 경우
            if hasattr(data, 'iloc'):
                project_id = data.iloc[row_idx, 0]
            # 리스트인 경우
            elif isinstance(data, list) and row_idx < len(data):
                project_id = data[row_idx][0]
            else:
                return ""

            if project_id and not str(project_id).startswith("("):
                return str(project_id)
    except Exception as e:
        print(f"[on_project_select] Error: {e}")
    return ""


def load_selected_project(project_id: str):
    """선택한 프로젝트 불러오기 - 모든 탭 UI 업데이트"""
    if not project_id or project_id.startswith("("):
        return (
            "❌ 프로젝트 ID를 입력하세요",  # loaded_project_info
            "",  # status
            "*주제를 입력하고 생성 버튼을 누르세요*",  # script_preview
            "",  # image_prompts
            "",  # final_prompts
            None,  # audio_preview
            [],  # images_gallery
            "",  # subtitle_preview
            None,  # video_preview
            None,  # final_video
        )

    try:
        # project.json 있는지 확인
        project_path = os.path.join(pipeline.project_dir, project_id)
        json_path = os.path.join(project_path, "project.json")

        if os.path.exists(json_path):
            project = pipeline.load_project(project_id)
        else:
            # 기존 프로젝트 가져오기 (자동으로 project.json 생성)
            project = pipeline.import_legacy_project(project_id)

        # === 각 탭 데이터 준비 ===

        # 1. 스크립트 미리보기
        script_preview_text = "*스크립트 없음*"
        image_prompts_text = ""
        if project.script:
            script_preview_text = f"# {project.script.title}\n\n"
            script_preview_text += f"**{len(project.script.scenes)}개 씬**\n\n"
            for scene in project.script.scenes:
                script_preview_text += f"### 씬 {scene.scene_id}: {scene.title}\n"
                script_preview_text += f"🖼️ {scene.image_count}장\n\n"
                script_preview_text += f"{scene.text}\n\n---\n\n"
                # 이미지 프롬프트
                for i, prompt in enumerate(scene.image_prompts, 1):
                    image_prompts_text += f"이미지 {scene.scene_id}-{i}: {prompt}\n\n"

        # 2. 오디오
        audio_file = project.audio_path if project.audio_path and os.path.exists(project.audio_path) else None

        # 3. 이미지 갤러리
        images = []
        if project.cut_paths:
            for img_path in project.cut_paths:
                if os.path.exists(img_path):
                    images.append(Image.open(img_path))

        # 4. 자막
        subtitle_text = ""
        if project.subtitle_path and os.path.exists(project.subtitle_path):
            with open(project.subtitle_path, "r", encoding="utf-8") as f:
                subtitle_text = f.read()[:2000]

        # 5. 영상
        video_file = project.video_path if project.video_path and os.path.exists(project.video_path) else None
        final_video_file = project.final_video_path if project.final_video_path and os.path.exists(project.final_video_path) else None

        # 상태 정보
        info = f"""### ✅ 프로젝트 불러오기 완료

**제목**: {project.title}
**분량**: {project.duration_min}분
**상태**: {project.status}

---
**스크립트**: {'✅ ' + str(len(project.script.scenes)) + '개 씬' if project.script else '❌ 없음 (TTS 재생성 불가)'}
**이미지**: {'✅ ' + str(len(project.cut_paths)) + '장' if project.cut_paths else '❌ 없음'}
**오디오**: {'✅ 있음' if audio_file else '❌ 없음'}
**영상**: {'✅ 있음' if final_video_file else '❌ 없음'}

{'⚠️ **기존 프로젝트**: 스크립트가 없어 TTS 재생성은 불가합니다. 기존 오디오로 영상 재렌더링만 가능합니다.' if not project.script else ''}
"""

        status_msg = f"✅ 프로젝트 불러오기 완료: {project.title}"

        return (
            info,  # loaded_project_info
            status_msg,  # status
            script_preview_text,  # script_preview
            image_prompts_text,  # image_prompts
            image_prompts_text,  # final_prompts
            audio_file,  # audio_preview
            images,  # images_gallery
            subtitle_text,  # subtitle_preview
            video_file,  # video_preview
            final_video_file,  # final_video
        )

    except Exception as e:
        return (
            f"❌ 오류: {e}",
            f"❌ 오류: {e}",
            "", "", "", None, [], "", None, None
        )


def regenerate_tts_for_repurpose(engine: str, style: str, speed: float):
    """TTS 재생성 (재활용용)"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 스크립트가 있는 프로젝트를 먼저 불러오세요", None

    try:
        audio_path = pipeline.regenerate_tts(engine=engine, style=style, speed=speed)
        total = sum(s.duration for s in pipeline.project.audio_segments)
        return f"✅ TTS 재생성 완료 ({total:.1f}초)", audio_path
    except Exception as e:
        return f"❌ 오류: {e}", None


def regenerate_subtitle_for_repurpose():
    """자막 재생성 (재활용용)"""
    if not pipeline.project or not pipeline.project.audio_path:
        return "❌ 오디오가 있는 프로젝트를 먼저 불러오세요"

    try:
        subtitle_path = pipeline.regenerate_subtitles()
        return f"✅ 자막 재생성 완료: {subtitle_path}"
    except Exception as e:
        return f"❌ 오류: {e}"


def rerender_video_for_repurpose(use_ken_burns: bool, bgm_option: str):
    """영상 재렌더링 (재활용용)"""
    if not pipeline.project:
        return "❌ 프로젝트를 먼저 불러오세요", None

    if not pipeline.project.cut_paths:
        return "❌ 이미지가 없습니다", None

    if not pipeline.project.audio_path:
        return "❌ 오디오가 없습니다 (TTS 먼저 생성하세요)", None

    try:
        # BGM 처리
        bgm_path = None
        if bgm_option == "random":
            bgm_path = pipeline.video_engine.get_random_bgm()

        final_path = pipeline.rerender_video(
            use_ken_burns=use_ken_burns,
            bgm_path=bgm_path
        )

        # 프로젝트 저장
        pipeline.save_project()

        return f"✅ 재렌더링 완료!", final_path
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
        style = getattr(pipeline.project, 'style', '정보') if pipeline.project else '정보'

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
            output_path=output_path
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
    """AI 생성 썸네일 텍스트 가져오기 (이미 생성된 경우)"""
    if not pipeline.project or not pipeline.project.script:
        return "❌ 프로젝트/스크립트 없음", "", "", ""

    # AI 생성 메타데이터가 있으면 사용
    youtube_metadata = getattr(pipeline.project, 'youtube_metadata', None)
    if youtube_metadata and youtube_metadata.get("thumbnail_text"):
        main_text = youtube_metadata["thumbnail_text"].replace("\\n", "\n")
        return "✅ AI 생성 썸네일 텍스트 적용!", "", main_text, ""

    # 없으면 기존 방식으로 생성
    script = pipeline.project.script
    title = script.title or ""
    style = getattr(pipeline.project, 'style', '정보')

    # 스타일별 텍스트 생성
    if style == "불교명상":
        sub_text = "잠자면서 듣는"
        if len(title) > 20:
            main_text = title[:20] + "..."
        else:
            main_text = title
        bottom_text = "마음이 편안해지는 말씀"
    elif style == "뉴스":
        sub_text = "긴급 속보"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = "지금 바로 확인하세요"
    elif style == "스토리텔링":
        sub_text = "충격 실화"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = "이게 진짜라고?"
    else:  # 정보
        sub_text = "꼭 알아야 할"
        main_text = title[:25] if len(title) > 25 else title
        bottom_text = "지금 확인하세요"

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
        style = getattr(pipeline.project, 'style', '정보') if pipeline.project else '정보'

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
            output_path=preview_path
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
        style = getattr(pipeline.project, 'style', '정보') if pipeline.project else '정보'

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
            output_path=output_path
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
        "정보",  # style_input
        STYLE_GUIDES["정보"],  # style_guide
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
                f"✅ **{lang_names.get(language, language)} 채널 연결됨**: {channel['title']}",
                f"### 📺 {lang_names.get(language, language)} 채널 정보\n"
                f"- **채널명**: {channel['title']}\n"
                f"- **구독자**: {channel['subscribers']}\n"
                f"- **영상 수**: {channel['videos']}개",
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
            if "forbidden" in str(result.get("thumbnail_error", "")).lower():
                thumb_note = "\n\n⚠️ **썸네일 업로드 실패**: YouTube 채널 전화번호 인증이 필요합니다.\n[YouTube 스튜디오 → 설정 → 채널 → 기능 사용 자격 요건](https://studio.youtube.com)"
            else:
                thumb_note = f"\n\n⚠️ 썸네일 업로드 실패: {result.get('thumbnail_error', '알 수 없음')}"

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

    if not pipeline.project:
        return "❌ 프로젝트 없음", "", "", "", "", None, None

    project = pipeline.project
    script = project.script
    style = getattr(project, 'style', '정보')

    # 영상 길이 계산 (분)
    duration = getattr(project, 'duration', 10)

    # AI 생성 메타데이터 우선 사용
    youtube_metadata = getattr(project, 'youtube_metadata', None)
    if youtube_metadata and youtube_metadata.get("title"):
        title = youtube_metadata["title"]
    else:
        # 폴백: 템플릿 기반 제목 생성
        title_templates = YOUTUBE_TITLE_TEMPLATES.get(style, YOUTUBE_TITLE_TEMPLATES.get("정보", []))
        if title_templates:
            title_template = random.choice(title_templates)
            title = title_template.format(duration=duration)
        else:
            title = script.title if script else project.title

    # 금지어 체크 및 제거
    for forbidden in YOUTUBE_FORBIDDEN_WORDS:
        if forbidden in title:
            title = title.replace(forbidden, "")

    # 씬 요약 생성
    scene_summaries = ""
    if script:
        for i, scene in enumerate(script.scenes[:5], 1):
            scene_summaries += f"📌 {scene.title}\n"

    # 언어별 설명 템플릿 선택
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

    # 설명 생성 - 언어별 템플릿 사용
    desc_template = desc_templates.get(style, desc_templates.get("default", ""))
    description = desc_template.format(
        title=title,
        scene_summaries=scene_summaries
    )

    # 태그 - 언어별 config에서 가져오기
    tags = tags_dict.get(style, "")

    # 추가 태그 (제목 키워드 추출) - 한국어만
    if language == "ko" and script and script.title:
        extra_keywords = script.title.replace(",", " ").split()[:3]
        for kw in extra_keywords:
            if len(kw) > 1 and kw not in tags:
                tags += f", {kw}"

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
                        ["뉴스", "정보", "스토리텔링",
                         "스토리텔링:한국불교", "스토리텔링:중국불교", "스토리텔링:인도불교",
                         "불교명상"],
                        value="정보",
                        label="스타일"
                    )

                    style_guide = gr.Markdown(STYLE_GUIDES["정보"])

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
                        ["wavenet", "elevenlabs", "elevenlabs2.5", "openai"],
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
                    - `elevenlabs2.5`: Turbo v2.5 SSML+voice_settings 감정 흉내 🚀
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
                            ("fal.ai", "fal"),
                            ("DALL-E", "dalle"),
                            ("Imagen", "imagen"),
                            ("스토리텔링전용", "storymaker"),
                        ],
                        value="fal",
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
                    gen_images_btn = gr.Button("🎨 이미지 생성", variant="primary")
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
        # Tab 7: 프로젝트 재활용 (다른 채널용)
        # ─────────────────────────────────────────────
        with gr.Tab("🔄 재활용") as repurpose_tab:
            gr.Markdown("### 🔄 프로젝트 재활용")
            gr.Markdown("*기존 이미지 유지 → TTS/자막 변경 → 다른 채널 업로드*")

            with gr.Row():
                with gr.Column(scale=1):
                    # 프로젝트 목록
                    gr.Markdown("#### 📁 저장된 프로젝트")
                    refresh_projects_btn = gr.Button("🔄 새로고침", size="sm")
                    project_list = gr.Dataframe(
                        headers=["ID", "제목", "분", "이미지", "오디오", "영상"],
                        datatype=["str", "str", "number", "str", "str", "str"],
                        interactive=False,
                        wrap=True
                    )
                    selected_project_id = gr.Textbox(label="선택된 프로젝트 ID", interactive=True)
                    load_project_btn = gr.Button("📥 프로젝트 불러오기", variant="primary")

                with gr.Column(scale=2):
                    # 불러온 프로젝트 정보
                    loaded_project_info = gr.Markdown("*프로젝트를 선택하세요*")

                    gr.Markdown("---")
                    gr.Markdown("#### 🎙️ TTS 재생성")

                    with gr.Row():
                        repurpose_tts_engine = gr.Dropdown(
                            label="TTS 엔진",
                            choices=["elevenlabs", "wavenet", "openai"],
                            value="elevenlabs"
                        )
                        repurpose_style = gr.Dropdown(
                            label="스타일 (음성 톤)",
                            choices=["뉴스", "정보", "스토리텔링", "불교명상"],
                            value="정보"
                        )
                        repurpose_speed = gr.Slider(0.5, 1.5, value=0.9, step=0.1, label="속도")

                    regenerate_tts_btn = gr.Button("🎙️ TTS 재생성", variant="secondary")
                    repurpose_audio_preview = gr.Audio(label="새 오디오 미리듣기")

                    gr.Markdown("---")
                    gr.Markdown("#### 🎬 영상 재렌더링")

                    with gr.Row():
                        repurpose_ken_burns = gr.Checkbox(label="줌 효과", value=True)
                        repurpose_bgm = gr.Dropdown(
                            label="BGM",
                            choices=[("없음", ""), ("무작위", "random")],
                            value=""
                        )

                    regenerate_subtitle_btn = gr.Button("📝 자막 재생성")
                    rerender_btn = gr.Button("🎬 영상 재렌더링", variant="primary")
                    repurpose_status = gr.Markdown()
                    repurpose_video_preview = gr.Video(label="재렌더링된 영상")

        # ─────────────────────────────────────────────
        # Tab 8: 트렌드 분석 (참고용)
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

    # 스타일 변경시 가이드 업데이트
    style_input.change(update_style_guide, [style_input], [style_guide])

    # Tab 1: 스크립트 생성 + AI 제목/썸네일 (언어 파라미터 추가)
    generate_btn.click(
        generate_script_and_images,
        [topic_input, duration_input, style_input, script_language],
        [status, script_preview, image_prompts, yt_title_input, yt_thumbnail_input]
    )

    # 이미지 프롬프트 자동 복사
    image_prompts.change(lambda x: x, [image_prompts], [final_prompts])

    # Tab 2: TTS
    # 탭 선택 시 ElevenLabs 사용량 로드
    tts_tab.select(get_elevenlabs_usage_info, [], [elevenlabs_usage_display])
    tts_preview_btn.click(preview_tts_script, [tts_engine], [tts_script_preview])
    tts_btn.click(generate_tts, [tts_engine, tts_speed], [status, audio_preview, tts_script_preview])

    # Tab 3: 이미지 생성
    image_engine.change(update_model_choices, [image_engine], [image_model])
    gen_images_btn.click(
        generate_images_from_text,
        [final_prompts, image_engine, image_model, style_input],
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

    # Tab 7: 프로젝트 재활용
    # 탭 선택 시 프로젝트 목록 로드
    repurpose_tab.select(get_project_list, [], [project_list])
    refresh_projects_btn.click(get_project_list, [], [project_list])

    # 테이블 클릭 시 프로젝트 ID 자동 입력
    project_list.select(on_project_select, [project_list], [selected_project_id])

    # 프로젝트 불러오기 - 모든 탭 UI 업데이트
    load_project_btn.click(
        load_selected_project,
        [selected_project_id],
        [
            loaded_project_info,  # 재활용 탭 정보
            status,  # 메인 상태
            script_preview,  # 스크립트 탭
            image_prompts,  # 이미지 프롬프트
            final_prompts,  # 이미지 생성 탭 프롬프트
            audio_preview,  # TTS 탭 오디오
            images_gallery,  # 이미지 갤러리
            subtitle_preview,  # 자막
            video_preview,  # 영상
            final_video,  # 최종 영상
        ]
    )

    # TTS 재생성
    regenerate_tts_btn.click(
        regenerate_tts_for_repurpose,
        [repurpose_tts_engine, repurpose_style, repurpose_speed],
        [repurpose_status, repurpose_audio_preview]
    )

    # 자막 재생성
    regenerate_subtitle_btn.click(
        regenerate_subtitle_for_repurpose,
        [],
        [repurpose_status]
    )

    # 영상 재렌더링
    rerender_btn.click(
        rerender_video_for_repurpose,
        [repurpose_ken_burns, repurpose_bgm],
        [repurpose_status, repurpose_video_preview]
    )

    # Tab 8: 트렌드
    trend_btn.click(analyze_trend, [trend_keyword], [status, trend_result, video_selector])
    extract_btn.click(extract_transcript_and_comments, [video_selector], [status, transcript_result, comments_result])


if __name__ == "__main__":
    port = int(os.environ.get("GRADIO_SERVER_PORT", 7860))
    app.launch(server_name="0.0.0.0", server_port=port, share=False)
