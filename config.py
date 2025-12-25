"""
파이프라인 설정 - 길이별 규격 및 기본값
"""

# 길이별 그리드 규격 (정서 단락 기반 배치)
# panels_per_scene은 기본값일 뿐, 실제로는 정서 전환점 분석으로 배치
DURATION_SPECS = {
    5: {"panels": 9, "rows": 3, "cols": 3, "scenes": 5, "panels_per_scene": 2},
    10: {"panels": 16, "rows": 4, "cols": 4, "scenes": 8, "panels_per_scene": 2},
    15: {"panels": 25, "rows": 5, "cols": 5, "scenes": 10, "panels_per_scene": 3},
    20: {"panels": 36, "rows": 6, "cols": 6, "scenes": 12, "panels_per_scene": 3},
    30: {"panels": 49, "rows": 7, "cols": 7, "scenes": 15, "panels_per_scene": 3},
    40: {"panels": 64, "rows": 8, "cols": 8, "scenes": 18, "panels_per_scene": 4},
}

# TTS 설정 (시니어 타겟 최적화)
TTS_CONFIG = {
    "default_engine": "elevenlabs",  # ElevenLabs 기본 (고품질)

    # Google WaveNet
    "wavenet_voice": "ko-KR-Wavenet-D",  # 남성, 따뜻한 목소리

    # ElevenLabs (시니어 타겟용)
    "elevenlabs_voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 따뜻하고 신뢰감 있는 남성
    "elevenlabs_voice_id_female": "21m00Tcm4TlvDq8ikWAM",  # Rachel - 부드러운 여성

    # OpenAI TTS
    "openai_voice": "onyx",  # 깊고 따뜻한 남성 목소리
}

# 스타일별 ElevenLabs 음성 설정
ELEVENLABS_STYLE_VOICES = {
    "뉴스": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 신뢰감 있는 뉴스 앵커 스타일
        "stability": 0.7,
        "similarity_boost": 0.8,
    },
    "정보": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 친근한 설명 스타일
        "stability": 0.5,
        "similarity_boost": 0.75,
    },
    "믿거나말거나": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 미스터리 내레이션
        "stability": 0.4,
        "similarity_boost": 0.7,
    },
    "불교종교": {
        "voice_id": "4p0HBzAAGyju0nYfNntV",  # 사용자 지정 - 명상/위로 스타일
        "stability": 0.35,  # 낮으면 더 감정적
        "similarity_boost": 0.8,
    },
}

# 스타일별 감정 태그 매핑 (ElevenLabs v3 Audio Tags - 영어만 인식)
# 참고: https://elevenlabs.io/blog/v3-audiotags
EMOTION_TAGS = {
    "불교종교": {
        "intro": "[calm, gentle]",
        "body_sad": "[sad, comforting]",
        "body_hope": "[warm, hopeful]",
        "climax": "[deep, emotional]",
        "ending": "[peaceful, soothing]",
    },
    "믿거나말거나": {
        "intro": "[curious, intrigued]",
        "body": "[tense, suspenseful]",
        "climax": "[shocked, dramatic]",
        "ending": "[mysterious, thoughtful]",
    },
    "뉴스": {
        "intro": "[professional, clear]",
        "body": "[informative, steady]",
        "climax": "[urgent, serious]",
        "ending": "[conclusive, calm]",
    },
    "정보": {
        "intro": "[friendly, engaging]",
        "body": "[clear, explanatory]",
        "climax": "[enthusiastic]",
        "ending": "[warm, encouraging]",
    },
}

# 이미지 설정
IMAGE_CONFIG = {
    # DALL-E 3 규격
    "size_landscape": "1792x1024",  # 롱폼 (16:9)
    "size_portrait": "1024x1792",   # 쇼츠 (9:16)
    "quality": "hd",
    "style": "vivid",
}

# 이미지 스타일 가이드 (일관성 유지용)
IMAGE_STYLE_GUIDES = {
    "oil_painting": "Oil painting style, warm colors, soft brushstrokes, classical art feeling",
    "cinematic": "Cinematic photorealistic, dramatic lighting, movie still quality, 4K resolution",
    "watercolor": "Watercolor illustration style, soft pastel colors, gentle artistic feeling",
    "anime": "High quality anime style, Studio Ghibli inspired, warm and nostalgic feeling",
    "webtoon": "Korean webtoon illustration style, clean line art, expressive characters",
    "realistic": "Photorealistic, professional photography, natural lighting, high detail",
}

# 타겟별 기본 스타일
TARGET_STYLES = {
    "senior": "cinematic",      # 시니어: 사실적이고 친숙한
    "family": "watercolor",     # 가족: 따뜻하고 부드러운
    "drama": "oil_painting",    # 드라마: 예술적이고 감성적
    "kids": "anime",            # 키즈: 애니메이션 스타일
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
        "fontname": "NanumMyeongjo",  # 정자체 (나눔명조)
        "fontsize": 38,  # 크게
        "primary_color": "&HFFFFFF",  # 흰색
        "outline_color": "&H000000",  # 검정 외곽선
        "outline": 3,  # 외곽선 두께
        "shadow": 1,
        "margin_v": 120,  # 화면 중간 아래 (값이 클수록 위로)
        "alignment": 2,  # 하단 중앙 정렬
    },
}

# BGM 설정
BGM_CONFIG = {
    "folder": "assets/bgm",  # BGM 폴더 경로
    "volume": 0.15,  # 배경음악 볼륨 (TTS 대비)
    "fade_out": 3,  # 페이드 아웃 시간 (초)
}

# DALL-E 합본 이미지 마스터 프롬프트
DALLE_MASTER_PROMPT = """You are creating a SINGLE storyboard sheet image.
The image MUST be divided into EXACTLY {rows} rows × {cols} columns = {panels} panels.

CRITICAL LAYOUT RULES:
- Perfect grid layout: {rows} rows × {cols} columns.
- ALL panels must be EXACTLY the same size.
- NO margins, NO gutters, NO borders, NO gaps between panels.
- Panels must fill the ENTIRE image edge-to-edge.
- Reading order: left-to-right, top-to-bottom (panel 1 is top-left).

CONTENT RULES:
- One consistent art style across all panels.
- Same main characters with consistent appearance (clothing, hair, features).
- Consistent world-building, color palette, and lighting.
- NO text, NO captions, NO speech bubbles, NO numbers, NO watermarks.

STORY BEATS (one beat per panel):
{beats_list}
"""
