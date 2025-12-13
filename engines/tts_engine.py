import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple
from openai import OpenAI
from models.types import Scene, ContentProfile
import requests

# Google Cloud TTS (선택적)
try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False


# ★ TTS Model Router v0.2 - 상황별 최적 엔진 라우팅
# "우선순위 리스트"가 아닌, 상황 조합 → 최적 단일 엔진 매핑
#
# 설계 원칙:
# 1. 자동 모드 = 상황별로 최적 엔진 하나를 결정
# 2. 폴백은 "선택한 엔진이 사용 불가할 때"만 발생
# 3. 사용자가 직접 선택하면 그 엔진을 사용 (실패 시에만 폴백)

# 상황별 최적 엔진 매핑 (단일 값, 리스트 아님!)
# ★ Naver/OpenAI 비활성화 → 모든 모드에서 Gemini 사용
# 키: (mode, has_dialogue, emotion_intensity) 조합
TTS_OPTIMAL_ENGINE = {
    # === 모드 기반 (8개 모드 전체) → 모두 Gemini ===
    "yadam": "gemini",
    "yadam_kr_v1": "gemini",
    "kids": "gemini",
    "kids_kr_v1": "gemini",
    "history": "gemini",
    "drama": "gemini",
    "drama_kr_v1": "gemini",
    "emotional": "gemini",
    "emotional_kr_v1": "gemini",
    "nostalgic": "gemini",
    "nostalgic_kr_v1": "gemini",
    "wisdom": "gemini",
    "wisdom_kr_v1": "gemini",
    "knowledge": "gemini",
    "knowledge_kr_v1": "gemini",
    "classic": "gemini",
    "classic_kr_v1": "gemini",
    "lecture": "gemini",
    "health": "gemini",
    "money": "gemini",

    # === 대사 유무 기반 → Gemini ===
    "has_dialogue": "gemini",

    # === 감정 강도 기반 → 모두 Gemini ===
    "emotion_high": "gemini",
    "emotion_serious": "gemini",
    "emotion_normal": "gemini",

    # === 기본값 ===
    "default": "gemini"
}

# 감정 태그 → 감정 강도 분류
EMOTION_INTENSITY = {
    "excited": "high",    # 강한 감정 → prosody 제어 필요
    "sad": "high",
    "serious": "serious", # 진지함 → 낮은 톤
    "warm": "normal",     # 일반
    "calm": "normal",
}

# TTS 엔진별 기본 음성 (★ 여성 음성 우선)
TTS_DEFAULT_VOICES = {
    "gemini": "Kore",       # ★ 여성 음성
    "openai": "nova",       # ★ 여성 음성
    "naver": "naver_nara",  # 여성 음성
    "google": "google_wavenet_a"  # 여성 음성
}

# 모드별 추천 음성 (엔진 내에서 세부 음성 선택) - ★ 모두 Gemini 여성 음성
TTS_MODE_VOICES = {
    # === 모든 모드 → Gemini 여성 음성 ===
    # Kore: 부드럽고 차분한 여성 (기본)
    # Aoede: 밝고 활기찬 여성 (유아/활기찬 콘텐츠용)

    # 야담 모드 → Kore (부드러운 여성, 이야기꾼 스타일)
    ("gemini", "yadam"): "Kore",
    ("gemini", "yadam_kr_v1"): "Kore",
    # 유아 동화 → Aoede (밝고 활기찬 여성)
    ("gemini", "kids"): "Aoede",
    ("gemini", "kids_kr_v1"): "Aoede",
    # 역사 모드 → Kore (차분한 여성)
    ("gemini", "history"): "Kore",
    # 드라마 모드 → Kore (감정적인 여성)
    ("gemini", "drama"): "Kore",
    ("gemini", "drama_kr_v1"): "Kore",
    # 감성/추억 모드 → Kore (따뜻한 여성)
    ("gemini", "emotional"): "Kore",
    ("gemini", "emotional_kr_v1"): "Kore",
    ("gemini", "nostalgic"): "Kore",
    ("gemini", "nostalgic_kr_v1"): "Kore",
    # 지혜 모드 → Kore (사려깊은 여성)
    ("gemini", "wisdom"): "Kore",
    ("gemini", "wisdom_kr_v1"): "Kore",
    # 지식 모드 → Kore (친근한 여성)
    ("gemini", "knowledge"): "Kore",
    ("gemini", "knowledge_kr_v1"): "Kore",
    # 클래식 모드 → Kore (감상적인 여성)
    ("gemini", "classic"): "Kore",
    ("gemini", "classic_kr_v1"): "Kore",
    # 강의/건강/재테크 → Kore (차분한 여성)
    ("gemini", "lecture"): "Kore",
    ("gemini", "health"): "Kore",
    ("gemini", "money"): "Kore",
}


# ★ Emotion TTS v0.2 - 감정별 TTS 프로필 (야담 스타일 0.85 기본)
# 레퍼런스 분석 결과 (5자/초) 반영 - 여유롭고 차분한 야담 스타일
EMOTION_TTS_PROFILES = {
    "warm": {
        "desc": "따뜻함, 감동",
        "google_ssml": {"rate": "slow", "pitch": "-1st", "volume": "medium"},
        "naver_params": {"speed": -1, "pitch": -1, "volume": 0},
        "openai_speed": 0.85
    },
    "serious": {
        "desc": "진지함, 긴장",
        "google_ssml": {"rate": "slow", "pitch": "-2st", "volume": "medium"},
        "naver_params": {"speed": -1, "pitch": -2, "volume": 0},
        "openai_speed": 0.85
    },
    "excited": {
        "desc": "기쁨, 놀람",
        "google_ssml": {"rate": "medium", "pitch": "+1st", "volume": "loud"},
        "naver_params": {"speed": 0, "pitch": 1, "volume": 1},
        "openai_speed": 0.90
    },
    "sad": {
        "desc": "슬픔, 회한",
        "google_ssml": {"rate": "slow", "pitch": "-2st", "volume": "soft"},
        "naver_params": {"speed": -1, "pitch": -2, "volume": -1},
        "openai_speed": 0.80
    },
    "calm": {
        "desc": "평온함, 마무리",
        "google_ssml": {"rate": "slow", "pitch": "0st", "volume": "medium"},
        "naver_params": {"speed": -1, "pitch": 0, "volume": 0},
        "openai_speed": 0.85
    }
}


