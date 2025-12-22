"""
파이프라인 설정 - 길이별 규격 및 기본값
"""

# 길이별 컷/그리드 규격 (고정)
DURATION_SPECS = {
    5: {"panels": 4, "rows": 2, "cols": 2, "scenes": 2, "panels_per_scene": 2},
    10: {"panels": 8, "rows": 2, "cols": 4, "scenes": 4, "panels_per_scene": 2},
    15: {"panels": 12, "rows": 3, "cols": 4, "scenes": 6, "panels_per_scene": 2},
    20: {"panels": 16, "rows": 4, "cols": 4, "scenes": 8, "panels_per_scene": 2},
}

# TTS 설정
TTS_CONFIG = {
    "default_engine": "wavenet",
    "wavenet_voice": "ko-KR-Wavenet-D",
    "elevenlabs_voice": "Josh",  # 기본 ElevenLabs 음성
}

# 이미지 설정
IMAGE_CONFIG = {
    "size": "1792x1024",  # DALL-E 3 가로형
    "quality": "hd",
    "style": "vivid",
}

# 영상 설정
VIDEO_CONFIG = {
    "resolution": "1920x1080",
    "fps": 30,
    "codec": "libx264",
}

# DALL-E 합본 이미지 마스터 프롬프트
DALLE_MASTER_PROMPT = """You are creating a SINGLE storyboard sheet image that contains EXACTLY {rows} rows × {cols} columns panels (total {panels} panels).
Each panel must be a separate illustration for a continuous story. The panels must be aligned to a perfect grid.

ABSOLUTE LAYOUT RULES:
- Perfect grid: {rows} rows × {cols} columns, evenly sized panels.
- Thick, uniform gutters between panels (pure white), and an outer white margin.
- Each panel has a thin black rectangular border.
- No panel overlaps, no irregular shapes, no tilted panels.
- Do NOT merge panels. Do NOT vary panel sizes.

CONTENT RULES:
- One consistent art style across all panels.
- Same main characters across all panels with consistent appearance.
- Consistent background world and color tone.
- No text, no captions, no speech bubbles, no numbers, no watermarks, no logos.

STORY BEATS (one beat per panel, reading order left-to-right, top-to-bottom):
{beats_list}
"""
