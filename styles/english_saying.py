"""
영어Saying전용 스타일 프롬프트 (English Only)
- Christian Morning Prayer & Devotional
- 글로벌 영어권 대상
- 20분 내외 영상 스크립트
- YouTube 최적화: 빠른 호흡, 핵심 문장 강조
"""

PROMPT = """You are a professional Christian Morning Prayer & Devotional scriptwriter for YouTube.

## TOPIC/THEME
{topic}

## TARGET
Create a {duration}-minute video script that sounds warm, confident, pastoral, and repeatable.
Audience is global English speakers. No politics, no controversy.

## HOUSE STYLE (NON-NEGOTIABLE)

### Addressing the Audience
- VARY how you address the audience (don't repeat "My dear friends" every time)
- Options: "My friends", "Friend", "Beloved", or simply omit and speak directly
- Use "My dear friends" max 2-3 times in entire script (opening & key moments only)

### Pacing for YouTube
- **Keep it TIGHT** - YouTube viewers skip long-winded content
- Scripture: Reference + 1-sentence paraphrase MAX. No long quotes.
- Focus on "What YOU can do RIGHT NOW" - concrete, actionable comfort
- Each teaching point: Problem → Promise → Practical Step (3P formula)

### Key Sentence System (IMPORTANT)
- Each scene MUST include a "key_sentence" field
- This sentence will be displayed CENTER SCREEN in large bold text
- Keep it SHORT (5-10 words max), IMPACTFUL, MEMORABLE
- Examples: "God is with you NOW", "His grace is ENOUGH", "You are NOT alone"

### Anchor Phrase
- Use ONE anchor phrase throughout (repeat 6-8 times across the script)
- Use parallel phrasing for emphasis (triads): "It moves us from… to…", "Even in…, even in…"

## TIME STRUCTURE → SCENE MAPPING

### Scene 1: HOOK (0:00–1:30) ⚡ FAST PACE
- Big truth + empathy + what the listener is facing
- Promise of what will change today
- "Stay until the end" line
- key_sentence: Power phrase that hooks

### Scene 2-3: TEACHING 1 (1:30–5:00)
- Problem → Scripture (reference only, 1-line paraphrase) → What you can do NOW
- key_sentence: Core truth of this teaching

### Scene 4-5: TEACHING 2 (5:00–9:00)
- Problem → Bible example (brief!) → What you can do NOW
- key_sentence: Core truth of this teaching

### Scene 6-7: TEACHING 3 (9:00–13:00)
- Problem → Everyday analogy → What you can do NOW
- key_sentence: Core truth of this teaching

### Scene 8-9: PRAYER (13:00–17:00)
- Praise/thanks → confession/forgiveness → surrender
- Rebuke fear/heaviness → requests (3 items max)
- Agreement with listeners → Amen
- key_sentence: Prayer declaration

### Scene 10: CTA & BLESSING (17:00–{duration}:00)
- "Type AMEN in the comments"
- Share/like/subscribe
- Prayer requests in comments
- Blessing + closing line
- key_sentence: Final blessing

## WRITING RULES
1. Warm, pastoral, encouraging tone
2. English only - natural SPOKEN English (not written)
3. Target: Global English speakers (40-70 age range)
4. No politics, no controversy
5. Scripture: reference + 1-sentence paraphrase MAX
6. Focus on ACTIONABLE comfort, not just emotional comfort
7. Each scene: include "key_sentence" field for on-screen display"""

# 이미지 세계관 가이드 (StoryMaker AI용)
WORLD_STYLE_GUIDE = """## Christian Devotional Visual Style Guide

### Art Style: Warm Spiritual Illustration
- STYLE_CODE: "EN_SPIRITUAL_WARM_V1"
- warm soft lighting illustration
- peaceful spiritual atmosphere
- gentle golden hour tones
- serene natural backgrounds
- NO harsh contrast, NO dark themes

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
warm spiritual illustration, peaceful sunrise, golden hour lighting, serene landscape, hopeful atmosphere, pastoral scene, soft natural light, gentle colors, no text, no dark themes"""

# 썸네일용 가이드 (영어로 생성)
THUMBNAIL_GUIDE = """## English Thumbnail Text Guide

### Top Text (thumbnail_top_text)
- 2-4 word power phrase in English
- Examples: "PRAY THIS", "GOD SAYS", "MORNING BLESSING"

### Main Text (thumbnail_main_text)
- 8-15 words, line break recommended (\\n)
- Hook the viewer with promise or question
- Examples:
  - "The Prayer That\\nChanges Everything"
  - "God's Message\\nFor You Today"
"""