class TTSEngine:
    """
    TTS 음성 합성 엔진
    - Google Cloud TTS (기본, 한국어 네이티브)
    - OpenAI TTS
    - 네이버 CLOVA Voice (한국어 최적화)
    """

    # 시니어 맞춤 음성 매핑
    VOICE_MAPPING = {
        "warm_slow": "alloy",     # 따뜻하고 중성적인
        "gentle": "nova",          # 부드러운 여성
        "calm": "shimmer",         # 차분한
        "friendly": "echo",        # 친근한 남성
        "professional": "onyx",    # 전문적인 남성
        "dramatic": "onyx",        # 드라마틱 (역사 모드용)
        "dramatic_emotional": "nova",  # 드라마 감정적
        "bright_friendly": "nova"  # 밝고 친근 (유아 모드용)
    }

    # 역사 모드 기본 음성 (다중 화자용)
    HISTORY_DEFAULT_VOICES = {
        "narrator1": "onyx",   # 메인 나레이터 (깊고 전문적인 남성)
        "narrator2": "nova"    # 서브 나레이터 (따뜻한 여성)
    }

    # OpenAI TTS 음성 특성 (GPT 음성 선택용)
    OPENAI_VOICE_CHARACTERISTICS = {
        "alloy": {"gender": "neutral", "tone": "warm", "style": "balanced"},
        "echo": {"gender": "male", "tone": "deep", "style": "authoritative"},
        "fable": {"gender": "male", "tone": "warm", "style": "storytelling"},
        "onyx": {"gender": "male", "tone": "deep", "style": "dramatic"},
        "nova": {"gender": "female", "tone": "warm", "style": "friendly"},
        "shimmer": {"gender": "female", "tone": "soft", "style": "gentle"}
    }

    # 네이버 CLOVA Voice 음성 목록
    # https://api.ncloud-docs.com/docs/ai-naver-clovavoice-ttspremium
    NAVER_VOICES = {
        # 한국어 여성
        "naver_nara": {"name": "nara", "gender": "female", "desc": "고운, 차분한 여성"},
        "naver_nara_call": {"name": "nara_call", "gender": "female", "desc": "고운 여성 (상담원)"},
        "naver_nminsang": {"name": "nminsang", "gender": "female", "desc": "밝고 경쾌한 여성"},
        "naver_nyejin": {"name": "nyejin", "gender": "female", "desc": "차분한 여성 아나운서"},
        "naver_mijin": {"name": "mijin", "gender": "female", "desc": "부드러운 여성"},
        "naver_jinho": {"name": "jinho", "gender": "female", "desc": "진지한 여성"},
        # 한국어 남성
        "naver_nwontak": {"name": "nwontak", "gender": "male", "desc": "따뜻한 남성"},
        "naver_nkyungtae": {"name": "nkyungtae", "gender": "male", "desc": "침착한 남성"},
        "naver_njoonyoung": {"name": "njoonyoung", "gender": "male", "desc": "활기찬 남성"},
        "naver_nseonghoon": {"name": "nseonghoon", "gender": "male", "desc": "온화한 남성"},
        "naver_njihwan": {"name": "njihwan", "gender": "male", "desc": "차분한 남성"},
        "naver_njooahn": {"name": "njooahn", "gender": "male", "desc": "부드러운 남성"},
        # 아동/동화용
        "naver_ndain": {"name": "ndain", "gender": "female", "desc": "아이 목소리 (동화용)"},
        "naver_noyj": {"name": "noyj", "gender": "female", "desc": "밝은 여성 (동화용)"},
    }

    # Gemini TTS 음성 목록 (gemini-2.5-flash-tts, gemini-2.5-pro-tts)
    # https://ai.google.dev/gemini-api/docs/speech-generation
    GEMINI_TTS_VOICES = {
        # Flash 모델 (빠른 생성)
        "gemini_flash_puck": {"model": "gemini-2.5-flash-preview-tts", "voice": "Puck", "gender": "male", "desc": "Puck - 밝고 경쾌한 남성 (Flash)"},
        "gemini_flash_charon": {"model": "gemini-2.5-flash-preview-tts", "voice": "Charon", "gender": "male", "desc": "Charon - 차분하고 따뜻한 남성 (Flash)"},
        "gemini_flash_kore": {"model": "gemini-2.5-flash-preview-tts", "voice": "Kore", "gender": "female", "desc": "Kore - 부드러운 여성 (Flash)"},
        "gemini_flash_fenrir": {"model": "gemini-2.5-flash-preview-tts", "voice": "Fenrir", "gender": "male", "desc": "Fenrir - 깊고 웅장한 남성 (Flash)"},
        "gemini_flash_aoede": {"model": "gemini-2.5-flash-preview-tts", "voice": "Aoede", "gender": "female", "desc": "Aoede - 밝고 활기찬 여성 (Flash)"},
        # Pro 모델 (고품질)
        "gemini_pro_puck": {"model": "gemini-2.5-pro-preview-tts", "voice": "Puck", "gender": "male", "desc": "Puck - 밝고 경쾌한 남성 (Pro, 고품질)"},
        "gemini_pro_charon": {"model": "gemini-2.5-pro-preview-tts", "voice": "Charon", "gender": "male", "desc": "Charon - 차분하고 따뜻한 남성 (Pro, 고품질)"},
        "gemini_pro_kore": {"model": "gemini-2.5-pro-preview-tts", "voice": "Kore", "gender": "female", "desc": "Kore - 부드러운 여성 (Pro, 고품질)"},
        "gemini_pro_fenrir": {"model": "gemini-2.5-pro-preview-tts", "voice": "Fenrir", "gender": "male", "desc": "Fenrir - 깊고 웅장한 남성 (Pro, 고품질)"},
        "gemini_pro_aoede": {"model": "gemini-2.5-pro-preview-tts", "voice": "Aoede", "gender": "female", "desc": "Aoede - 밝고 활기찬 여성 (Pro, 고품질)"},
    }

    # 주인공 대사용 기본 음성 설정 (나레이션 ↔ 대사 매핑)
    # ★ 나레이션이 여성이면 대사(등장인물)는 남성, 그 반대도 마찬가지
    DIALOGUE_VOICE_MAP = {
        # OpenAI 음성 매핑
        "onyx": "echo",      # 메인이 onyx면 대사는 echo
        "nova": "shimmer",   # 메인이 nova면 대사는 shimmer
        "alloy": "fable",    # 메인이 alloy면 대사는 fable
        "echo": "onyx",      # 메인이 echo면 대사는 onyx
        "fable": "echo",     # 메인이 fable면 대사는 echo
        "shimmer": "nova",   # 메인이 shimmer면 대사는 nova
        # ★ Gemini 음성 매핑 (나레이션 여성 → 대사 남성)
        "Kore": "Charon",    # 나레이션 Kore(여성) → 대사 Charon(남성)
        "Aoede": "Puck",     # 나레이션 Aoede(여성) → 대사 Puck(남성)
        "Charon": "Kore",    # 나레이션 Charon(남성) → 대사 Kore(여성)
        "Puck": "Aoede",     # 나레이션 Puck(남성) → 대사 Aoede(여성)
        "Fenrir": "Kore",    # 나레이션 Fenrir(남성) → 대사 Kore(여성)
        # Google 음성 매핑
        "google_wavenet_a": "google_wavenet_b",  # A(여성) → B(남성)
        "google_wavenet_c": "google_wavenet_d",  # C(여성) → D(남성)
        "google_wavenet_b": "google_wavenet_a",  # B(남성) → A(여성)
        "google_wavenet_d": "google_wavenet_c",  # D(남성) → C(여성)
    }

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: OpenAI API 키
        """
        # OpenAI TTS
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            print("[TTSEngine] Warning: No OpenAI API key. TTS disabled.")

        # Google Cloud TTS
        self.google_client = None
        if GOOGLE_TTS_AVAILABLE:
            try:
                # GOOGLE_APPLICATION_CREDENTIALS 환경변수 또는 자동 인증 사용
                self.google_client = texttospeech.TextToSpeechClient()
                print("[TTSEngine] Google Cloud TTS initialized")
            except Exception as e:
                print(f"[TTSEngine] Google Cloud TTS not available: {e}")
                print("[TTSEngine] Set GOOGLE_APPLICATION_CREDENTIALS for Google TTS")

        # 네이버 CLOVA Voice API
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
        self.naver_enabled = bool(self.naver_client_id and self.naver_client_secret)
        if self.naver_enabled:
            print("[TTSEngine] 네이버 CLOVA Voice initialized")
        else:
            print("[TTSEngine] 네이버 CLOVA Voice not configured (NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 필요)")

        # Gemini TTS (gemini-2.5-flash-tts, gemini-2.5-pro-tts)
        # ★ TTS 전용 키 우선, 없으면 공용 키 사용 (할당량 분리 가능)
        self.gemini_api_key = os.getenv("GEMINI_TTS_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.gemini_tts_enabled = bool(self.gemini_api_key)
        if self.gemini_tts_enabled:
            key_type = "TTS전용" if os.getenv("GEMINI_TTS_API_KEY") else "공용"
            print(f"[TTSEngine] Gemini TTS initialized ({key_type} 키)")
        else:
            print("[TTSEngine] Gemini TTS not configured (GEMINI_TTS_API_KEY 또는 GEMINI_API_KEY 필요)")

    def _analyze_story_tone(self, scenes: List[Scene]) -> str:
        """
        이야기 흐름을 분석하여 일관된 나레이션 톤 결정

        규칙:
        - 시작이 어둡고/힘들면 → calm (차분함)
        - 시작이 따뜻하고/평범하면 → warm (따뜻함)
        - 엔딩이 행복이면 → warm
        - 엔딩이 물음표/여운이면 → calm

        Returns:
            str: 나레이션 톤 ('warm' 또는 'calm')
        """
        if not scenes:
            return "warm"

        # 시작 씬 분석 (channel_intro 제외)
        start_scene = None
        for scene in scenes:
            if scene.scene_id not in ["channel_intro", "opening"]:
                start_scene = scene
                break

        # 끝 씬 분석
        end_scene = scenes[-1] if scenes else None

        # 어두운/힘든 키워드
        dark_keywords = ["죽", "피", "눈물", "슬", "아픔", "고통", "두려", "무서", "공포",
                        "절망", "비극", "암흑", "어둠", "잔혹", "처형", "살", "복수",
                        "원한", "저주", "귀신", "혼령", "망령"]

        # 따뜻한/평범한 키워드
        warm_keywords = ["햇살", "따뜻", "평화", "행복", "웃", "미소", "사랑", "기쁨",
                        "희망", "축복", "선물", "감사", "포근", "편안"]

        # 열린 결말/여운 키워드
        open_keywords = ["알 수 없", "미스터리", "의문", "비밀", "전해", "한다더라",
                        "라고 한다", "뿐이었", "그랬을까", "였을까", "알 길이"]

        # 시작 톤 분석
        start_tone = "warm"
        if start_scene:
            narration = start_scene.narration.lower() if start_scene.narration else ""
            scene_emotion = getattr(start_scene, 'emotion_tag', 'warm')

            dark_count = sum(1 for kw in dark_keywords if kw in narration)
            warm_count = sum(1 for kw in warm_keywords if kw in narration)

            if dark_count > warm_count or scene_emotion in ["sad", "serious"]:
                start_tone = "calm"

        # 엔딩 톤 분석
        end_tone = "warm"
        if end_scene:
            narration = end_scene.narration.lower() if end_scene.narration else ""
            scene_emotion = getattr(end_scene, 'emotion_tag', 'warm')

            open_count = sum(1 for kw in open_keywords if kw in narration)
            warm_count = sum(1 for kw in warm_keywords if kw in narration)

            if open_count > 0 or scene_emotion == "calm":
                end_tone = "calm"
            elif scene_emotion in ["warm", "excited"]:
                end_tone = "warm"

        # 최종 결정: 시작과 끝이 다르면 시작 기준, 같으면 그대로
        final_tone = start_tone

        print(f"[TTSEngine] ★ 이야기 톤 분석: 시작={start_tone}, 끝={end_tone} → 나레이션 톤: {final_tone}")
        return final_tone

    def generate_audio(self, scenes: List[Scene], profile: ContentProfile,
                      output_dir: str) -> List[Dict[str, any]]:
        """
        각 scene의 나레이션을 오디오로 변환
        [DIALOGUE] 태그가 있으면 주인공 대사를 다른 음성으로 처리

        Args:
            scenes: Scene 리스트
            profile: 컨텐츠 프로필 (속도, 톤 등 설정)
            output_dir: 오디오 파일 저장 디렉토리

        Returns:
            오디오 정보 리스트 [{"path": "...", "duration": ...}, ...]
        """
        if not self.enabled:
            print("[TTSEngine] Skipping audio generation (API not configured)")
            return []

        os.makedirs(output_dir, exist_ok=True)
        audio_files = []

        # ★ 통합 설정: profile.extra["tts_config"]에서 읽기
        # profile_engine.py에서 모드별로 최적 TTS 설정을 해둠
        tts_config = profile.extra.get("tts_config", {})

        # 음성 선택 우선순위: 환경변수 > profile 설정 > 자동 모드
        selected_voice = os.getenv("TTS_VOICE", "")

        # 환경변수가 없으면 profile에서 가져오기
        if not selected_voice and tts_config:
            selected_voice = tts_config.get("voice", "")
            if selected_voice:
                print(f"[TTSEngine] ★ Profile 설정 사용: voice={selected_voice}")

        is_auto_mode = (selected_voice == "auto" or selected_voice == "")

        if is_auto_mode:
            print(f"[TTSEngine] ★ 자동 모드: TTS Model Router 활성화 (Scene별 최적 엔진 선택)")

        # ★ 속도 설정: tts_config에서 읽거나 profile.speech_speed 사용
        base_speech_speed = tts_config.get("speed", profile.speech_speed)
        print(f"[TTSEngine] 기본 속도: {base_speech_speed}")

        # 명시적 음성 선택 시 초기 설정
        use_google_tts = False
        use_naver_tts = False
        use_gemini_tts = False
        voice = "alloy"  # 기본값
        naver_voice = "nara"
        google_voice = "ko-KR-Wavenet-A"
        gemini_voice = "gemini_flash_puck"

        if not is_auto_mode:
            use_google_tts = selected_voice.startswith("google_")
            use_naver_tts = selected_voice.startswith("naver_")
            use_gemini_tts = selected_voice.startswith("gemini_")
            use_openai_tts = selected_voice in ["alloy", "nova", "shimmer", "echo", "fable", "onyx"]

            # ★ Naver TTS 비활성화 (선택 불가)
            if use_naver_tts:
                print(f"[TTSEngine] ⚠️ Naver TTS 비활성화됨. Gemini TTS로 전환.")
                use_naver_tts = False
                use_gemini_tts = True
                gemini_voice = "gemini_flash_kore"  # 여성 음성

            # ★ OpenAI TTS 비활성화 (선택 불가)
            if use_openai_tts:
                print(f"[TTSEngine] ⚠️ OpenAI TTS 비활성화됨. Gemini TTS로 전환.")
                use_gemini_tts = True
                gemini_voice = "gemini_flash_kore"  # 여성 음성

            if use_gemini_tts:
                # Gemini TTS 음성
                if selected_voice in self.GEMINI_TTS_VOICES:
                    gemini_voice = selected_voice
                elif not gemini_voice:
                    gemini_voice = "gemini_flash_kore"  # ★ 기본 여성 음성

                # Gemini TTS 사용 가능 여부 확인
                if not self.gemini_tts_enabled:
                    print(f"[TTSEngine] ⚠️ Gemini TTS 선택되었으나 사용 불가. Google TTS로 폴백.")
                    use_gemini_tts = False
                    use_google_tts = True
                    google_voice = "ko-KR-Wavenet-A"  # 여성 음성
            elif use_google_tts:
                # ★ Google TTS 음성 매핑 (여성 음성만 - Neural2 포함)
                google_voice_map = {
                    "google_wavenet_a": "ko-KR-Wavenet-A",   # 여성, 차분
                    "google_wavenet_b": "ko-KR-Wavenet-B",   # 여성, 밝음
                    "google_wavenet_c": "ko-KR-Wavenet-C",   # 남성 (대사용)
                    "google_wavenet_d": "ko-KR-Wavenet-D",   # 남성 (대사용)
                    "google_neural2_a": "ko-KR-Neural2-A",   # 여성, 자연스러움
                    "google_neural2_b": "ko-KR-Neural2-B",   # 여성, 활기참
                }
                google_voice = google_voice_map.get(selected_voice, "ko-KR-Wavenet-A")

                # Google TTS 사용 가능 여부 확인
                if not self.google_client:
                    print(f"[TTSEngine] ⚠️ Google TTS 선택되었으나 사용 불가. Gemini로 폴백.")
                    use_google_tts = False
                    use_gemini_tts = True
                    gemini_voice = "gemini_flash_kore"
            else:
                # ★ 기본값: Gemini 여성 음성 (나레이션 1명 고정)
                use_gemini_tts = True
                use_google_tts = False
                gemini_voice = "gemini_flash_kore"

        # ★★★ 핵심: 나레이션 음성 고정 (처음부터 끝까지 1명!)
        # UI에서 선택한 음성 또는 기본 Kore
        if selected_voice == "gemini_kore" or selected_voice == "":
            gemini_voice = "gemini_flash_kore"
        elif selected_voice == "gemini_aoede":
            gemini_voice = "gemini_flash_aoede"

        narrator_voice_gemini = gemini_voice
        print(f"[TTSEngine] ★★★ 나레이션 음성 고정: {narrator_voice_gemini} (전체 {len(scenes)}개 씬)")

        # ★ 대사용 음성 설정 (나레이션 여성 → 대사 남성) - 더 이상 사용 안 함
        dialogue_voice_gemini_map = {
            "gemini_flash_kore": "gemini_flash_charon",   # Kore(여성) → Charon(남성)
            "gemini_flash_aoede": "gemini_flash_puck",    # Aoede(여성) → Puck(남성)
        }
        dialogue_voice_gemini = dialogue_voice_gemini_map.get(narrator_voice_gemini, "gemini_flash_charon")

        # ★★★ 이야기 흐름 분석하여 일관된 나레이션 톤 결정
        consistent_narration_tone = self._analyze_story_tone(scenes)
        print(f"[TTSEngine] ★ 나레이션 톤 고정: {consistent_narration_tone} (전체 씬 동일)")

        for idx, scene in enumerate(scenes):
            # ★ 자동 모드 비활성화 - 나레이션은 항상 고정된 음성 사용
            # (씬마다 다른 음성 선택하는 로직 제거)

            # 주인공 대사 음성 설정 (프로필에서 가져오거나 자동 매핑)
            dialogue_voice = profile.extra.get("dialogue_voice")
            if not dialogue_voice and not use_naver_tts and not use_google_tts:
                dialogue_voice = self.DIALOGUE_VOICE_MAP.get(voice, "echo")
            audio_path = os.path.join(output_dir, f"audio_{idx:03d}_{scene.safe_filename_id}.mp3")

            try:
                # ★ 일관된 나레이션 톤 사용 (씬별 emotion_tag 대신)
                narration_tone = consistent_narration_tone
                emotion_profile = EMOTION_TTS_PROFILES.get(narration_tone, EMOTION_TTS_PROFILES["warm"])

                print(f"[TTSEngine] Generating audio for {scene.scene_id}")
                print(f"  Text: {scene.narration[:100]}...")
                print(f"  Tone: {narration_tone} (일관된 나레이션 톤)")

                # [DIALOGUE], [DIALOGUE:M], [DIALOGUE:F] 태그 감지
                has_dialogue = re.search(r'\[DIALOGUE(?::[MF])?\]', scene.narration) and "[/DIALOGUE]" in scene.narration

                if use_gemini_tts:
                    # ★★★ Gemini TTS - 나레이션 고정 + 대사 분리
                    narrator_config = self.GEMINI_TTS_VOICES.get(narrator_voice_gemini, self.GEMINI_TTS_VOICES["gemini_flash_kore"])

                    # [DIALOGUE], [DIALOGUE:M], [DIALOGUE:F] 태그 감지
                    has_dialogue_in_scene = re.search(r'\[DIALOGUE(?::[MF])?\]', scene.narration) and "[/DIALOGUE]" in scene.narration

                    if has_dialogue_in_scene:
                        # ★ 대사 포함: 단일 음성으로 대사 감정 분석
                        print(f"  Voice: {narrator_config['voice']} (단일 음성 + 대사 내용 기반 감정)")
                        self._generate_gemini_tts_with_dialogue(
                            scene.narration, narrator_voice_gemini, dialogue_voice_gemini,
                            audio_path, narration_tone
                        )
                    else:
                        # 대사 없음: 나레이션 음성만 사용
                        print(f"  Voice: {narrator_config['voice']} ({narrator_config['model']}, {narration_tone})")
                        clean_narration = self._clean_text_for_tts(scene.narration)
                        self._generate_gemini_tts(
                            clean_narration, narrator_voice_gemini, audio_path, narration_tone
                        )
                elif use_naver_tts:
                    # 네이버 CLOVA Voice 사용 (감정 프로필 적용)
                    naver_emotion = emotion_profile["naver_params"]
                    print(f"  Voice: {naver_voice} (네이버 CLOVA Voice, {narration_tone})")
                    clean_narration = self._clean_text_for_tts(scene.narration, for_naver=True)
                    self._generate_naver_tts_with_emotion(
                        clean_narration, naver_voice, audio_path,
                        base_speech_speed, naver_emotion
                    )
                elif use_google_tts:
                    # ★★★ Google Cloud TTS - 나레이션 고정 + 대사 분리
                    ssml_params = emotion_profile["google_ssml"]

                    # [DIALOGUE] 태그 감지
                    has_dialogue_in_scene = "[DIALOGUE]" in scene.narration and "[/DIALOGUE]" in scene.narration

                    if has_dialogue_in_scene:
                        # ★ 대사 포함: 나레이션(여성) + 대사(남성) 분리
                        print(f"  Voice: {narrator_voice} (나레이션) / {dialogue_voice_google} (대사)")
                        self._generate_google_tts_with_dialogue(
                            scene.narration, narrator_voice, dialogue_voice_google,
                            audio_path, base_speech_speed, ssml_params
                        )
                    else:
                        # 대사 없음: 나레이션 음성만 사용
                        print(f"  Voice: {narrator_voice} (Google Cloud TTS, {narration_tone})")
                        clean_narration = self._clean_text_for_tts(scene.narration)
                        self._generate_google_tts_with_emotion(
                            clean_narration, narrator_voice, audio_path,
                            base_speech_speed, ssml_params
                        )
                elif has_dialogue and dialogue_voice:
                    # OpenAI TTS + 주인공 대사 분리 (감정 속도 적용)
                    emotion_speed = emotion_profile["openai_speed"]
                    adjusted_speed = base_speech_speed * emotion_speed
                    print(f"  Voice: {voice} (나레이션) / {dialogue_voice} (대사), speed: {adjusted_speed:.2f}")
                    clean_narration = self._remove_emojis(scene.narration)
                    self._generate_audio_with_dialogue(
                        clean_narration, voice, dialogue_voice,
                        audio_path, adjusted_speed
                    )
                else:
                    # OpenAI TTS 단일 음성 (감정별 속도 조절)
                    emotion_speed = emotion_profile["openai_speed"]
                    adjusted_speed = base_speech_speed * emotion_speed
                    print(f"  Voice: {voice}, Speed: {adjusted_speed:.2f} (OpenAI TTS, {narration_tone})")
                    clean_narration = self._clean_text_for_tts(scene.narration)
                    response = self.client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=clean_narration,
                        speed=adjusted_speed
                    )
                    response.stream_to_file(audio_path)

                # 오디오 길이 측정
                duration = self.get_audio_duration(audio_path)

                audio_files.append({
                    "path": audio_path,
                    "duration": duration,
                    "scene_id": scene.scene_id
                })

                print(f"  ✓ Saved: {audio_path} ({duration:.1f}s)")

                # ★ 디버그: TTS 검증 (예상 시간 vs 실제 시간)
                text_len = len(scene.narration)
                expected_duration = text_len / 7.0  # 한국어 약 초당 7자
                ratio = duration / expected_duration if expected_duration > 0 else 1.0
                if ratio < 0.5 or ratio > 2.0:
                    print(f"  ⚠️ TTS 검증 경고: 텍스트 {text_len}자 → 예상 {expected_duration:.0f}초, 실제 {duration:.1f}초 (비율: {ratio:.1f}x)")

            except Exception as e:
                print(f"[TTSEngine] ✗ TTS 실패 - {scene.scene_id}: {e}")
                # ★ TTS 실패 시 즉시 중단 (더미 정보 추가하지 않음)
                raise RuntimeError(f"TTS 생성 실패 ({scene.scene_id}): {e}")

        return audio_files

    def _remove_dialogue_tags(self, text: str) -> str:
        """[DIALOGUE], [DIALOGUE:M], [DIALOGUE:F]...[/DIALOGUE] 태그만 제거하고 내용은 유지"""
        # [DIALOGUE], [DIALOGUE:M], [DIALOGUE:F] 모두 제거
        result = re.sub(r'\[DIALOGUE(?::[MF])?\]', '', text)
        result = re.sub(r'\[/DIALOGUE\]', '', result)
        return result.strip()

    def _remove_emojis(self, text: str) -> str:
        """
        텍스트에서 이모지 제거 (TTS 이상 발음 방지)
        이모지가 TTS에서 '음음' 같은 이상한 소리로 변환되는 것을 방지

        ★ 주의: 한글 범위(U+AC00~U+D7AF)를 포함하지 않도록 주의
        """
        # 이모지 유니코드 범위 제거 (한글 제외)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # 이모티콘
            "\U0001F300-\U0001F5FF"  # 기호 & 픽토그램
            "\U0001F680-\U0001F6FF"  # 교통 & 지도 기호
            "\U0001F1E0-\U0001F1FF"  # 깃발
            "\U00002702-\U000027B0"  # 딩뱃
            # ★ 수정: \U000024C2-\U0001F251 제거 (한글 범위 포함 문제)
            # 대신 안전한 범위만 사용
            "\U0001F910-\U0001F9FF"  # 보조 이모지 (손, 얼굴 등)
            "\U0001FA00-\U0001FA6F"  # 체스 기호
            "\U0001FA70-\U0001FAFF"  # 기호 확장
            "\U00002600-\U000026FF"  # 기타 기호 (☀, ⭐ 등)
            "\U00002700-\U000027BF"  # 딩뱃 기호
            "\U0001F200-\U0001F251"  # 동봉 문자 (🈀 등) - 안전한 범위
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text).strip()

    def _clean_text_for_tts(self, text: str, for_naver: bool = False) -> str:
        """TTS용 텍스트 정리 (태그 제거 + 이모지 제거)"""
        text = self._remove_dialogue_tags(text)
        text = self._remove_emojis(text)

        # ★ "야담." 또는 "야담," 시작 제거 (부자연스러운 발음 방지)
        if text.startswith("야담.") or text.startswith("야담,"):
            text = text[3:].strip()
        elif text.startswith("야담 "):
            text = text[3:].strip()

        if for_naver:
            # 네이버 TTS 특수 처리 (TN 오류 방지)
            # 1. 물결표 제거
            text = text.replace('~', '')
            # 2. 말줄임표 정리 (... → .)
            text = re.sub(r'\.{2,}', '.', text)
            # 3. 반복 구두점 정리
            text = re.sub(r'!{2,}', '!', text)
            text = re.sub(r'\?{2,}', '?', text)
            # 4. 특수 인용 부호 → 일반 인용 부호
            text = text.replace('"', '"').replace('"', '"')
            text = text.replace(''', "'").replace(''', "'")
            # 5. 일부 특수문자 제거
            text = re.sub(r'[★☆●○◆◇■□▲△▼▽♠♣♥♦]', '', text)
            # 6. 빈 괄호 제거
            text = re.sub(r'\(\s*\)', '', text)
            text = re.sub(r'\[\s*\]', '', text)

        # 연속 공백 정리
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_dialogue_segments(self, narration: str) -> List[Tuple[str, str]]:
        """
        나레이션에서 대사 세그먼트 추출 (성별 구분 포함)

        [DIALOGUE:M]남자대사[/DIALOGUE] 또는 [DIALOGUE:F]여자대사[/DIALOGUE] 태그를 파싱
        기존 [DIALOGUE]대사[/DIALOGUE] 형태도 하위 호환 (기본 남자)

        Returns:
            [("narration", 텍스트), ("dialogue_m", 남자대사), ("dialogue_f", 여자대사), ...] 형태의 리스트
        """
        segments = []
        # 성별 표시 포함 패턴: [DIALOGUE:M] 또는 [DIALOGUE:F] 또는 [DIALOGUE]
        pattern = r'\[DIALOGUE(?::([MF]))?\](.*?)\[/DIALOGUE\]'

        last_end = 0
        for match in re.finditer(pattern, narration, re.DOTALL):
            # 대사 전 일반 나레이션
            if last_end < match.start():
                text = narration[last_end:match.start()].strip()
                if text:
                    segments.append(("narration", text))

            # 대사 (성별 구분)
            gender = match.group(1)  # M, F, 또는 None
            dialogue_text = match.group(2).strip()
            if dialogue_text:
                if gender == "F":
                    segments.append(("dialogue_f", dialogue_text))  # 여자 대사
                else:
                    segments.append(("dialogue_m", dialogue_text))  # 남자 대사 (기본)

            last_end = match.end()

        # 마지막 세그먼트 (대사 이후 나레이션)
        if last_end < len(narration):
            text = narration[last_end:].strip()
            if text:
                segments.append(("narration", text))

        # 세그먼트가 없으면 전체를 나레이션으로
        if not segments:
            segments.append(("narration", narration.strip()))

        return segments

    def _generate_audio_with_dialogue(self, narration: str, narrator_voice: str,
                                       dialogue_voice: str, output_path: str, speed: float):
        """
        나레이션과 주인공 대사를 각각 다른 음성으로 생성 후 합치기

        Args:
            narration: [DIALOGUE] 태그가 포함된 나레이션
            narrator_voice: 나레이터 음성
            dialogue_voice: 주인공 대사 음성
            output_path: 출력 파일 경로
            speed: 재생 속도
        """
        segments = self._parse_dialogue_segments(narration)
        temp_files = []

        try:
            print(f"    주인공 대사 분리: {len(segments)}개 세그먼트")

            for idx, (seg_type, text) in enumerate(segments):
                if not text.strip():
                    continue

                # 음성 선택
                voice = dialogue_voice if seg_type == "dialogue" else narrator_voice
                voice_label = "대사" if seg_type == "dialogue" else "나레이션"
                print(f"    [{voice_label}] {voice}: {text[:40]}...")

                # 임시 파일 생성
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"tts_dialogue_{idx}_{hash(text)}.mp3"
                )

                response = self.client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                    speed=speed
                )
                response.stream_to_file(temp_path)
                temp_files.append(temp_path)

            # FFmpeg로 오디오 파일 합치기
            if len(temp_files) == 1:
                import shutil
                shutil.copy(temp_files[0], output_path)
            elif len(temp_files) > 1:
                self._concat_audio_files(temp_files, output_path)
            else:
                # 세그먼트가 없는 경우 빈 파일 방지
                response = self.client.audio.speech.create(
                    model="tts-1",
                    voice=narrator_voice,
                    input=narration,
                    speed=speed
                )
                response.stream_to_file(output_path)

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass

    def get_audio_duration(self, audio_path: str) -> float:
        """
        오디오 파일의 길이를 반환 (ffprobe 사용)

        Args:
            audio_path: 오디오 파일 경로

        Returns:
            길이 (초)
        """
        try:
            # ffprobe로 오디오 길이 측정
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    audio_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                encoding='utf-8',
                errors='replace'
            )
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            print(f"[TTSEngine] Warning: Could not measure audio duration: {e}")
            # Fallback: 나레이션 길이로 대략 추정
            return 10.0  # 기본값

    def _generate_google_tts(self, text: str, voice_name: str, output_path: str, speed: float = 1.0):
        """
        Google Cloud TTS로 음성 생성

        Args:
            text: 변환할 텍스트
            voice_name: 음성 이름 (예: ko-KR-Wavenet-A)
            output_path: 저장 경로
            speed: 재생 속도 (0.25 ~ 4.0)
        """
        if not self.google_client:
            raise Exception("Google Cloud TTS client not initialized")

        # 텍스트 입력 설정
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # 음성 설정
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice_name
        )

        # 오디오 설정
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,  # 재생 속도
            pitch=0.0,  # 음높이 (기본값)
        )

        # TTS 요청
        response = self.google_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # 파일 저장
        with open(output_path, 'wb') as out:
            out.write(response.audio_content)

    def generate_multi_narrator_audio(self, scenes: List[Scene], profile: ContentProfile,
                                       output_dir: str) -> List[Dict[str, any]]:
        """
        다중 화자 오디오 생성 (역사 모드용)

        나레이션에 [NARRATOR1], [NARRATOR2] 태그가 있으면 해당 화자 음성으로 생성
        태그가 없으면 기본 화자(narrator1) 사용

        Args:
            scenes: Scene 리스트
            profile: 컨텐츠 프로필
            output_dir: 오디오 파일 저장 디렉토리

        Returns:
            오디오 정보 리스트
        """
        if not self.enabled:
            print("[TTSEngine] Skipping audio generation (API not configured)")
            return []

        os.makedirs(output_dir, exist_ok=True)
        audio_files = []

        # 화자별 음성 선택 (GPT 기반)
        narrator_voices = self._select_voices_with_gpt(profile)
        print(f"[TTSEngine] 다중 화자 모드: {narrator_voices}")

        for idx, scene in enumerate(scenes):
            audio_path = os.path.join(output_dir, f"audio_{idx:03d}_{scene.safe_filename_id}.mp3")

            try:
                print(f"[TTSEngine] Generating multi-narrator audio for {scene.scene_id}")

                # 나레이션에서 화자별 세그먼트 추출
                segments = self._parse_narrator_segments(scene.narration)

                if len(segments) == 1 and segments[0][0] is None:
                    # 단일 화자 (태그 없음) - 기본 화자 사용
                    voice = narrator_voices.get("narrator1", "onyx")
                    print(f"  단일 화자: {voice}")
                    print(f"  Text: {scene.narration[:100]}...")

                    response = self.client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=scene.narration,
                        speed=profile.speech_speed
                    )
                    response.stream_to_file(audio_path)
                else:
                    # 다중 화자 - 각 세그먼트별로 생성 후 합치기
                    print(f"  다중 화자: {len(segments)}개 세그먼트")
                    self._generate_multi_segment_audio(
                        segments, narrator_voices, audio_path, profile.speech_speed
                    )

                duration = self.get_audio_duration(audio_path)
                audio_files.append({
                    "path": audio_path,
                    "duration": duration,
                    "scene_id": scene.scene_id
                })
                print(f"  ✓ Saved: {audio_path} ({duration:.1f}s)")

                # ★ 디버그: TTS 검증 (예상 시간 vs 실제 시간)
                text_len = len(scene.narration)
                expected_duration = text_len / 7.0  # 한국어 약 초당 7자
                ratio = duration / expected_duration if expected_duration > 0 else 1.0
                if ratio < 0.5 or ratio > 2.0:
                    print(f"  ⚠️ TTS 검증 경고: 텍스트 {text_len}자 → 예상 {expected_duration:.0f}초, 실제 {duration:.1f}초 (비율: {ratio:.1f}x)")

            except Exception as e:
                print(f"[TTSEngine] ✗ TTS 실패 - {scene.scene_id}: {e}")
                # ★ TTS 실패 시 즉시 중단 (더미 정보 추가하지 않음)
                raise RuntimeError(f"TTS 생성 실패 ({scene.scene_id}): {e}")

        return audio_files

    def _parse_narrator_segments(self, narration: str) -> List[Tuple[str, str]]:
        """
        나레이션에서 화자별 세그먼트 추출

        [NARRATOR1] 텍스트...
        [NARRATOR2] 텍스트...

        Returns:
            [(narrator_id, text), ...] 형태의 리스트
            narrator_id가 None이면 기본 화자
        """
        # 화자 태그 패턴
        pattern = r'\[NARRATOR([12])\]\s*'

        segments = []
        last_end = 0
        current_narrator = None

        for match in re.finditer(pattern, narration):
            # 이전 세그먼트 저장
            if last_end < match.start():
                text = narration[last_end:match.start()].strip()
                if text:
                    segments.append((current_narrator, text))

            current_narrator = f"narrator{match.group(1)}"
            last_end = match.end()

        # 마지막 세그먼트
        if last_end < len(narration):
            text = narration[last_end:].strip()
            if text:
                segments.append((current_narrator, text))

        # 세그먼트가 없으면 전체를 하나의 세그먼트로
        if not segments:
            segments.append((None, narration.strip()))

        return segments

    def _generate_multi_segment_audio(self, segments: List[Tuple[str, str]],
                                       narrator_voices: Dict[str, str],
                                       output_path: str, speed: float):
        """
        여러 화자의 세그먼트를 각각 생성하고 하나로 합치기

        Args:
            segments: [(narrator_id, text), ...] 리스트
            narrator_voices: {"narrator1": "onyx", "narrator2": "nova"} 형태
            output_path: 최종 출력 경로
            speed: 재생 속도
        """
        temp_files = []

        try:
            # 각 세그먼트별 오디오 생성
            for idx, (narrator_id, text) in enumerate(segments):
                if not text.strip():
                    continue

                # 화자 음성 선택
                voice = narrator_voices.get(narrator_id, narrator_voices.get("narrator1", "onyx"))
                print(f"    [{narrator_id or 'default'}] {voice}: {text[:50]}...")

                # 임시 파일 생성
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"tts_segment_{idx}_{hash(text)}.mp3"
                )

                response = self.client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                    speed=speed
                )
                response.stream_to_file(temp_path)
                temp_files.append(temp_path)

            # FFmpeg로 오디오 파일 합치기
            if len(temp_files) == 1:
                # 하나뿐이면 그냥 복사
                import shutil
                shutil.copy(temp_files[0], output_path)
            else:
                self._concat_audio_files(temp_files, output_path)

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass

    def _concat_audio_files(self, audio_files: List[str], output_path: str):
        """
        여러 오디오 파일을 하나로 합치기 (FFmpeg concat)

        Args:
            audio_files: 오디오 파일 경로 리스트
            output_path: 출력 경로
        """
        # concat 파일 생성
        concat_file = os.path.join(tempfile.gettempdir(), f"concat_{hash(str(audio_files))}.txt")
        with open(concat_file, 'w') as f:
            for audio_file in audio_files:
                f.write(f"file '{audio_file}'\n")

        try:
            subprocess.run([
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',
                output_path
            ], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        finally:
            if os.path.exists(concat_file):
                os.remove(concat_file)

    def _generate_naver_tts(self, text: str, voice_name: str, output_path: str, speed: float = 1.0):
        """
        네이버 CLOVA Voice API로 음성 생성

        Args:
            text: 변환할 텍스트
            voice_name: 음성 이름 (예: nara, nminsang, ndain 등)
            output_path: 저장 경로
            speed: 재생 속도 (-5 ~ 5, 기본 0) -> 0.5~2.0 스케일을 -5~5로 변환
        """
        if not self.naver_enabled:
            raise Exception("네이버 CLOVA Voice API not configured")

        # 속도 변환: 0.5~2.0 -> -5~5
        # 1.0 = 0, 0.5 = -5, 2.0 = 5
        naver_speed = int((speed - 1.0) * 10)
        naver_speed = max(-5, min(5, naver_speed))

        # API 요청
        url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.naver_client_id,
            "X-NCP-APIGW-API-KEY": self.naver_client_secret,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "speaker": voice_name,
            "text": text,
            "volume": 0,  # -5 ~ 5
            "speed": naver_speed,
            "pitch": 0,   # -5 ~ 5
            "format": "mp3"
        }

        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
        else:
            raise Exception(f"네이버 TTS API 에러: {response.status_code} - {response.text}")

    def _generate_naver_tts_with_emotion(self, text: str, voice_name: str, output_path: str,
                                          speed: float, emotion_params: dict):
        """
        ★ Emotion TTS: 네이버 CLOVA Voice API로 감정 적용 음성 생성

        Args:
            text: 변환할 텍스트
            voice_name: 음성 이름
            output_path: 저장 경로
            speed: 기본 재생 속도
            emotion_params: 감정 파라미터 {"speed": -1, "pitch": -1, "volume": 0}
        """
        if not self.naver_enabled:
            raise Exception("네이버 CLOVA Voice API not configured")

        # 기본 속도에 감정 속도 조정 적용
        base_speed = int((speed - 1.0) * 10)
        final_speed = max(-5, min(5, base_speed + emotion_params.get("speed", 0)))
        final_pitch = max(-5, min(5, emotion_params.get("pitch", 0)))
        final_volume = max(-5, min(5, emotion_params.get("volume", 0)))

        url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
        headers = {
            "X-NCP-APIGW-API-KEY-ID": self.naver_client_id,
            "X-NCP-APIGW-API-KEY": self.naver_client_secret,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "speaker": voice_name,
            "text": text,
            "volume": final_volume,
            "speed": final_speed,
            "pitch": final_pitch,
            "format": "mp3"
        }

        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
        else:
            raise Exception(f"네이버 TTS API 에러: {response.status_code} - {response.text}")

    def _generate_google_tts_with_dialogue(self, narration: str, narrator_voice: str,
                                            dialogue_voice: str, output_path: str,
                                            speed: float, ssml_params: dict):
        """
        ★★★ Google TTS: 나레이션과 대사를 각각 다른 음성으로 생성 후 합치기

        Args:
            narration: [DIALOGUE] 태그가 포함된 나레이션
            narrator_voice: 나레이터 음성 (여성)
            dialogue_voice: 대사 음성 (남성)
            output_path: 출력 파일 경로
            speed: 재생 속도
            ssml_params: SSML 파라미터
        """
        if not self.google_client:
            raise Exception("Google Cloud TTS client not initialized")

        segments = self._parse_dialogue_segments(narration)
        temp_files = []

        try:
            print(f"    ★ Google TTS 대사 분리: {len(segments)}개 세그먼트")

            for idx, (seg_type, text) in enumerate(segments):
                if not text.strip():
                    continue

                # 음성 선택: 대사면 남성, 나레이션이면 여성
                voice_name = dialogue_voice if seg_type == "dialogue" else narrator_voice
                voice_label = "대사" if seg_type == "dialogue" else "나레이션"
                print(f"    [{voice_label}] {voice_name}: {text[:40]}...")

                # 임시 파일 생성
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"google_tts_{idx}_{hash(text)}.mp3"
                )

                # SSML 생성
                rate = ssml_params.get("rate", "medium")
                pitch = ssml_params.get("pitch", "0st")
                volume = ssml_params.get("volume", "medium")

                # 대사는 약간 다른 톤으로
                if seg_type == "dialogue":
                    pitch = "+1st"  # 대사는 약간 높은 톤

                ssml_text = f"""<speak>
