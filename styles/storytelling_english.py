"""
영어 Devotional 스타일 프롬프트 (영어 전용)
- 미국/영어권 35~70 대상: Morning Devotional + Prayer + Gentle CTA
- AI 템플릿 티 제거: softener + micro-scene + cliche blacklist + command limit
- 옵션: prayer_style (gentle / warfare), cta_strength (soft / medium)
- 2-pass 검수 지원
- signature prop: soft sunlight streaming through a window (no text)
"""

from __future__ import annotations

SIGNATURE_PROP = "soft sunlight streaming through a window, no text, no logo"

STYLE_CONFIG = {
    "prayer_style": {
        "gentle": {
            "name": "Gentle pastoral",
            "addon": """
## Prayer tone: Gentle pastoral
- Avoid aggressive spiritual warfare language.
- Use tender, honest, calm phrasing.
- Example: "Give us peace / steady our minds / help us trust You today"
- No "we reject spirits" / "enemy must run" style.
"""
        },
        "warfare": {
            "name": "Spiritual warfare",
            "addon": """
## Prayer tone: Spiritual warfare (controlled)
- Use firm but not sensational language.
- Avoid fear-mongering or extreme claims.
- No demon details, no violent imagery.
- Keep it within mainstream prayer tone.
"""
        },
    },
    "cta_strength": {
        "soft": {
            "name": "Soft CTA",
            "addon": """
## CTA strength: Soft
- One line only. Example: "If this helped, consider sharing with someone who needs it."
- No "type AMEN right now" pressure.
"""
        },
        "medium": {
            "name": "Medium CTA",
            "addon": """
## CTA strength: Medium
- Two lines max. Invite engagement gently.
- Example: "If you'd like, share a prayer request below."
- Still avoid pressure language.
"""
        }
    }
}

# 강한 AI 템플릿 냄새를 내는 표현들 (확장 가능)
CLICHE_BLACKLIST = [
    "turning point",
    "life-changing",
    "i'm here to tell you",
    "in this very moment",
    "right where you are",
    "enemy has to run",
    "breakthrough is coming",
    "shift in the atmosphere",
    "prophetic word",
    "divine appointment",
    "painted your future",
    "break every chain",
    "completely transform",
    "darkness has no power",
    "the enemy is defeated",
    "this is your season",
    "god is positioning you",
    "victory party",
]

PROMPT_BASE = """You are a US Christian devotional scriptwriter for a YouTube channel.
Audience: adults 35-70 (tired, anxious, faith-seeking). Tone: warm, grounded, human. Not hypey. Not preachy.
Format: {num_scenes} scenes (1 image each). {duration} minutes spoken.

## ⚠️ LENGTH REQUIREMENTS (CRITICAL!)
- Target duration: **{duration} minutes**
- Total word count: **{total_words} words minimum** (approx 150 words/minute)
- Each scene: **{words_per_scene} words minimum**
- Scene count: **exactly {num_scenes} scenes**

DO NOT write a short 5-minute script when asked for 15 minutes!
Each scene text MUST be substantial - not just 2-3 sentences.

IMPORTANT: ALL OUTPUT MUST BE IN ENGLISH ONLY.
If the topic is provided in Korean or another language, translate it to English first.
Do NOT include any Korean or non-English text in the final script.

GOAL
Write a devotional that feels human: specific, gentle, honest, and actionable.
No sensationalism. No manipulative fear language. No "AI template" cliches.

HARD RULES (ANTI-AI)
1) Each scene MUST include:
   - one micro-scene detail (time/place/small action/body sensation)
     Examples: "2:07 a.m., staring at the ceiling, tight chest"
              "You reread the same text three times before hitting send"
              "Standing in the grocery aisle, forgetting why you came"
   - one "softener" phrase: (maybe / if you're like me / I don't know your exact story, but... / it might be...)
2) Max 1 direct command per scene. (No constant imperatives.)
3) Avoid cliches in this blacklist (do not use exact phrases):
   "turning point", "life-changing", "i'm here to tell you", "in this very moment",
   "right where you are", "enemy has to run", "breakthrough is coming",
   "shift in the atmosphere", "prophetic word", "divine appointment",
   "painted your future", "break every chain", "completely transform",
   "darkness has no power", "the enemy is defeated", "this is your season",
   "god is positioning you", "victory party"
4) Scripture: 1-2 references total, woven naturally (no stacking verses).
5) Practice: NOT a list of 3-7 tips. Provide ONE small practice explained as steps (10-60 seconds).
6) No overpromising. No prosperity claims. No guaranteed outcomes.

STRUCTURE (8 scenes)
S1 Hook: a concrete moment + the theme in one sentence (no hype).
S2 Teaching: one short verse + what it means (simple).
S3 Application: one real-life area + micro-practice (10 seconds).
S4 Bible story: one character moment with a vivid detail (brief).
S5 Reframe: what this season might be forming in you (no promises).
S6 Practice: "try this today" as steps 1-2-3 (single practice, deeper).
S7 Prayer: 120-180 words.
S8 CTA & Blessing: CTA per option + short blessing.

IMAGE PROMPTS
- One image prompt per scene.
- Keep a consistent style: warm soft lighting, peaceful spiritual atmosphere.
- Always include the signature prop: "soft sunlight streaming through a window, no text, no logo"

KEY SENTENCE (for on-screen display)
- Each scene MUST include a UNIQUE "key_sentence" field (5-10 words max)
- This will be displayed CENTER SCREEN in large bold text
- EVERY SCENE MUST HAVE A DIFFERENT key_sentence - NO REPETITION!
- Examples: "God sees your struggle", "His grace is enough", "You are never alone"

OUTPUT JSON (must be valid)
{
  "title": "...",
  "thumbnail_top_text": "2-4 word power phrase (e.g., MORNING PRAYER)",
  "thumbnail_main_text": "8-15 words hook with line break",
  "scenes": [
    {
      "scene_id": 1,
      "title": "HOOK - ...",
      "text": "...",
      "key_sentence": "...",
      "image_prompts": ["..."]
    }
  ]
}
"""


