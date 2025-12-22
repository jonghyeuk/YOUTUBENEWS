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

# FFmpeg 필터 설정
FFMPEG_FILTERS = {
    # Ken Burns Effect (줌인/줌아웃)
    "ken_burns": {
        "zoom_in": "zoompan=z='min(zoom+0.0015,1.5)':d={duration}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        "zoom_out": "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':d={duration}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        "pan_left": "zoompan=z='1.3':d={duration}:x='if(lte(on,1),(iw-iw/zoom)/2,x-1)':y='(ih-ih/zoom)/2':s={resolution}:fps={fps}",
        "pan_right": "zoompan=z='1.3':d={duration}:x='if(lte(on,1),0,min(x+1,(iw-iw/zoom)))':y='(ih-ih/zoom)/2':s={resolution}:fps={fps}",
    },
    # 오디오 믹싱 (TTS + BGM)
    "audio_mix": {
        # TTS 볼륨 1.0, BGM 볼륨 0.15
        "filter": "[0:a]volume=1.0[tts];[1:a]volume=0.15[bgm];[tts][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
    },
    # 자막 스타일
    "subtitle_style": {
        "fontname": "NanumGothic",
        "fontsize": 24,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline": 2,
        "shadow": 1,
        "margin_v": 50,
    },
}

# BGM 설정
BGM_CONFIG = {
    "folder": "assets/bgm",  # BGM 폴더 경로
    "volume": 0.15,  # 배경음악 볼륨 (TTS 대비)
    "fade_out": 3,  # 페이드 아웃 시간 (초)
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