<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
{text}
</prosody>
</speak>"""

                # SSML 입력 설정
                synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)

                # 음성 설정
                voice = texttospeech.VoiceSelectionParams(
                    language_code="ko-KR",
                    name=voice_name
                )

                # 오디오 설정
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=speed,
                )

                # TTS 요청
                response = self.google_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )

                # 임시 파일 저장
                with open(temp_path, 'wb') as f:
                    f.write(response.audio_content)
                temp_files.append(temp_path)

            # 세그먼트 합치기 (FFmpeg concat)
            if len(temp_files) > 1:
                # concat 리스트 파일 생성
                concat_list = os.path.join(tempfile.gettempdir(), f"concat_{hash(narration)}.txt")
                with open(concat_list, 'w', encoding='utf-8') as f:
                    for temp_path in temp_files:
                        f.write(f"file '{temp_path}'\n")

                # FFmpeg로 합치기
                subprocess.run([
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', concat_list, '-c', 'copy', output_path
                ], capture_output=True, check=True)

                os.remove(concat_list)
            elif len(temp_files) == 1:
                # 세그먼트 하나면 그냥 복사
                import shutil
                shutil.copy(temp_files[0], output_path)

        finally:
            # 임시 파일 정리
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass

    def _generate_google_tts_with_emotion(self, text: str, voice_name: str, output_path: str,
                                           speed: float, ssml_params: dict):
        """
        ★ Emotion TTS: Google Cloud TTS로 SSML 감정 적용 음성 생성

        Args:
            text: 변환할 텍스트
            voice_name: 음성 이름 (예: ko-KR-Wavenet-A)
            output_path: 저장 경로
            speed: 기본 재생 속도
            ssml_params: SSML 파라미터 {"rate": "slow", "pitch": "-1st", "volume": "medium"}
        """
        if not self.google_client:
            raise Exception("Google Cloud TTS client not initialized")

        # SSML 생성
        rate = ssml_params.get("rate", "medium")
        pitch = ssml_params.get("pitch", "0st")
        volume = ssml_params.get("volume", "medium")

        ssml_text = f"""<speak>
