"""
영어Saying전용 스타일 프롬프트 (English Only)
- Christian Morning Prayer & Devotional
- 글로벌 영어권 대상
- 20분 내외 영상 스크립트
- YouTube 최적화: 빠른 호흡, 핵심 문장 강조
"""

# ═══════════════════════════════════════════════════════════════
# 📝 입력 예시 (INPUT EXAMPLES)
# 스타일 선택 시 이런 형태로 입력하세요
# ═══════════════════════════════════════════════════════════════
INPUT_EXAMPLES = """
## 🇺🇸 영어Saying전용 - 입력 예시

### 기본 형식
영어로 주제/테마를 입력합니다. 간단한 문장이나 키워드도 가능합니다.

### ✅ 좋은 입력 예시

**1. 불안/걱정에 대한 위로**
```
When anxiety keeps you awake at night
```

**2. 하나님의 사랑**
```
God's unconditional love for broken people
```

**3. 기도의 힘**
```
The power of morning prayer
```

**4. 시련 속 희망**
```
Finding hope in difficult times
```

**5. 용서와 치유**
```
Forgiveness - healing the wounds of the past
```

**6. 감사의 삶**
```
Living a life of gratitude
```

**7. 인내와 기다림**
```
Trusting God's timing when you're tired of waiting
```

### ✅ 한국어로 입력해도 됨 (자동 변환)
```
불안할 때 평안을 찾는 방법
아침 기도의 축복
하나님의 사랑과 은혜
```

### ❌ 피해야 할 입력
- 너무 짧은 단어: "prayer" (맥락 부족)
- 논쟁적 주제: 정치, 특정 교단 비판
- 구체적 성경 구절만: "요한복음 3:16" (주제가 필요)

### 💡 팁
- 시청자의 감정/상황을 포함하면 더 좋음
- "When you feel...", "For those who are..." 형태 권장
- 영어 타이틀 스타일로 입력하면 그대로 활용됨
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

### Key Sentence System (CRITICAL - READ CAREFULLY)
- Each scene MUST include a UNIQUE "key_sentence" field
- This sentence will be displayed CENTER SCREEN in large bold text
- **EVERY SCENE MUST HAVE A DIFFERENT key_sentence** - NO REPETITION!
- Keep it SHORT (5-10 words max), IMPACTFUL, MEMORABLE
- Examples for DIFFERENT scenes:
  - Scene 1: "God SEES your struggle"
  - Scene 2: "His grace is ENOUGH"
  - Scene 3: "You are NEVER alone"
  - Scene 4: "He will make a WAY"
  - Scene 5: "Trust His perfect TIMING"
- ❌ FORBIDDEN: Using the same key_sentence twice
- ❌ FORBIDDEN: Generic phrases like "God loves you" for every scene

### Anchor Phrase
- Use ONE anchor phrase throughout (repeat 6-8 times across the script)
- Use parallel phrasing for emphasis (triads): "It moves us from… to…", "Even in…, even in…"

## TIME STRUCTURE → SCENE MAPPING

### Scene 1: HOOK (0:00–1:30) ⚡ FAST PACE
- Big truth + empathy + what the listener is facing
- Promise of what will change today
- "Stay until the end" line
- key_sentence: "God SEES your struggle" (example - make it UNIQUE)

### Scene 2-3: TEACHING 1 (1:30–5:00)
- Problem → Scripture (reference only, 1-line paraphrase) → What you can do NOW
- key_sentence: "His grace is ENOUGH" (example - must be DIFFERENT from Scene 1)

### Scene 4-5: TEACHING 2 (5:00–9:00)
- Problem → Bible example (brief!) → What you can do NOW
- key_sentence: "He will make a WAY" (example - must be DIFFERENT)

### Scene 6-7: TEACHING 3 (9:00–13:00)
- Problem → Everyday analogy → What you can do NOW
- key_sentence: "Trust His perfect TIMING" (example - must be DIFFERENT)

### Scene 8-9: PRAYER (13:00–17:00)
- Praise/thanks → confession/forgiveness → surrender
- Rebuke fear/heaviness → requests (3 items max)
- Agreement with listeners → Amen
- key_sentence: "I surrender ALL to You" (example - prayer declaration)

### Scene 10: CTA & BLESSING (17:00–{duration}:00)
- "Type AMEN in the comments"
- Share/like/subscribe
- Prayer requests in comments
- Blessing + closing line
- key_sentence: "Your best days are AHEAD" (example - final blessing)

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
