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

    # 음성 속도 설정 (1.0 = 기본, 0.5 = 느리게, 2.0 = 빠르게)
    # - WaveNet: 0.25 ~ 4.0
    # - ElevenLabs: 0.5 ~ 2.0 (v3 모델 기준)
    # - OpenAI: 0.25 ~ 4.0
    "speed": 0.9,  # 시니어 타겟: 약간 느리게 (0.9)

    # Google WaveNet
    "wavenet_voice": "ko-KR-Wavenet-D",  # 남성, 따뜻한 목소리

    # ElevenLabs (시니어 타겟용)
    "elevenlabs_voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 따뜻하고 신뢰감 있는 남성
    "elevenlabs_voice_id_female": "21m00Tcm4TlvDq8ikWAM",  # Rachel - 부드러운 여성

    # OpenAI TTS
    "openai_voice": "onyx",  # 깊고 따뜻한 남성 목소리
}

# 스타일별 ElevenLabs 음성 설정
# stability 허용값: 0.0 (Creative), 0.5 (Natural), 1.0 (Robust)
# speed: 0.5 ~ 2.0 (미지정 시 TTS_CONFIG["speed"] 사용)
ELEVENLABS_STYLE_VOICES = {
    "뉴스": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 신뢰감 있는 뉴스 앵커 스타일
        "stability": 1.0,  # Robust - 안정적이고 일관된 톤
        "similarity_boost": 0.8,
        "speed": 1.0,  # 뉴스: 보통 속도
    },
    "정보": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 친근한 설명 스타일
        "stability": 0.5,  # Natural - 자연스러운 톤
        "similarity_boost": 0.75,
        "speed": 0.95,  # 정보: 약간 느리게
    },
    "믿거나말거나": {
        "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam - 미스터리 내레이션
        "stability": 0.0,  # Creative - 다양하고 극적인 톤
        "similarity_boost": 0.7,
        "speed": 0.9,  # 미스터리: 느리게 (긴장감)
    },
    "불교종교": {
        "voice_id": "4p0HBzAAGyju0nYfNntV",  # 사용자 지정 - 명상/위로 스타일
        "stability": 0.0,  # Creative - 감정적이고 따뜻한 톤
        "similarity_boost": 0.8,
        "speed": 0.85,  # 불교: 천천히 (명상적)
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
    # Ken Burns Effect (확실히 눈에 보이는 움직임)
    "ken_burns": {
        # 줌인: 1.0 → 1.25 (25% 확대, 확실히 보임)
        "slow_zoom_in": "zoompan=z='min(zoom+0.001,1.25)':d={duration}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        # 줌아웃: 1.25 → 1.0 (축소)
        "slow_zoom_out": "zoompan=z='if(lte(zoom,1.0),1.25,max(1.0,zoom-0.001))':d={duration}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        # 왼쪽으로 이동 (1.2배 확대 상태)
        "slow_pan_left": "zoompan=z='1.2':d={duration}:x='if(lte(x,0),(iw-iw/zoom),x-3)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        # 오른쪽으로 이동
        "slow_pan_right": "zoompan=z='1.2':d={duration}:x='if(gte(x,iw-iw/zoom),0,x+3)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
        # 정적: 움직임 없음
        "static": "zoompan=z='1':d={duration}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution}:fps={fps}",
    },
    # 오디오 믹싱 (TTS + BGM)
    "audio_mix": {
        # TTS 볼륨 1.0, BGM 볼륨 0.15
        "filter": "[0:a]volume=1.0[tts];[1:a]volume=0.15[bgm];[tts][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
    },
    # 자막 스타일
    "subtitle_style": {
        "fontname": "NanumMyeongjo",  # 정자체 (나눔명조)
        "fontsize": 108,  # 시니어용: 1.5배 더 크게 (72→108)
        "primary_color": "&HFFFFFF",  # 흰색
        "outline_color": "&H000000",  # 검정 외곽선
        "outline": 5,  # 외곽선 두께 (더 두껍게)
        "shadow": 2,  # 그림자 (더 진하게)
        "margin_v": 100,  # 하단 마진 (조금 위로)
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

# ═══════════════════════════════════════════════════════════════
# YouTube 업로드 설정 - 제목/설명/태그 자동 생성
# ═══════════════════════════════════════════════════════════════

# 후킹형 제목 8종 타입
YOUTUBE_HOOK_TYPES = {
    "경고형": "이 말만은… 하지 마세요",
    "상황저격형": "오늘도 생각이 많은 사람",
    "반전형": "놓아야 해결됩니다",
    "관계절연형": "이런 인연은 끊으세요",
    "숫자형": "딱 3가지 / 5가지",
    "질문형": "왜 마음이 불안한가",
    "즉시성": "오늘 밤 30분만",
    "자존감형": "남 눈치 끊는 법",
}

# 스타일별 제목 템플릿
YOUTUBE_TITLE_TEMPLATES = {
    "불교종교": [
        "잠들기 전 {duration}분, 불안이 가라앉는 부처님의 한마디",
        "생각이 많고 예민한 사람, 오늘 밤 {duration}분만 이렇게 하세요",
        "인간관계로 지친 날, 부처님 말씀 {duration}분 낭독",
        "마음이 편해지는 {duration}분 불교 조언",
        "화가 치밀 때, 절대 하지 말아야 할 말 {duration}분",
        "나이 들수록 조심해야 할 것 5가지 (불교 조언 {duration}분)",
        "남 눈치 보느라 힘든 분들께, {duration}분만 들으세요",
        "외로움이 커지는 밤, 마음을 붙잡는 {duration}분 낭독",
        "걱정이 멈추지 않는다면, 오늘은 이 문장으로 끝내세요 ({duration}분)",
        "인연을 끊어야 편해지는 순간들, 불교의 현실 조언 {duration}분",
        "잠자기 전 {duration}분, 마음속 소음을 끄는 법",
        "왜 나는 늘 불안한가? 부처님의 답 {duration}분 낭독",
        "후회가 많은 밤, 마음이 가벼워지는 불교 {duration}분",
        "참는 삶에서 벗어나는 법, 오늘 밤 {duration}분",
        "가족 때문에 마음이 무너질 때, 부처님 말씀 {duration}분",
        "자존감이 깎일 때, 남을 놓아주는 연습 {duration}분",
        "마음이 복잡할수록 단순하게, 불교의 정리 {duration}분",
        "노후가 불안한 분들께, 딱 이것만 {duration}분",
        "오늘 하루를 놓아주는 {duration}분, 수면 낭독",
    ],
    "뉴스": [
        "오늘 꼭 알아야 할 소식 {duration}분 정리",
        "지금 난리난 이슈, {duration}분 총정리",
        "이것만 알면 됩니다 {duration}분 뉴스 브리핑",
    ],
    "정보": [
        "알아두면 쓸모있는 정보 {duration}분",
        "이것만 알면 인생이 편해집니다 {duration}분",
        "모르면 손해보는 꿀팁 {duration}분 정리",
    ],
    "믿거나말거나": [
        "믿기 어려운 실화 {duration}분",
        "소름돋는 이야기 {duration}분",
        "충격적인 진실 {duration}분",
    ],
}

# 제목 생성 시 금지 단어 (과장/허위/의학적 효능)
YOUTUBE_FORBIDDEN_WORDS = [
    "치료", "완치", "치매예방", "100%", "확실한", "무조건",
    "기적", "만능", "특효", "보장", "절대", "반드시",
]

# 스타일별 기본 태그
YOUTUBE_DEFAULT_TAGS = {
    "불교종교": "명상, 불교, 마음치유, 힐링, 위로, 잠잘때듣는, 부처님말씀, 인생명언, ASMR, 수면, 낭독",
    "뉴스": "뉴스, 이슈, 시사, 정보, 핫이슈, 트렌드, 속보, 정리",
    "정보": "정보, 꿀팁, 생활정보, 유용한정보, 알아두면좋은, 상식",
    "믿거나말거나": "미스터리, 실화, 소름, 충격, 믿거나말거나, 신기한이야기",
}

# 설명란 템플릿
YOUTUBE_DESCRIPTION_TEMPLATE = {
    "불교종교": """🙏 {title}

{scene_summaries}

═══════════════════════════════════════
📢 구독과 좋아요 부탁드립니다!
🔔 알림 설정으로 새 영상을 받아보세요

💬 오늘 하루도 마음 편안하시길 바랍니다.
═══════════════════════════════════════

#명상 #불교 #마음치유 #힐링 #위로 #수면 #ASMR
""",
    "default": """📺 {title}

{scene_summaries}

═══════════════════════════════════════
📢 구독과 좋아요 부탁드립니다!
🔔 알림 설정으로 새 영상을 받아보세요
═══════════════════════════════════════
""",
}

# ═══════════════════════════════════════════════════════════════
# 썸네일 텍스트 설정 - 제목과 별도 (초단문 8~16자)
# ═══════════════════════════════════════════════════════════════

# 썸네일 텍스트 템플릿 (제목과 분리 - 짧게!)
# 패턴: 감정/문제 + 동작(해결) 또는 + 시간(길이)
YOUTUBE_THUMBNAIL_TEXT_TEMPLATES = {
    "불교종교": [
        # 1줄 (6~12자, 강력)
        "불안 내려놓기",
        "생각 멈춤",
        "걱정 OFF",
        "화 끊기",
        "인연 정리",
        "마음 비우기",
        "놓아야 산다",
        "예민함 다스리기",
        # 2줄 패턴 (\n으로 구분)
        "불안 내려놓기\n{duration}분 낭독",
        "잠들기 전\n{duration}분",
        "생각 많은 밤\n이 한마디",
        "걱정이 많다면\n오늘만 {duration}분",
        "오늘 밤\n{duration}분",
        "마음이 힘들 때\n듣는 말씀",
    ],
    "뉴스": [
        "오늘 핵심만",
        "핵심 요약",
        "{duration}분 브리핑",
        "지금 무슨 일?",
        "오늘 뉴스\n{duration}분 정리",
    ],
    "정보": [
        "이건 꼭 알기",
        "알면 유리함",
        "모르면 손해",
        "꿀팁 정리",
        "{duration}분 꿀정보",
        "꼭 알아야 할\n{duration}분 정보",
    ],
    "믿거나말거나": [
        "실화입니다",
        "소름 주의",
        "충격 실화",
        "끝까지 보세요",
        "믿기 어려운\n실화",
    ],
}

# 후킹 타입별 썸네일 전용 문구 (짧은 스니펫)
YOUTUBE_THUMBNAIL_HOOK_SNIPPETS = {
    "경고형": ["하지 마세요", "조심하세요", "금지"],
    "상황저격형": ["생각 많은 밤", "예민한 사람", "불안한 밤"],
    "반전형": ["놓아야 됩니다", "비우면 풀림", "그게 답"],
    "관계절연형": ["인연 정리", "거리 두기", "끊어야 편함"],
    "숫자형": ["딱 3가지", "5가지", "1가지"],
    "질문형": ["왜 불안한가", "왜 힘든가", "답은 간단"],
    "즉시성": ["오늘 밤 {duration}분", "지금 바로", "딱 {duration}분"],
    "자존감형": ["눈치 끊기", "나를 지키기", "내가 우선"],
}

# 썸네일 금지어 (제목과 동일 룰 재사용)
YOUTUBE_THUMBNAIL_FORBIDDEN_WORDS = YOUTUBE_FORBIDDEN_WORDS

# 썸네일 생성 규칙
YOUTUBE_THUMBNAIL_RULES = {
    # 길이 기준
    "optimal_chars": 12,       # 최적: 6~12자 (1줄)
    "max_chars": 18,           # 최대: 18자 (2줄 포함)
    "max_chars_per_line": 9,   # 줄당 최대 9자
    "max_lines": 2,            # 최대 줄 수
    # 스타일 규칙
    "prefer_korean_short": True,
    "avoid_punctuation": True,  # ".", "!" 남발 금지
    "avoid_too_many_keywords": True,
    # 피해야 할 것
    "warn_over_chars": 20,     # 20자 이상이면 경고 (모바일 뭉개짐)
}