<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">
{text}
</prosody>
</speak>"""

        # SSML 입력 설정
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)

        # 음성 설정
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice_name
        )

        # 오디오 설정
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
        )

        # TTS 요청
        response = self.google_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # 파일 저장
        with open(output_path, 'wb') as out:
            out.write(response.audio_content)

    def _analyze_scene_context(self, scene: Scene, profile: ContentProfile) -> dict:
        """
        Scene과 Profile을 분석하여 라우팅에 필요한 컨텍스트 추출

        Returns:
            {
                "mode": "history" | "kids" | "lecture" | ...,
                "has_dialogue": True | False,
                "emotion_tag": "warm" | "serious" | ...,
                "emotion_intensity": "high" | "serious" | "normal",
                "text_length": "short" | "medium" | "long"
            }
        """
        # 1. 컨텐츠 모드 (profile.mode_id 우선, category 폴백)
        mode = getattr(profile, 'mode_id', '') or profile.category or ""
        # mode_id에서 카테고리 추출 (예: "yadam_kr_v1" → "yadam")
        if mode and "_" in mode:
            mode_category = mode.split("_")[0]
        else:
            mode_category = mode
        mode = mode_category or profile.extra.get("mode", "")

        # 2. 대사 유무
        has_dialogue = "[DIALOGUE]" in scene.narration and "[/DIALOGUE]" in scene.narration

        # 3. 감정 태그 및 강도
        emotion_tag = getattr(scene, 'emotion_tag', 'warm')
        emotion_intensity = EMOTION_INTENSITY.get(emotion_tag, "normal")

        # 4. 텍스트 길이 (한국어 기준)
        text_len = len(scene.narration)
        if text_len < 100:
            text_length = "short"
        elif text_len < 300:
            text_length = "medium"
        else:
            text_length = "long"

        return {
            "mode": mode,
            "has_dialogue": has_dialogue,
            "emotion_tag": emotion_tag,
            "emotion_intensity": emotion_intensity,
            "text_length": text_length
        }

    def _select_tts_for_scene(self, scene: Scene, profile: ContentProfile) -> Tuple[str, str]:
        """
        ★ TTS Model Router v0.2: 상황별 최적 엔진 라우팅

        설계 원칙:
        1. 상황 분석 → 최적 엔진 하나를 결정 (리스트 순회 아님)
        2. 선택된 엔진이 사용 불가할 때만 폴백
        3. 모드 > 대사 > 감정 순으로 결정 요인 적용

        Args:
            scene: 현재 장면
            profile: 컨텐츠 프로필

        Returns:
            (selected_voice, reason) 튜플
        """
        # 1. 사용 가능한 엔진 확인 (★ Naver/OpenAI 비활성화 - Gemini/Google만 사용)
        available_engines = []
        if self.gemini_tts_enabled:  # Gemini TTS (우선순위 높음)
            available_engines.append("gemini")
        # ★ OpenAI TTS 비활성화 (자동 모드에서 제외)
        # if self.enabled:  # OpenAI
        #     available_engines.append("openai")
        # ★ Naver TTS 비활성화 (자동 모드에서 제외)
        # if self.naver_enabled:
        #     available_engines.append("naver")
        if self.google_client:
            available_engines.append("google")

        if not available_engines:
            return ("alloy", "기본값 (사용 가능한 엔진 없음)")

        # 2. 컨텍스트 분석
        ctx = self._analyze_scene_context(scene, profile)

        # 3. 최적 엔진 결정 (우선순위: 모드 > 대사 > 감정)
        optimal_engine = None
        reason = ""

        # 3-1. 모드 기반 결정
        if ctx["mode"] and ctx["mode"] in TTS_OPTIMAL_ENGINE:
            optimal_engine = TTS_OPTIMAL_ENGINE[ctx["mode"]]
            reason = f"모드({ctx['mode']}) → {optimal_engine}"

        # 3-2. 대사 유무 기반 결정
        elif ctx["has_dialogue"]:
            optimal_engine = TTS_OPTIMAL_ENGINE.get("has_dialogue", "openai")
            reason = f"대사 포함 → {optimal_engine} (다중 음성)"

        # 3-3. 감정 강도 기반 결정
        else:
            intensity_key = f"emotion_{ctx['emotion_intensity']}"
            optimal_engine = TTS_OPTIMAL_ENGINE.get(intensity_key, TTS_OPTIMAL_ENGINE["default"])
            reason = f"감정({ctx['emotion_tag']}/{ctx['emotion_intensity']}) → {optimal_engine}"

        # 4. 가용성 체크 및 폴백
        if optimal_engine not in available_engines:
            # 선택된 엔진이 사용 불가 → 폴백
            fallback_engine = available_engines[0]
            reason = f"{reason} [불가→{fallback_engine} 폴백]"
            optimal_engine = fallback_engine

        # 5. 엔진 내 세부 음성 선택
        voice = self._select_voice_for_engine(optimal_engine, ctx)

        return (voice, reason)

    def _select_voice_for_engine(self, engine: str, ctx: dict) -> str:
        """
        선택된 엔진 내에서 상황에 맞는 세부 음성 선택
        ★ 나레이션은 항상 일관된 목소리, 대사만 다른 목소리로

        Args:
            engine: "openai" | "naver" | "google" | "gemini"
            ctx: 컨텍스트 딕셔너리

        Returns:
            음성 ID (예: "nova", "naver_nara", "google_wavenet_a", "Kore")
        """
        # ★ 나레이션 목소리는 항상 일관되게 유지 (감정에 따라 바뀌지 않음)
        # 대사([DIALOGUE])만 다른 목소리로 처리 (DIALOGUE_VOICE_MAP 사용)
        # Gemini 여성 음성
        if engine == "gemini":
            # ★ 나레이션은 항상 Kore로 고정 (일관성 유지)
            return "Kore"  # 부드러운 여성 (기본)

        # Google 여성 음성
        if engine == "google":
            return "google_wavenet_a"  # 한국어 여성 (Wavenet-A)

        # OpenAI 여성 음성 (폴백용)
        # ★ 나레이션은 항상 nova로 고정 (일관성 유지)
        if engine == "openai":
            return "nova"  # 따뜻한 여성 (기본)

        # Naver 여성 음성 (폴백용)
        if engine == "naver":
            return "naver_nara"  # 고운 여성

        # 기본값 (여성)
        return "nova"

    def _select_voices_with_gpt(self, profile: ContentProfile) -> Dict[str, str]:
        """
        GPT를 사용하여 화자별 최적 음성 선택

        역사 모드에서는 콘텐츠 특성에 맞는 음성을 GPT가 추천

        Args:
            profile: 컨텐츠 프로필

        Returns:
            {"narrator1": "onyx", "narrator2": "nova"} 형태
        """
        narrators_config = profile.extra.get("narrators", {})

        if not narrators_config:
            return self.HISTORY_DEFAULT_VOICES.copy()

        # GPT API로 음성 추천 받기
        try:
            voice_options = list(self.OPENAI_VOICE_CHARACTERISTICS.keys())
            voice_info = "\n".join([
                f"- {name}: {info['gender']}, {info['tone']} tone, {info['style']} style"
                for name, info in self.OPENAI_VOICE_CHARACTERISTICS.items()
            ])

            prompt = f"""당신은 TTS 음성 전문가입니다.