def get_english_prompt(topic: str, prayer_style: str = "gentle", cta_strength: str = "soft", duration: int = 10) -> str:
    """영어 디보셔널 프롬프트 생성"""
    prayer = STYLE_CONFIG["prayer_style"].get(prayer_style, STYLE_CONFIG["prayer_style"]["gentle"])
    cta = STYLE_CONFIG["cta_strength"].get(cta_strength, STYLE_CONFIG["cta_strength"]["soft"])

    # duration 기반 분량 계산
    num_scenes = max(6, duration // 2 + 2)  # 5분=5씬, 10분=7씬, 15분=9씬, 20분=12씬
    total_words = duration * 150  # 분당 150단어 기준
    words_per_scene = total_words // num_scenes

    formatted_prompt = PROMPT_BASE.format(
        duration=duration,
        num_scenes=num_scenes,
        total_words=total_words,
        words_per_scene=words_per_scene
    )

    return (
        formatted_prompt
        + "\n\n"
        + "TOPIC:\n"
        + topic.strip()
        + "\n\n"
        + prayer["addon"]
        + "\n"
        + cta["addon"]
    )


def get_review_prompt() -> str:
    """
    2-pass 검수용. 1차 생성 결과(JSON)를 입력으로 받아,
    - 금지 클리셰 제거
    - micro-scene/softener 누락 씬 보완
    - command 과다 감소
    - prayer 톤 가이드 준수
    를 수행하고 수정된 JSON만 출력하도록 유도.
    """
    blacklist_str = ", ".join([f'"{x}"' for x in CLICHE_BLACKLIST])
    return f"""You are a strict editor for a Christian devotional script.
You will receive a JSON script. Your job:
- Keep the SAME structure (8 scenes). Preserve meaning.
- Remove or replace exact cliche phrases from blacklist:
  {blacklist_str}
- Ensure EACH scene contains:
  (a) micro-scene detail (time/place/action/body sensation)
  (b) one softener phrase (maybe / if you're like me / I don't know your exact story, but... / it might be...)
- Max 1 direct command per scene. Reduce imperatives if too many.
- Prayer scene: 120-180 words. Match selected prayer tone if detectable; otherwise keep gentle.
- CTA: keep short and non-pushy.
- Ensure all key_sentence values are UNIQUE across scenes.

Output ONLY the corrected JSON (valid). No commentary.
"""


def get_image_prompt_with_prop(image_prompt: str) -> str:
    """signature prop을 항상 덧붙임 (no text 강제)"""
    p = (image_prompt or "").strip()
    if not p:
        return SIGNATURE_PROP
    # 중복 방지용 간단 처리
    if "sunlight" in p.lower() and "window" in p.lower():
        return p + ", no text, no logo"
    return f"{p}, {SIGNATURE_PROP}"


# 이미지 세계관 가이드 (StoryMaker AI용)
WORLD_STYLE_GUIDE = """## English Devotional Visual Style Guide

### Art Style: Warm Spiritual Illustration
- STYLE_CODE: "EN_DEVOTIONAL_WARM_V1"
- warm soft lighting illustration
- peaceful spiritual atmosphere
- gentle golden hour tones
- serene natural backgrounds
- NO harsh contrast, NO dark themes

### Signature Element (MUST INCLUDE)
- Soft sunlight streaming through a window
- This element should appear in EVERY image for channel identity

### Key Features
- Soft, warm color palette
- Natural lighting (sunrise/sunset)
- Peaceful landscapes
- Spiritual symbolism (light, nature)

### Visual Elements
- Sunrise/sunset scenes
- Peaceful nature (fields, mountains, water)
- Warm golden light
- Open skies, clouds
- Gentle pastoral settings
- Window with sunlight (signature)

### Color Palette
- Warm golden tones
- Soft blues and greens
- Cream and white highlights
- Peaceful pastels

### Mood/Atmosphere
- Hopeful and uplifting
- Peaceful and serene
- Warm and welcoming
- Spiritually comforting

### Forbidden Elements
- Dark or scary imagery
- Controversial symbols
- Specific denominational imagery
- Text, watermarks
- Harsh colors or contrast

### Prompt Keywords
warm spiritual illustration, peaceful sunrise, golden hour lighting, serene landscape, hopeful atmosphere, pastoral scene, soft natural light, gentle colors, soft sunlight streaming through window, no text, no dark themes"""


# 썸네일용 가이드 (영어로 생성)
THUMBNAIL_GUIDE = """## English Thumbnail Text Guide

### Top Text (thumbnail_top_text)
- 2-4 word power phrase in English
- Examples: "MORNING PRAYER", "GOD'S MESSAGE", "DAILY DEVOTIONAL"

### Main Text (thumbnail_main_text)
- 8-15 words, line break recommended (\\n)
- Hook the viewer with promise or question
- Avoid cliches: no "life-changing", "breakthrough", etc.
- Examples:
  - "When Worry Won't\\nLet You Sleep"
  - "A Quiet Word\\nFor Tired Hearts"
"""