다음 화자 설정에 가장 적합한 OpenAI TTS 음성을 선택해주세요.

화자 설정:
"""
            for narrator_id, config in narrators_config.items():
                prompt += f"- {narrator_id}: 성별={config.get('gender', 'unknown')}, 역할={config.get('role', 'narrator')}, 설명={config.get('description', '')}\n"

            prompt += f"""
사용 가능한 음성:
{voice_info}

JSON 형식으로만 응답하세요:
{{"narrator1": "음성이름", "narrator2": "음성이름"}}
"""
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3
            )

            import json
            result_text = response.choices[0].message.content.strip()
            # JSON 파싱
            result_text = re.sub(r'```json\s*', '', result_text)
            result_text = re.sub(r'```\s*', '', result_text)
            voices = json.loads(result_text)

            # 유효성 검사
            validated = {}
            for narrator_id, voice in voices.items():
                if voice in voice_options:
                    validated[narrator_id] = voice
                else:
                    validated[narrator_id] = self.HISTORY_DEFAULT_VOICES.get(narrator_id, "onyx")

            print(f"[TTSEngine] GPT 음성 선택: {validated}")
            return validated

        except Exception as e:
            print(f"[TTSEngine] GPT 음성 선택 실패: {e}, 기본값 사용")
            return self.HISTORY_DEFAULT_VOICES.copy()

    def _analyze_dialogue_emotion(self, dialogue_text: str) -> str:
        """
        대사 내용을 분석하여 적절한 감정 결정

        Args:
            dialogue_text: 대사 텍스트

        Returns:
            str: 감정 태그 (excited, sad, serious, warm, calm)
        """
        text = dialogue_text.lower()

        # 분노/강한 감정 키워드
        angry_keywords = ["화", "분노", "어떻게", "왜", "안돼", "못해", "죽", "놈",
                         "이놈", "저놈", "꺼져", "닥쳐", "감히", "뭐라고", "대체"]

        # 슬픔/간청 키워드
        sad_keywords = ["울", "눈물", "슬", "부탁", "제발", "살려", "미안", "용서",
                       "그리워", "보고싶", "왜 이런", "어쩌면", "힘들", "아프"]

        # 기쁨/신남 키워드
        excited_keywords = ["기쁘", "좋아", "잘됐", "해냈", "고마", "감사", "축하",
                          "대단", "놀라", "정말", "드디어", "바로", "오"]

        # 두려움/걱정 키워드
        fear_keywords = ["무서", "두려", "걱정", "조심", "위험", "도망", "숨어",
                        "어떡해", "큰일", "안돼"]

        # 진지/엄숙 키워드
        serious_keywords = ["명심", "잊지", "반드시", "꼭", "절대", "중요", "진실",
                          "비밀", "약속", "맹세"]

        # 키워드 매칭
        angry_count = sum(1 for kw in angry_keywords if kw in text)
        sad_count = sum(1 for kw in sad_keywords if kw in text)
        excited_count = sum(1 for kw in excited_keywords if kw in text)
        fear_count = sum(1 for kw in fear_keywords if kw in text)
        serious_count = sum(1 for kw in serious_keywords if kw in text)

        # 문장 부호로 추가 판단
        if text.endswith("!") or "!" in text:
            excited_count += 1
        if text.endswith("?") or "?" in text:
            # 질문은 상황에 따라 다름
            pass

        # 가장 많이 매칭된 감정 선택
        emotion_scores = {
            "excited": angry_count + excited_count,  # 강한 감정은 excited로
            "sad": sad_count + fear_count,  # 슬픔/두려움은 sad로
            "serious": serious_count,  # 진지함
            "warm": 0  # 기본값
        }

        max_emotion = max(emotion_scores, key=emotion_scores.get)

        # 매칭된 게 없으면 기본값 warm
        if emotion_scores[max_emotion] == 0:
            return "warm"

        return max_emotion

    def _generate_gemini_tts_with_dialogue(self, narration: str, narrator_voice: str,
                                            dialogue_voice_m: str, audio_path: str,
                                            emotion_tag: str = "warm"):
        """
        ★★★ Gemini TTS: 나레이션 1명이 모든 걸 하되, 대사는 내용 기반 감정

        Args:
            narration: [DIALOGUE:M] 또는 [DIALOGUE:F] 태그가 포함된 나레이션
            narrator_voice: 나레이터 음성 (여성 - Kore/Aoede) - 모든 파트에 사용
            dialogue_voice_m: (사용 안 함 - 호환성 유지용)
            audio_path: 출력 파일 경로
            emotion_tag: 나레이션 감정 태그
        """
        segments = self._parse_dialogue_segments(narration)
        temp_files = []

        # ★ 단일 음성: 나레이터가 모든 파트를 연기
        # 대사는 내용을 분석하여 적절한 감정으로 표현

        try:
            print(f"    ★ Gemini TTS 단일 음성 연기: {len(segments)}개 세그먼트")

            for idx, (seg_type, text) in enumerate(segments):
                if not text.strip():
                    continue

                # ★ 모든 파트에 동일한 나레이터 음성 사용
                voice_id = narrator_voice

                # ★ 대사는 내용 분석하여 감정 결정 (남녀 구분 없음)
                if seg_type in ["dialogue_m", "dialogue_f", "dialogue"]:
                    segment_emotion = self._analyze_dialogue_emotion(text)
                    voice_label = "대사"
                else:
                    segment_emotion = emotion_tag  # 나레이션 → 일관된 톤 유지
                    voice_label = "나레이션"

                voice_config = self.GEMINI_TTS_VOICES.get(voice_id, self.GEMINI_TTS_VOICES["gemini_flash_kore"])
                print(f"    [{voice_label}] {voice_config['voice']} ({segment_emotion}): {text[:40]}...")

                # 임시 파일 생성
                temp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"gemini_tts_{idx}_{hash(text)}.mp3"
                )

                # Gemini TTS로 생성 (감정 다르게)
                self._generate_gemini_tts(text, voice_id, temp_path, segment_emotion)
                temp_files.append(temp_path)

            # 세그먼트 합치기 (FFmpeg concat)
            if len(temp_files) > 1:
                # concat 리스트 파일 생성
                concat_list = os.path.join(tempfile.gettempdir(), f"concat_gemini_{hash(narration)}.txt")
                with open(concat_list, 'w', encoding='utf-8') as f:
                    for temp_path in temp_files:
                        f.write(f"file '{temp_path}'\n")

                # FFmpeg로 합치기
                subprocess.run([
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', concat_list, '-c', 'copy', audio_path
                ], capture_output=True, check=True)

                os.remove(concat_list)
            elif len(temp_files) == 1:
                # 세그먼트 하나면 그냥 복사
                import shutil
                shutil.copy(temp_files[0], audio_path)

        finally:
            # 임시 파일 정리
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass

    def _generate_gemini_tts(self, text: str, voice_id: str, output_path: str, emotion_tag: str = "warm"):
        """
        Gemini TTS (gemini-2.5-flash-tts, gemini-2.5-pro-tts)로 음성 생성

        Args:
            text: 변환할 텍스트
            voice_id: 음성 ID (예: gemini_flash_puck, gemini_pro_kore)
            output_path: 저장 경로
            emotion_tag: 감정 태그 (warm, serious, excited, sad, calm)

        Returns:
            저장된 파일 경로
        """
        if not self.gemini_tts_enabled:
            raise Exception("Gemini TTS not configured (GEMINI_TTS_API_KEY 또는 GEMINI_API_KEY 필요)")

        try:
            from google import genai
            from google.genai import types

            # 음성 설정 가져오기
            voice_config = self.GEMINI_TTS_VOICES.get(voice_id)
            if not voice_config:
                # 기본값 사용
                voice_config = self.GEMINI_TTS_VOICES.get("gemini_flash_puck")

            model_name = voice_config["model"]
            voice_name = voice_config["voice"]

            # 감정에 따른 영어 톤 설정 (Gemini TTS용)
            # ★ 중요: 텍스트를 정확하게 읽도록 "Read aloud exactly" 형식 사용
            emotion_tones = {
                "warm": "warm and gentle",
                "serious": "serious and calm",
                "excited": "bright and energetic",
                "sad": "emotional and soft",
                "calm": "peaceful and steady"
            }
            tone = emotion_tones.get(emotion_tag, emotion_tones["warm"])

            # Gemini TTS 클라이언트 생성
            client = genai.Client(api_key=self.gemini_api_key)

            # TTS 요청 - 텍스트를 정확하게 읽도록 명시
            # ★ "Read aloud exactly as written" 형식으로 텍스트 변형 방지
            prompt = f"Read aloud the following Korean text exactly as written, in a {tone} tone:\n\n{text}"

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name
                            )
                        )
                    )
                )
            )

            # 응답에서 오디오 데이터 추출
            if response.candidates and len(response.candidates) > 0:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        audio_data = part.inline_data.data
                        mime_type = getattr(part.inline_data, 'mime_type', 'audio/pcm')

                        import tempfile
                        import wave
                        import struct

                        # Gemini TTS는 raw PCM (24kHz, 16-bit, mono)을 반환
                        if 'pcm' in mime_type.lower() or mime_type == 'audio/L16':
                            # PCM 데이터를 WAV 형식으로 변환
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                                wav_path = wav_file.name

                            # WAV 파일 생성 (PCM 24kHz, 16-bit, mono)
                            with wave.open(wav_path, 'wb') as wav:
                                wav.setnchannels(1)  # mono
                                wav.setsampwidth(2)  # 16-bit
                                wav.setframerate(24000)  # 24kHz (Gemini TTS 기본)
                                wav.writeframes(audio_data)
                        else:
                            # 다른 포맷 (이미 WAV 등)은 그대로 저장
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                                wav_file.write(audio_data)
                                wav_path = wav_file.name

                        # FFmpeg로 MP3 변환
                        subprocess.run([
                            'ffmpeg', '-y',
                            '-i', wav_path,
                            '-codec:a', 'libmp3lame',
                            '-q:a', '2',
                            output_path
                        ], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

                        # 임시 WAV 파일 삭제
                        os.remove(wav_path)

                        # ★ 오디오 길이 검증: 예상 길이 대비 확인
                        try:
                            actual_duration = self.get_audio_duration(output_path)
                            expected_duration = len(text) / 7.0  # 한글 약 7자/초
                            max_allowed_duration = expected_duration * 1.8  # 최대 허용: 예상의 1.8배

                            # 실제 길이가 예상의 2배 이상이면 Gemini가 텍스트 확장했을 가능성
                            if actual_duration > expected_duration * 2:
                                print(f"  ⚠ 오디오 길이 비정상: 실제 {actual_duration:.1f}초 vs 예상 {expected_duration:.1f}초")
                                print(f"  ⚠ 오디오를 {max_allowed_duration:.1f}초로 트리밍합니다...")

                                # FFmpeg로 오디오 트리밍 (최대 허용 길이로 자르기)
                                trimmed_path = output_path + ".trimmed.mp3"
                                subprocess.run([
                                    'ffmpeg', '-y',
                                    '-i', output_path,
                                    '-t', str(max_allowed_duration),
                                    '-codec:a', 'libmp3lame', '-q:a', '2',
                                    trimmed_path
                                ], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')

                                # 트리밍된 파일로 교체
                                os.remove(output_path)
                                os.rename(trimmed_path, output_path)

                                trimmed_duration = self.get_audio_duration(output_path)
                                print(f"  ✓ 트리밍 완료: {trimmed_duration:.1f}초")

                        except Exception as e:
                            print(f"  ⚠ 오디오 길이 검증 실패: {e}")

                        print(f"  ✓ Gemini TTS ({voice_name}) saved: {output_path}")
                        return output_path

            raise Exception("Gemini TTS 응답에 오디오 데이터 없음")

        except ImportError:
            raise Exception("google-genai 패키지가 필요합니다. pip install google-genai")
        except Exception as e:
            print(f"  ✗ Gemini TTS error: {e}")
            raise
