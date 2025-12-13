import os
import re
import requests
from typing import List
import google.generativeai as genai
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from models.types import Scene
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import base64
import io
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from engines.utils.google_auth import GoogleAuthManager


# ★ DALL-E 프롬프트 순화 함수 - content_policy_violation 방지
def sanitize_for_dalle(prompt: str, aggressive: bool = False) -> str:
    """
    DALL-E에 전달하기 전 프롬프트를 순화합니다.
    - [DIALOGUE]...[/DIALOGUE] 태그 제거
    - 폭력적/선정적 단어 순화
    - 너무 긴 프롬프트 요약

    Args:
        prompt: 원본 이미지 프롬프트
        aggressive: True면 더 강력하게 순화 (content_policy_violation 재시도용)

    Returns:
        순화된 프롬프트
    """
    if not prompt:
        return prompt

    # 1. [DIALOGUE]...[/DIALOGUE] 태그 및 내용 제거
    prompt = re.sub(r'\[DIALOGUE\].*?\[/DIALOGUE\]', '', prompt, flags=re.DOTALL)

    # 2. 폭력/선정적 단어 → 순화어로 대체
    sanitize_map = {
        # 폭력 관련
        '피': 'red liquid',
        '피투성이': 'injured',
        '피가 낭자': 'chaotic scene',
        '살인': 'conflict',
        '살해': 'conflict',
        '죽이': 'defeat',
        '죽음': 'ending',
        '시체': 'fallen figure',
        '송장': 'fallen figure',
        '목을 베': 'defeated',
        '참수': 'defeat',
        '처형': 'punishment',
        '고문': 'interrogation',
        '잔혹': 'intense',
        '잔인': 'dramatic',
        '무참히': 'completely',
        '피범벅': 'aftermath',
        '피바다': 'aftermath scene',
        '학살': 'battle',
        '도륙': 'conflict',
        # 무기 관련 (완화)
        '칼로 찌르': 'strike',
        '칼에 맞': 'struck',
        '칼을 휘두': 'swing weapon',
        # 공포 관련
        '귀신': 'mysterious spirit',
        '원귀': 'spirit',
        '악귀': 'dark spirit',
        '저주': 'mystery',
        '무덤': 'resting place',
        # 선정적 관련
        '벌거벗': 'unclothed figure (artistic)',
        '나체': 'figure',
        '알몸': 'figure',
        # ★ 학대/폭력 관련 추가 (content_policy_violation 방지)
        '학대': 'hardship',
        '폭행': 'conflict',
        '구타': 'conflict',
        '때리': 'struggle',
        '맞': 'struggle',
        '가두': 'confine',
        '감금': 'isolation',
        '창고에 가두': 'isolated in room',
        '지하 창고': 'dark room',
        '마귀': 'troubled',
        '미쳤': 'troubled',
        '미친': 'troubled',
        '밀쳐': 'pushed',
        '넘어지': 'fell down',
        '멍': 'mark',
        '상처': 'mark',
        '피멍': 'bruise mark',
        '굶기': 'deprived',
        '굶주': 'hungry',
    }

    for bad_word, safe_word in sanitize_map.items():
        prompt = prompt.replace(bad_word, safe_word)

    # 3. 영어 폭력 단어도 순화
    english_sanitize = {
        'blood': 'red color',
        'bloody': 'dramatic',
        'gore': 'aftermath',
        'gory': 'intense',
        'death': 'ending',
        'dead': 'fallen',
        'kill': 'defeat',
        'murder': 'conflict',
        'corpse': 'fallen figure',
        'decapitate': 'defeat',
        'torture': 'interrogation',
        'naked': 'figure',
        'nude': 'figure',
        # ★ 학대/폭력 관련 추가
        'abuse': 'hardship',
        'abused': 'troubled',
        'beat': 'conflict',
        'beaten': 'hurt',
        'hit': 'strike',
        'punch': 'strike',
        'slap': 'strike',
        'bruise': 'mark',
        'wound': 'mark',
        'imprison': 'confine',
        'lock': 'confine',
        'cage': 'room',
        'starve': 'hungry',
        'suffer': 'endure',
        'suffering': 'hardship',
        'terrified': 'worried',
        'terror': 'fear',
        'scream': 'cry',
        'cry': 'emotional',
    }

    # 대소문자 구분 없이 치환
    for bad_word, safe_word in english_sanitize.items():
        prompt = re.sub(rf'\b{bad_word}\b', safe_word, prompt, flags=re.IGNORECASE)

    # ★ aggressive 모드: 더 강력하게 순화 (content_policy_violation 재시도용)
    if aggressive:
        # 감정적/부정적 단어 제거
        aggressive_remove = [
            'gaunt', 'sunken', 'pale', 'hollow', 'trembling', 'shaking',
            'fear', 'scared', 'frightened', 'anxious', 'nervous',
            'dark', 'shadow', 'sinister', 'ominous', 'menacing',
            'victim', 'helpless', 'vulnerable', 'weak', 'frail',
            'desperate', 'despair', 'hopeless', 'miserable', 'wretched',
        ]
        for word in aggressive_remove:
            prompt = re.sub(rf'\b{word}\b', '', prompt, flags=re.IGNORECASE)

    # 4. 중복 공백 제거
    prompt = re.sub(r'\s+', ' ', prompt).strip()

    # 5. 너무 긴 경우 요약 (4000자 제한)
    if len(prompt) > 3500:
        prompt = prompt[:3500] + "..."

    return prompt


def ensure_dict(value, default=None):
    """
    값이 dict인지 확인하고, 아니면 기본값 반환.
    'str' object has no attribute 'get' 에러 방지용.
    """
    if default is None:
        default = {}
    return value if isinstance(value, dict) else default


# ★ Model Router v0.1 - 자동 모델 선택 규칙
MODEL_ROUTING_RULES = {
    # model_hint 값 → 실제 모델 ID
    "auto": None,  # 자동 선택 (아래 규칙 적용)
    "imagen3": "gemini_flash",  # Imagen 3
    "dalle3": "dalle3",         # DALL-E 3
    "gpt_image": "gpt_image",   # GPT Image
}

# 자동 선택 시 키워드 기반 라우팅
MODEL_AUTO_SELECT_KEYWORDS = {
    # 사람/인물 중심 → Imagen 3 (사실적인 인물 사진)
    "imagen3": ["사람", "인물", "노부부", "시니어", "가족", "얼굴", "미소", "건강", "운동",
                "person", "people", "elderly", "family", "face", "portrait", "emotional",
                # 추가: 감성/향수/회상 모드 키워드
                "추억", "옛날", "가족사진", "nostalgic", "memory", "vintage",
                # ★ 야담도 Imagen으로 (애니 스타일 프롬프트로 처리)
                "야담", "조선", "장터", "기와집", "호랑이", "도깨비", "사또", "선비", "양반",
                "joseon", "historical korean", "traditional korean"],
    # 만화/지식/클래식 → DALL-E 3 (일러스트/정보 시각화)
    "dalle3": ["만화", "웹툰", "일러스트", "manhwa", "webtoon", "comic", "illustration",
               "ink brush",
               "도표", "그래프", "차트", "기호", "아이콘", "인포그래픽", "설명", "비교", "통계",
               "diagram", "chart", "graph", "icon", "symbol", "infographic", "comparison",
               # 추가: 지식/교훈/명언 모드 키워드
               "명언", "교훈", "지혜", "wisdom", "philosophy", "quote", "lesson",
               "정보", "팁", "방법", "노하우", "knowledge", "tips", "howto",
               # 추가: 클래식/명작 모드 키워드
               "클래식", "명작", "음악", "예술", "영화", "classic", "masterpiece", "art", "music"],
    # 동화/귀여운 캐릭터 → GPT Image
    "gpt_image": ["동화", "캐릭터", "토끼", "곰", "요정", "애니메이션", "귀여운",
                  "cartoon", "character", "rabbit", "bear", "fairy", "cute", "animated", "chibi"]
}


# 시니어 맞춤 이미지 스타일 가이드
SENIOR_IMAGE_STYLES = {
    "health": {
        "base_prompt": "중년 이상의 한국인이 건강을 챙기는 장면",
        "style": "따뜻한 색감, 밝은 조명, 신뢰감 있는 분위기",
        "mood": "희망적이고 긍정적인",
        "avoid": "병원 장비, 주사기 등 불안감을 주는 요소는 피함"
    },
    "money": {
        "base_prompt": "시니어가 편안하게 재정 계획을 세우는 장면",
        "style": "안정적이고 깔끔한 느낌, 파란색이나 녹색 계열",
        "mood": "신뢰감 있고 안정적인",
        "avoid": "복잡한 그래프나 어려운 차트는 피함"
    },
    "emotion": {
        "base_prompt": "따뜻한 가족, 추억의 장면",
        "style": "따뜻하고 서정적인 색감, 부드러운 조명",
        "mood": "향수를 불러일으키는, 감성적인",
        "avoid": "너무 슬프거나 우울한 분위기는 피함"
    },
    "emotional": {  # emotional_kr_v1 호환
        "base_prompt": "따뜻한 가족, 추억의 장면, 감동 실화 스타일",
        "style": "따뜻하고 서정적인 색감, 부드러운 조명, 시네마틱",
        "mood": "향수를 불러일으키는, 감성적인, 눈물이 나는",
        "avoid": "너무 슬프거나 우울한 분위기는 피함"
    },
    "memory": {
        "base_prompt": "옛날 한국의 풍경과 사람들",
        "style": "빈티지 사진 느낌, 세피아 톤 또는 흑백",
        "mood": "향수 어린, 추억을 소환하는",
        "avoid": "너무 현대적인 요소는 피함"
    },
    "nostalgic": {  # nostalgic_kr_v1 호환
        "base_prompt": "옛날 한국의 풍경과 사람들, 60-80년대 추억",
        "style": "빈티지 사진 느낌, 세피아 톤 또는 흑백, 필름 그레인",
        "mood": "향수 어린, 추억을 소환하는, 그리움이 묻어나는",
        "avoid": "너무 현대적인 요소는 피함, 스마트폰, 현대 건물"
    },
    "wisdom": {  # wisdom_kr_v1 - 교훈/명언형
        "base_prompt": "명언과 인생 교훈을 전달하는 현자, 자연 배경",
        "style": "깊은 색감, 자연광, 사색적인 분위기, 책/글씨 요소",
        "mood": "사려깊은, 철학적인, 깨달음을 주는",
        "avoid": "산만한 배경, 복잡한 구도, 화려한 색감"
    },
    "knowledge": {  # knowledge_kr_v1 - 지식/정보형
        "base_prompt": "시니어가 새로운 정보를 배우는 장면, 일상 팁",
        "style": "밝고 깔끔한 색감, 정돈된 느낌, 인포그래픽 요소",
        "mood": "친근하고 신뢰감 있는, 유익한",
        "avoid": "복잡한 전문 용어, 어려운 다이어그램"
    },
    "classic": {  # classic_kr_v1 - 명작/음악 해설형
        "base_prompt": "클래식 음악, 명작 영화, 예술 작품 감상 장면",
        "style": "우아하고 고전적인 분위기, 골드/버건디 색조, 고급스러운",
        "mood": "감상적인, 예술적인, 고급스러운 여유",
        "avoid": "저품질 느낌, 산만한 배경, 너무 현대적인 요소"
    },
    "general": {
        "base_prompt": "편안하고 이해하기 쉬운 장면",
        "style": "밝고 명확한 색감, 높은 명도 대비",
        "mood": "친근하고 편안한",
        "avoid": "복잡하거나 산만한 구도는 피함"
    },
    "history": {
        "base_prompt": "역사적 장면, 조선시대 또는 고대 한국 배경",
        "style": "드라마틱하고 영화적인 분위기, 깊은 색감과 명암 대비",
        "mood": "웅장하고 극적인, 역사 다큐멘터리 느낌",
        "avoid": "현대적 요소, 애니메이션 스타일, 캐리커처는 피함"
    },
    "drama": {
        "base_prompt": "시니어 드라마 스틸컷 느낌, 한국 일상 배경, 감정 몰입형 장면",
        "style": "한국 멜로/가족 드라마 색감, 시네마틱 조명, 상징적 구도",
        "mood": "드라마틱하고 감정적인, 몰입감 있는, 현실적인",
        "avoid": "과도하게 선정적이거나 폭력적인 장면, 만화 스타일, 정면 얼굴 클로즈업",
        # ★ 시니어 드라마 특화 연출 가이드
        "composition": "정면보다 측면/뒷모습, 부분 초점 (손, 실루엣), 상황 상징성 강조",
        "color_flow": {
            "평온": "따뜻한 밝은 톤 (베이지, 크림색, 주황빛)",
            "갈등": "어두운 톤 (회색, 청회색, 그림자, 낮은 채도)",
            "해결": "따뜻함 회복 (주황빛, 황금빛) 또는 냉소적 끝맺음 (차가운 파란색)",
        },
        "settings": ["아파트 거실", "식탁", "병원 복도", "공원 벤치", "사무실", "현관문 앞"],
    },
    "kids": {
        "base_prompt": "귀여운 동물 캐릭터, 어린이 동화 일러스트 스타일",
        "style": "밝고 화사한 파스텔 색감, 동화책 그림체, 3D 애니메이션 캐릭터, 따뜻하고 부드러운 느낌",
        "mood": "밝고 즐거운, 따뜻하고 포근한, 판타지 동화 느낌",
        "avoid": "무서운 장면, 어두운 색감, 현실적인 사람, 폭력적이거나 슬픈 장면, 복잡한 배경"
    },
    "yadam": {
        "base_prompt": "Korean historical anime illustration, Joseon dynasty setting, dramatic anime art style",
        "style": "anime illustration style, Japanese anime aesthetic, Korean historical drama, vibrant colors, dramatic lighting, detailed character design, Studio Ghibli inspired, cel-shaded art, 2D animation style",
        "mood": "극적이고 긴장감 있는, 권선징악 스토리, 전통적이면서 다이나믹한",
        "avoid": "photorealistic, 3D render, western cartoon, chibi, cute style, modern clothing",
        # ★ 야담 특화 연출 가이드 (애니 스타일)
        "composition": "dramatic camera angles, silhouette shots, side/back view composition, dynamic action poses, anime-style composition",
        "color_palette": {
            "기본": "warm earth tones, traditional Korean colors, soft lighting",
            "긴장": "dark shadows, high contrast, red accents, dramatic lighting",
            "평화": "soft watercolor tones, gentle greens and blues, serene atmosphere",
        },
        "settings": ["Joseon era marketplace", "traditional Korean hanok", "tavern", "mountain cabin", "blacksmith", "government office", "nobleman's mansion"],
        "art_direction": "anime illustration of Korean historical drama, like a high-quality anime movie set in Joseon Korea, detailed backgrounds, expressive characters"
    }
}


class ImageEngine:
    """
    이미지 생성 엔진 (Gemini API)
    - 각 scene의 image_prompt를 기반으로 시니어 맞춤 이미지 생성
    - 썸네일 이미지 생성
    - PIL을 사용한 텍스트 오버레이
    - 실패 시 Pexels 이미지 대체 (자막 포함)
    - 주인공 캐릭터 일관성 유지 (모든 씬에서 동일한 외형)
    """

    PEXELS_PHOTOS_API_URL = "https://api.pexels.com/v1/search"

    # 주인공 캐릭터 프로필 저장 (세션 내 일관성 유지)
    _protagonist_profile = None

    def __init__(self, api_key: str = None, openai_key: str = None):
        """
        Args:
            api_key: Gemini API 키 (환경변수에서 가져오거나 직접 전달)
            openai_key: OpenAI API 키 (DALL-E 3용)
        """
        # 비디오 해상도에 따른 이미지 비율 설정
        # YouTube Shorts: 1080x1920 (9:16) → DALL-E: 1024x1792
        # YouTube Long: 1920x1080 (16:9) → DALL-E: 1792x1024
        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        width, height = map(int, resolution.split('x'))

        if height > width:  # 세로 영상 (Shorts)
            self.dalle3_size = "1024x1792"  # 9:16
            self.aspect_ratio = "9:16"
        else:  # 가로 영상 (Long)
            self.dalle3_size = "1792x1024"  # 16:9
            self.aspect_ratio = "16:9"

        self.video_width = width
        self.video_height = height
        print(f"[ImageEngine] Video: {resolution} ({self.aspect_ratio}) → DALL-E 3: {self.dalle3_size}")

        # Claude API 초기화 (동적 프롬프트 생성용)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_client = None
        if anthropic_key:
            try:
                self.anthropic_client = Anthropic(api_key=anthropic_key)
                print("[ImageEngine] Claude API enabled for dynamic prompt generation")
            except Exception as e:
                print(f"[ImageEngine] Warning: Failed to initialize Claude API: {e}")

        # 이미지 엔진 선택
        image_engine = os.getenv("IMAGE_ENGINE", "gemini_flash").lower()

        self.engine_type = image_engine
        self.enabled = False

        # 클라이언트 초기화 (None으로 먼저 설정하여 AttributeError 방지)
        self.openai_client = None
        self.gemini_api_key = None

        # Pexels API 키 (폴백용)
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")
        self.pexels_enabled = bool(self.pexels_api_key)

        # ★ 사용자 명시적 선택 여부 (auto가 아닌 경우)
        self.user_explicit_selection = (image_engine != "auto")

        # "auto" 모드: 사용 가능한 엔진 중 우선순위로 선택 (Imagen > DALL-E)
        if image_engine == "auto":
            openai_api_key = openai_key or os.getenv("OPENAI_API_KEY")
            gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")

            # 두 엔진 모두 초기화 (런타임 자동 선택용)
            if gemini_api_key:
                try:
                    genai.configure(api_key=gemini_api_key)
                    self.gemini_api_key = gemini_api_key
                except Exception as e:
                    print(f"[ImageEngine] Warning: Failed to initialize Gemini: {e}")
                    self.gemini_api_key = None

            if openai_api_key:
                try:
                    # ★ 타임아웃 180초 (3분)로 증가 - 대량 이미지 생성 시 안정성 향상
                    self.openai_client = OpenAI(api_key=openai_api_key, timeout=180.0)
                except Exception as e:
                    print(f"[ImageEngine] Warning: Failed to initialize OpenAI: {e}")
                    self.openai_client = None

            # ★ 기본 엔진 결정 (우선순위: Imagen > DALL-E)
            # - Imagen 우선, 실패 시 DALL-E 폴백
            if gemini_api_key:
                self.engine_type = "gemini_flash"
                self.enabled = True
                if openai_api_key:
                    print("[ImageEngine] Auto mode: Imagen (primary) → DALL-E (fallback)")
                else:
                    print("[ImageEngine] Auto mode: Imagen only")
            elif openai_api_key:
                self.engine_type = "dalle3"
                self.enabled = True
                print("[ImageEngine] Auto mode: DALL-E 3 only (no Imagen key)")
            else:
                print("[ImageEngine] Auto mode: No API keys, using placeholder")

        # OpenAI 계열 엔진
        elif image_engine in ["dalle3", "dalle2"]:
            openai_api_key = openai_key or os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                try:
                    # ★ 타임아웃 180초 (3분) 설정 - 대량 이미지 생성 시 안정성 향상
                    self.openai_client = OpenAI(
                        api_key=openai_api_key,
                        timeout=180.0
                    )
                    self.enabled = True
                    engine_names = {
                        "dalle3": "DALL-E 3",
                        "dalle2": "DALL-E 2"
                    }
                    print(f"[ImageEngine] Using {engine_names.get(image_engine, image_engine)} (timeout: 180s)")
                except Exception as e:
                    print(f"[ImageEngine] Warning: Failed to initialize OpenAI: {e}")
                    self.enabled = False
            else:
                print("[ImageEngine] Warning: No OpenAI API key. Using placeholder.")

        # Google Imagen 4.0 / Gemini 3 Pro Image 엔진
        elif image_engine in ["gemini_flash", "gemini_pro", "gemini_ultra", "gemini_3_pro_image"]:
            gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
            if gemini_api_key:
                try:
                    # Gemini API 초기화 (Imagen 4.0 / Gemini 3 Pro 백엔드 사용)
                    genai.configure(api_key=gemini_api_key)
                    self.gemini_api_key = gemini_api_key
                    self.enabled = True
                    engine_names = {
                        "gemini_flash": "Imagen 4.0 Fast ($0.02/장)",
                        "gemini_pro": "Imagen 4.0 ($0.04/장)",
                        "gemini_ultra": "Imagen 4.0 Ultra ($0.06/장)",
                        "gemini_3_pro_image": "Gemini 3 Pro Image ($0.134/장)"
                    }
                    print(f"[ImageEngine] Using {engine_names.get(image_engine, image_engine)}")

                    # ★ DALL-E 폴백용 OpenAI 클라이언트 초기화
                    openai_api_key = os.getenv("OPENAI_API_KEY")
                    if openai_api_key:
                        try:
                            self.openai_client = OpenAI(api_key=openai_api_key)
                            print(f"[ImageEngine] DALL-E fallback enabled")
                        except Exception as e:
                            print(f"[ImageEngine] DALL-E fallback not available: {e}")
                except Exception as e:
                    print(f"[ImageEngine] Warning: Failed to initialize Gemini: {e}")
                    print(f"[ImageEngine] Falling back to placeholder images")
                    self.enabled = False
            else:
                print("[ImageEngine] Warning: No Gemini API key. Using placeholder.")

        else:
            # placeholder
            print("[ImageEngine] Using placeholder images (no AI generation)")

    def _select_model_for_scene(self, scene: Scene) -> str:
        """
        ★ Model Router: Scene의 model_hint와 내용을 분석하여 최적 모델 선택

        Args:
            scene: Scene 객체 (model_hint, image_prompt 포함)

        Returns:
            선택된 모델 ID (gemini_flash, dalle3, gpt_image 등)
        """
        # 1. Scene에서 model_hint 가져오기
        model_hint = getattr(scene, 'model_hint', 'auto')

        # 2. 명시적 힌트가 있으면 해당 모델 사용
        if model_hint and model_hint != 'auto':
            target_model = MODEL_ROUTING_RULES.get(model_hint)
            if target_model:
                print(f"  [ModelRouter] model_hint='{model_hint}' → {target_model}")
                return target_model

        # 3. auto인 경우 키워드 기반 자동 선택
        image_prompt = scene.image_prompt.lower() if scene.image_prompt else ""
        narration = scene.narration.lower() if scene.narration else ""
        combined_text = f"{image_prompt} {narration}"

        # 키워드 매칭 점수 계산
        scores = {}
        for model_id, keywords in MODEL_AUTO_SELECT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in combined_text)
            if score > 0:
                scores[model_id] = score

        # 가장 높은 점수의 모델 선택
        if scores:
            best_model = max(scores, key=scores.get)
            target_model = MODEL_ROUTING_RULES.get(best_model, self.engine_type)
            print(f"  [ModelRouter] auto → {best_model} (score: {scores[best_model]}) → {target_model}")
            return target_model

        # 4. 기본값: 설정된 엔진 사용
        print(f"  [ModelRouter] auto → default ({self.engine_type})")
        return self.engine_type

    def _generate_image_with_model(self, prompt: str, model_id: str, output_path: str) -> bool:
        """
        ★ Model Router: 지정된 모델로 이미지 생성 (실패 시 폴백)

        Args:
            prompt: 이미지 프롬프트
            model_id: 모델 ID (gemini_flash, dalle3, gpt_image)
            output_path: 출력 경로

        Returns:
            성공 여부
        """
        success = False

        try:
            if model_id in ["gemini_flash", "gemini_pro", "gemini_ultra", "gemini_3_pro_image"]:
                # Imagen 4.0 / Gemini 3 Pro Image 생성 시도
                success = self._generate_with_gemini(prompt, output_path)

                # Imagen 실패 시 DALL-E 3로 폴백 (사람 없이 배경만)
                if not success and self.openai_client:
                    print(f"  [ModelRouter] Imagen 실패 → DALL-E 3로 폴백 (배경 전용)")
                    success = self._generate_with_dalle3(prompt, output_path, is_fallback=True)

            elif model_id == "dalle3":
                # DALL-E 3 생성
                success = self._generate_with_dalle3(prompt, output_path)

                # ★ DALL-E 실패 시 Imagen으로 폴백
                if not success and self.gemini_api_key:
                    print(f"  [ModelRouter] DALL-E 3 실패 → Imagen으로 폴백")
                    success = self._generate_with_gemini(prompt, output_path)

            elif model_id == "dalle2":
                # DALL-E 2 생성
                success = self._generate_with_dalle2(prompt, output_path)

                # ★ DALL-E 2 실패 시 Imagen으로 폴백
                if not success and self.gemini_api_key:
                    print(f"  [ModelRouter] DALL-E 2 실패 → Imagen으로 폴백")
                    success = self._generate_with_gemini(prompt, output_path)
            elif model_id == "gpt_image":
                # GPT Image 생성 (OpenAI Image API)
                success = self._generate_with_dalle3(prompt, output_path)  # 같은 API 사용
            else:
                # 기본값: 현재 설정된 엔진
                if self.engine_type.startswith("gemini"):
                    success = self._generate_with_gemini(prompt, output_path)
                    # Gemini 실패 시 DALL-E 폴백 (사람 없이 배경만)
                    if not success and self.openai_client:
                        print(f"  [ModelRouter] Gemini 실패 → DALL-E 3로 폴백 (배경 전용)")
                        success = self._generate_with_dalle3(prompt, output_path, is_fallback=True)
                elif self.engine_type.startswith("dalle"):
                    success = self._generate_with_dalle3(prompt, output_path)
                    # ★ DALL-E 실패 시 Imagen 폴백
                    if not success and self.gemini_api_key:
                        print(f"  [ModelRouter] DALL-E 실패 → Imagen으로 폴백")
                        success = self._generate_with_gemini(prompt, output_path)

        except Exception as e:
            print(f"  [ModelRouter] Error with model {model_id}: {e}")

        return success

    def _generate_protagonist_profile(self, scenes: List[Scene], category: str) -> dict:
        """
        스토리 분석을 통해 주인공 캐릭터 프로필 생성
        ★ 모든 모드는 이야기 기반! 모든 영상에는 주인공이 있다.

        Args:
            scenes: Scene 리스트 (나레이션 분석용)
            category: 카테고리 (역사, 건강, 감성, 재테크 등)

        Returns:
            주인공 프로필 딕셔너리:
            {
                "description": "영어 캐릭터 묘사",
                "mood_context": "스토리 전체 분위기",
                "setting": "배경/시대 설정",
                "supporting_chars": "주변 인물 스타일"
            }
        """
        if not self.anthropic_client:
            print("[ImageEngine] Claude API 없음 - 기본 프로필 사용")
            return None

        # 전체 나레이션 수집 (스토리 이해용)
        all_narrations = "\n".join([
            f"Scene {i+1} ({s.scene_id}): {s.narration}"
            for i, s in enumerate(scenes[:5])  # 처음 5개 씬만 분석
        ])

        system_prompt = """당신은 영상 스토리 분석가입니다.

★★★ 핵심 원칙 ★★★
나레이션 내용을 직접 분석해서 주인공과 배경을 파악하세요.
카테고리는 힌트일 뿐, 나레이션 내용이 진실입니다!

★★★ 시대/맥락 자동 감지 (필수!) ★★★
나레이션을 읽고 스스로 판단하세요:
- 어떤 시대의 이야기인가? (고대, 중세, 근대, 현대, 미래, 판타지)
- 주인공은 누구인가? (역사 인물, 일반인, 캐릭터)
- 어떤 상황/장소인가? (전쟁, 궁궐, 가정, 학교, 직장)

→ 나레이션에서 특정 시대/인물이 언급되면:
  - 해당 시대에 맞는 복장 (갑옷, 한복, 양복, 현대복 등)
  - 해당 시대에 맞는 배경 (궁궐, 전쟁터, 마을, 도시 등)
  - 현대 요소 삽입 금지!

분석할 것:
1. 시대/배경: 나레이션에서 직접 추론 (언급된 인물, 사건, 장소 기반)
2. 주인공 외형: 나이, 성별, 체형, 시대에 맞는 복장
3. 분위기: 긴장감, 슬픔, 희망, 따뜻함 등
4. 주변 인물: 나레이션 맥락에 맞는 스타일

출력 형식:
- 영어로 작성 (이미지 생성 AI용)
- 구체적이고 시각적으로 묘사
- 주인공이 명시되지 않아도 나레이션에서 추론"""

        # 카테고리 힌트 (참고용, 나레이션 내용이 우선!)
        category_hints = {
            "emotional": "감동/헌신 스토리. 단, 나레이션 내용이 우선!",
            "nostalgic": "회상/향수 스토리. 단, 나레이션 내용이 우선!",
            "wisdom": "교훈/명언 스토리. 단, 나레이션 내용이 우선!",
            "knowledge": "지식/정보 스토리. 단, 나레이션 내용이 우선!",
            "classic": "명작/음악 스토리. 단, 나레이션 내용이 우선!",
            "drama": "드라마형 서사. 측면/뒷모습, 갈등 상황, 극적 색조 전환, 상징적 구도!",
            "kids": "어린이 동화. 귀여운 캐릭터, 파스텔 색감.",
            "general": "일반 스토리. 나레이션 내용에서 직접 파악!"
        }

        # 유아 모드는 별도 프롬프트 사용 (캐릭터 스타일이 다름)
        if category == "kids":
            return self._generate_kids_character_profile(scenes)

        user_prompt = f"""다음 나레이션을 분석해서 이 이야기의 주인공을 찾아주세요:

{all_narrations}

카테고리: {category}
힌트: {category_hints.get(category, category_hints['general'])}

★ 이 영상의 주인공은 누구인가요? 모든 씬에서 같은 사람이 등장해야 합니다.

JSON 형식으로 답해주세요:
{{
    "protagonist": {{
        "age": "estimated age range (e.g., 'late 50s', '40s', '70s')",
        "gender": "male/female",
        "appearance": "detailed physical description - face shape, hair style, skin tone, build (in English)",
        "clothing": "typical outfit for this story context",
        "expression": "default emotional expression matching story mood"
    }},
    "mood": "overall story mood (e.g., tense, hopeful, melancholic, warm, informative)",
    "setting": "time period and typical location (e.g., 'modern Korean home', '1970s rural Korea', 'Joseon dynasty palace')",
    "supporting_style": "how other characters should look (e.g., 'family members in casual clothes', 'soldiers in uniform')"
}}"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=system_prompt
            )

            import json
            result_text = response.content[0].text.strip()

            # JSON 파싱 시도
            # ```json ... ``` 형태로 올 수 있으므로 처리
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            profile = json.loads(result_text)

            # ★ 타입 안전성 확보 (str이 올 경우 dict로 변환)
            profile = ensure_dict(profile, {})

            # 영어 캐릭터 묘사 생성
            protagonist = ensure_dict(profile.get("protagonist"), {})
            description = f"{protagonist.get('age', 'middle-aged')} {protagonist.get('gender', 'person')}, " \
                         f"{protagonist.get('appearance', 'Korean person')}, " \
                         f"wearing {protagonist.get('clothing', 'casual clothes')}, " \
                         f"{protagonist.get('expression', 'neutral expression')}"

            final_profile = {
                "description": description,
                "mood_context": profile.get("mood", "neutral"),
                "setting": profile.get("setting", "modern Korean"),
                "supporting_chars": profile.get("supporting_style", "typical Korean people")
            }

            print(f"[ImageEngine] ★ 주인공 프로필 생성됨 (모든 씬 적용):")
            print(f"  - 외형: {description[:80]}...")
            print(f"  - 분위기: {final_profile['mood_context']}")
            print(f"  - 배경: {final_profile['setting']}")

            return final_profile

        except Exception as e:
            print(f"[ImageEngine] 프로필 생성 실패: {e}")
            return None

    def _generate_kids_character_profile(self, scenes: List[Scene]) -> dict:
        """
        유아 동화용 캐릭터 프로필 생성
        귀여운 동물/요정 캐릭터의 일관된 외형 정의
        ★ 매우 구체적인 특징 정의 (색상, 무늬, 악세사리 등)

        Args:
            scenes: Scene 리스트 (나레이션 분석용)

        Returns:
            캐릭터 프로필 딕셔너리
        """
        if not self.anthropic_client:
            print("[ImageEngine] Claude API 없음 - 기본 동화 캐릭터 사용")
            return {
                "description": "a cute small rabbit character with big round sparkling brown eyes, fluffy cream-white fur with a small pink nose, pink inner ears, wearing a bright red bow on the right ear and a tiny blue vest with yellow buttons",
                "character_id": "cream_rabbit_red_bow",
                "style": "Pixar 3D animation style, soft lighting, pastel colors",
                "mood_context": "bright, cheerful, warm fairy tale",
                "setting": "colorful fantasy forest with pastel pink and blue sky, fluffy white clouds, green grass with small flowers",
                "supporting_chars": "other cute animal friends: a small brown bear with a green scarf, an orange squirrel with round glasses"
            }

        # 전체 나레이션 수집
        all_narrations = "\n".join([
            f"Scene {i+1}: {s.narration}"
            for i, s in enumerate(scenes[:5])
        ])

        system_prompt = """당신은 어린이 동화 일러스트레이터입니다.
나레이션을 읽고 이 동화의 주인공 캐릭터를 디자인해주세요.

★★★ 매우 중요: 캐릭터 일관성을 위해 아주 구체적으로 묘사해야 합니다! ★★★

모든 특징을 구체적으로:
- 털/피부 색상: "cream-white fur" (X "white fur")
- 눈 색상과 형태: "big round sparkling brown eyes"
- 코/귀 색상: "small pink nose, pink inner ears"
- 악세사리: "bright red bow on the right ear" (위치까지 명시)
- 옷: "tiny blue vest with yellow buttons" (색상, 디테일 명시)

캐릭터 디자인 원칙:
1. 귀여운 동물 캐릭터 (토끼, 곰, 다람쥐, 고양이 등)
2. 큰 반짝이는 눈, 동글동글한 형태
3. 특징적인 악세사리 (리본, 모자, 스카프 등) - 색상/위치 명시
4. 4~7세 아이들이 좋아할 스타일
5. 픽사/디즈니 3D 애니메이션 스타일

★ 주변 캐릭터도 구체적으로 (색상, 악세사리 포함)

피해야 할 것:
- 모호한 묘사 ("cute animal" 대신 "cute cream-white rabbit")
- 무서운 요소
- 현실적인 사람
- 어두운 색감

출력: 영어로 된 매우 구체적인 캐릭터 묘사"""

        user_prompt = f"""다음 어린이 동화 나레이션을 읽고 주인공 캐릭터를 아주 구체적으로 디자인해주세요:

{all_narrations}

JSON 형식으로 답해주세요 (★ 모든 색상, 위치, 디테일을 영어로 구체적으로!):
{{
    "character": {{
        "type": "specific animal (e.g., 'rabbit', 'bear cub', 'baby fox')",
        "fur_color": "very specific color (e.g., 'cream-white', 'soft brown', 'light orange')",
        "eye_details": "color and shape (e.g., 'big round sparkling brown eyes')",
        "nose_ears": "details (e.g., 'small pink nose, pink inner ears')",
        "accessory": "specific item with color and position (e.g., 'bright red bow on the right ear')",
        "clothing": "specific outfit with colors (e.g., 'tiny blue vest with yellow buttons')",
        "special_feature": "unique trait (e.g., 'a small heart-shaped patch on left cheek')"
    }},
    "style": "Pixar 3D animation style, soft lighting, pastel colors",
    "setting": "specific background with colors",
    "supporting_characters": [
        {{"type": "animal", "color": "fur color", "accessory": "item"}},
        {{"type": "animal", "color": "fur color", "accessory": "item"}}
    ]
}}"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=700,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=system_prompt
            )

            import json
            result_text = response.content[0].text.strip()

            # JSON 파싱
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            profile = json.loads(result_text)

            # ★ 타입 안전성 확보
            profile = ensure_dict(profile, {})

            # 매우 구체적인 캐릭터 묘사 조합
            character = ensure_dict(profile.get("character"), {})

            # 모든 특징을 조합
            description_parts = [
                f"a cute {character.get('type', 'rabbit')} character",
                f"with {character.get('fur_color', 'cream-white')} fur",
                character.get('eye_details', 'big round sparkling eyes'),
                character.get('nose_ears', 'small pink nose'),
                f"wearing {character.get('accessory', 'a red bow')}",
                f"and {character.get('clothing', 'a blue vest')}"
            ]

            if character.get('special_feature'):
                description_parts.append(character.get('special_feature'))

            description = ", ".join(description_parts)

            # 캐릭터 ID 생성 (일관성 추적용)
            char_type = character.get('type', 'rabbit').replace(' ', '_')
            char_color = character.get('fur_color', 'white').split()[0] if character.get('fur_color') else 'white'
            character_id = f"{char_color}_{char_type}"

            # 주변 캐릭터 묘사 (리스트가 아닌 경우 빈 리스트로)
            supporting = profile.get("supporting_characters", [])
            if not isinstance(supporting, list):
                supporting = []
            supporting_desc = []
            for s in supporting[:2]:  # 최대 2명
                if isinstance(s, dict):
                    supporting_desc.append(f"a {s.get('color', 'brown')} {s.get('type', 'animal')} with {s.get('accessory', 'no accessory')}")

            final_profile = {
                "description": description,
                "character_id": character_id,
                "style": profile.get("style", "Pixar 3D animation style, soft lighting, pastel colors"),
                "mood_context": "bright, cheerful, warm fairy tale atmosphere",
                "setting": profile.get("setting", "colorful fantasy world with pastel colors"),
                "supporting_chars": ", ".join(supporting_desc) if supporting_desc else "other cute animal friends with similar cartoon style"
            }

            print(f"[ImageEngine] ★ 동화 캐릭터 프로필 생성됨:")
            print(f"  - 캐릭터 ID: {character_id}")
            print(f"  - 외형: {description[:100]}...")
            print(f"  - 스타일: {final_profile['style']}")
            print(f"  - 친구들: {final_profile['supporting_chars'][:50]}...")

            return final_profile

        except Exception as e:
            print(f"[ImageEngine] 동화 캐릭터 프로필 생성 실패: {e}")
            # 기본 귀여운 토끼 캐릭터 (매우 구체적)
            return {
                "description": "a cute small rabbit character with big round sparkling brown eyes, fluffy cream-white fur with a small pink nose, pink inner ears, wearing a bright red bow on the right ear and a tiny blue vest with yellow buttons",
                "character_id": "cream_rabbit_red_bow",
                "style": "Pixar 3D animation style, soft lighting, pastel colors",
                "mood_context": "bright, cheerful, warm fairy tale",
                "setting": "colorful fantasy forest with pastel pink and blue sky, fluffy white clouds, green grass with small flowers",
                "supporting_chars": "a small brown bear cub with a green scarf, an orange squirrel with round glasses"
            }

    def generate_scene_images(self, scenes: List[Scene], output_dir: str,
                              category: str = "general",
                              profile=None) -> tuple[List[str], List[dict]]:
        """
        각 scene에 대한 이미지 생성 (병렬 처리)

        Args:
            scenes: Scene 리스트
            output_dir: 이미지 저장 디렉토리
            category: 카테고리 (스타일 가이드 선택용)
            profile: ContentProfile 객체 (있으면 profile.extra["image_style"] 우선 사용)

        Returns:
            (이미지 경로 리스트, 이벤트 로그 리스트) 튜플
        """
        if not self.enabled:
            print("[ImageEngine] Skipping image generation (API not configured)")
            return [], []

        os.makedirs(output_dir, exist_ok=True)

        # ★ 모드별 이미지 엔진 강제 설정
        # - 사용자가 명시적으로 엔진을 선택한 경우: 모드 기반 오버라이드 안 함
        # - auto 모드인 경우에만 모드별 최적 엔진 자동 선택
        mode_id = getattr(profile, 'mode_id', '') if profile else ''

        if self.user_explicit_selection:
            # ★ 사용자가 직접 엔진 선택 → 그대로 사용 (오버라이드 안 함)
            print(f"[ImageEngine] ★ 사용자 선택 엔진: {self.engine_type} (모드 오버라이드 안 함)")
        else:
            # ★ auto 모드 → 모드별 최적 엔진 자동 선택
            # 야담 모드: Imagen 사용 (애니 스타일)
            force_imagen_modes = ['yadam', 'yadam_kr_v1']
            if mode_id in force_imagen_modes or category == 'yadam':
                print(f"[ImageEngine] ★ {mode_id or category} 모드: Imagen 사용 (애니 스타일)")
                for scene in scenes:
                    scene.model_hint = 'imagen3'

            # 키즈 모드: DALL-E 3 사용 (동화 일러스트 스타일)
            force_dalle3_modes = ['kids', 'kids_kr_v1']
            if mode_id in force_dalle3_modes or category == 'kids':
                print(f"[ImageEngine] ★ {mode_id or category} 모드: DALL-E 3 강제 사용 (동화 일러스트 스타일)")
                for scene in scenes:
                    scene.model_hint = 'dalle3'

        # ★ 통합 설정: profile.extra["image_style"]이 있으면 우선 사용
        if profile and profile.extra.get("image_style"):
            style_guide = profile.extra["image_style"]
            print(f"[ImageEngine] Using profile-based image style for '{category}'")
        else:
            # 하위 호환: 기존 SENIOR_IMAGE_STYLES 사용
            style_guide = SENIOR_IMAGE_STYLES.get(category, SENIOR_IMAGE_STYLES["general"])

        # ★ 주인공 캐릭터 프로필 생성 (일관성 유지)
        print(f"[ImageEngine] Analyzing story for character consistency...")
        self._protagonist_profile = self._generate_protagonist_profile(scenes, category)

        # ★ 순차 처리: Gemini API RPM(분당 요청) 제한 준수
        # 무료 티어 15 RPM 제한으로 인해 순차 처리로 변경
        max_workers = 1
        print(f"[ImageEngine] Starting sequential image generation ({len(scenes)} images, RPM 제한 준수)")

        image_paths = [None] * len(scenes)  # 인덱스 순서 유지
        event_logs = []  # 이벤트 로그 저장

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 모든 scene에 대한 작업 제출 (딜레이 포함)
            futures = {}
            for idx, scene in enumerate(scenes):
                # 나레이션 맥락을 포함한 프롬프트 생성
                enhanced_prompt = self._build_senior_prompt(
                    scene.image_prompt,
                    style_guide,
                    scene.scene_id,
                    narration=scene.narration  # 나레이션 맥락 전달
                )
                image_path = os.path.join(output_dir, f"scene_{idx:03d}_{scene.safe_filename_id}.png")

                # 병렬로 실행할 작업 제출
                future = executor.submit(
                    self._generate_single_image,
                    idx,
                    scene,
                    image_path,
                    enhanced_prompt
                )
                futures[future] = idx

                # ★ API 할당량 초과 방지: 작업 제출 간 0.5초 딜레이
                if idx < len(scenes) - 1:
                    time.sleep(0.5)

            # 완료된 작업 처리 (완료 순서대로)
            completed = 0
            for future in as_completed(futures):
                idx = futures[future]
                completed += 1
                try:
                    result_path, status_message = future.result()
                    image_paths[idx] = result_path

                    # 이벤트 로그 추가
                    event_logs.append({
                        "type": "image",
                        "scene_idx": idx,
                        "scene_id": scenes[idx].scene_id,
                        "status": status_message,
                        "path": result_path
                    })

                    print(f"[ImageEngine] ✓ Completed {completed}/{len(scenes)}: scene_{idx:03d} - {status_message}")
                except Exception as e:
                    print(f"[ImageEngine] ✗ Error on scene {idx}: {e}")
                    # 에러 시 Pexels 대체 시도
                    scene = scenes[idx]
                    image_path = os.path.join(output_dir, f"scene_{idx:03d}_{scene.safe_filename_id}.png")
                    fallback_path, status = self._fallback_to_pexels_image(scene, image_path, scene.image_prompt)
                    image_paths[idx] = fallback_path

                    event_logs.append({
                        "type": "image",
                        "scene_idx": idx,
                        "scene_id": scene.scene_id,
                        "status": status,
                        "error": str(e)[:100],
                        "path": fallback_path
                    })

        # ★ 디버그: 이미지 생성 결과 요약
        success_count = len([p for p in image_paths if p])
        fail_count = len(scenes) - success_count
        print(f"[ImageEngine] Parallel generation complete: {success_count} images")

        if fail_count > 0:
            print(f"[ImageEngine] ⚠️ 실패 요약: {fail_count}개 이미지 생성 실패")
            for log in event_logs:
                if "error" in log:
                    print(f"    ❌ Scene {log['scene_idx']} ({log['scene_id']}): {log.get('error', 'unknown')[:50]}")

        return [p for p in image_paths if p], event_logs  # None 제거 + 이벤트 로그 반환

    def _build_senior_prompt(self, base_prompt: str, style_guide: dict,
                            scene_id: str, narration: str = "") -> str:
        """
        시니어 맞춤 이미지 프롬프트 생성 (Claude 기반 동적 생성)

        Args:
            base_prompt: ScriptEngine에서 생성된 기본 프롬프트
            style_guide: 카테고리별 스타일 가이드
            scene_id: 장면 ID
            narration: 나레이션 텍스트 (맥락 파악용)
        """

        # Claude API가 있으면 동적 프롬프트 생성
        if self.anthropic_client and narration:
            try:
                dynamic_prompt = self._generate_contextual_prompt(
                    narration=narration,
                    base_prompt=base_prompt,
                    scene_id=scene_id,
                    style_guide=style_guide
                )
                if dynamic_prompt:
                    return dynamic_prompt
            except Exception as e:
                print(f"  [Warning] Claude prompt generation failed: {e}, using fallback")

        # 폴백: 기본 프롬프트 구조 사용
        return self._build_fallback_prompt(base_prompt, style_guide, scene_id, narration)

    def _generate_contextual_prompt(self, narration: str, base_prompt: str,
                                   scene_id: str, style_guide: dict) -> str:
        """
        Claude를 사용하여 나레이션 맥락에 맞는 이미지 프롬프트 동적 생성
        ★ 주인공 캐릭터 일관성 + 문맥/감정 일관성 적용
        ★ 유아 모드는 별도의 강화된 캐릭터 일관성 적용

        Args:
            narration: 나레이션 텍스트
            base_prompt: 기본 이미지 프롬프트
            scene_id: 장면 ID
            style_guide: 스타일 가이드

        Returns:
            DALL-E용 영문 이미지 프롬프트
        """
        # ★ style_guide가 dict인지 확인 (문자열로 전달되는 경우 방지)
        if not isinstance(style_guide, dict):
            style_guide = {"base_prompt": "", "art_direction": "", "mood": "warm"}

        # 유아 모드 확인 (kids 스타일 가이드)
        is_kids_mode = style_guide.get('base_prompt', '').startswith('귀여운 동물')

        # 유아 모드는 별도 프롬프트 생성
        if is_kids_mode and self._protagonist_profile:
            return self._generate_kids_contextual_prompt(narration, scene_id, style_guide)

        # 야담 모드 확인 (yadam 스타일 가이드)
        is_yadam_mode = style_guide.get('art_direction', '').startswith('Korean traditional manhwa')

        # 야담 모드는 만화/일러스트 스타일로 별도 프롬프트 생성
        if is_yadam_mode:
            return self._generate_yadam_contextual_prompt(narration, scene_id, style_guide)

        # 주인공 프로필 정보 (있으면 사용)
        protagonist_info = ""
        mood_context = ""
        setting_info = ""

        if self._protagonist_profile:
            protagonist_info = f"""
★ 주인공 캐릭터 (반드시 일관되게 유지):
{self._protagonist_profile['description']}

주변 인물 스타일: {self._protagonist_profile['supporting_chars']}"""

            mood_context = f"""
★ 스토리 전체 분위기: {self._protagonist_profile['mood_context']}
- 이 분위기에 맞는 표정과 배경을 사용하세요
- 탈출 장면이면 긴장된 표정, 슬픈 장면이면 우울한 표정 등"""

            setting_info = f"""
★ 시대/배경 설정: {self._protagonist_profile['setting']}
- 이 설정에 맞는 배경, 소품, 의상을 사용하세요"""

        system_prompt = f"""당신은 유튜브 영상 제작자입니다.
나레이션을 읽고, 그 순간을 촬영한 듯한 자연스러운 사진을 묘사해주세요.

★★★ 가장 중요한 규칙: 캐릭터 일관성 ★★★
{protagonist_info}
{setting_info}

핵심 원칙:
1. 주인공은 모든 씬에서 같은 사람처럼 보여야 함 (나이, 체형, 얼굴 특징 일관)
2. 나레이션의 감정/상황에 맞는 표정과 행동
3. 배경은 나레이션 내용과 어울려야 함 (탈출 장면에 행복한 가족 사진 금지!)
4. 마치 다큐멘터리 촬영처럼 실제 장면을 포착한 느낌
{mood_context}

피해야 할 것:
- "Glowing", "magical", "ethereal", "perfect lighting" 같은 인위적 표현
- 나레이션 내용과 어울리지 않는 감정/분위기
- 매 씬마다 다른 사람처럼 보이는 주인공
- 나레이션에서 파악한 시대/배경과 맞지 않는 요소

★★ 시대/맥락은 나레이션에서 직접 파악! ★★
나레이션 내용을 분석해서 시대와 맥락을 스스로 판단하세요.
- 역사적 인물/사건이 언급되면 → 해당 시대 복장/배경
- 현대 이야기면 → 현대 복장/배경
- 나레이션이 정답입니다. 직접 분석하세요!

출력: 영어로 된 자연스러운 장면 묘사만 (설명 없이, 1-2문장)
★ 주인공이 나오면 반드시 외형 특징을 포함하세요!"""

        user_prompt = f"""다음 나레이션을 읽고 그 장면을 자연스럽게 묘사해주세요:

"{narration}"

이 장면은 '{scene_id}' 유형입니다.
참고: {style_guide['mood']} 분위기로 만들어주세요.
피해야 할 것: {style_guide['avoid']}

★ 주인공이 등장하면 반드시 일관된 외형 특징을 명시하세요!"""

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=system_prompt
        )

        generated_prompt = response.content[0].text.strip()

        # 최소한의 기술적 요구사항만 추가
        final_prompt = f"""{generated_prompt}

Style: Candid photography, natural lighting, documentary style
Format: High resolution, {self.aspect_ratio} aspect ratio, no text or logos"""

        return final_prompt

    def _generate_kids_contextual_prompt(self, narration: str, scene_id: str, style_guide: dict) -> str:
        """
        유아 동화 모드 전용 프롬프트 생성
        ★ 캐릭터 외형을 매우 구체적으로 반복하여 일관성 확보

        Args:
            narration: 나레이션 텍스트
            scene_id: 장면 ID
            style_guide: 스타일 가이드

        Returns:
            DALL-E용 영문 이미지 프롬프트
        """
        profile = self._protagonist_profile
        character_desc = profile['description']
        style = profile.get('style', 'Pixar 3D animation style')
        setting = profile.get('setting', 'colorful fantasy world')
        supporting = profile.get('supporting_chars', '')

        system_prompt = f"""당신은 어린이 동화 일러스트레이터입니다.

★★★★★ 절대 변경 금지: 주인공 캐릭터 외형 ★★★★★
{character_desc}

이 캐릭터는 모든 장면에서 100% 동일하게 보여야 합니다!
- 털 색깔, 눈 색깔, 악세사리, 옷 모두 동일
- 자세나 표정만 나레이션에 맞게 변경

주변 친구들: {supporting}

★ 배경 기본 설정: {setting}
★ 스타일: {style}

출력 규칙:
1. 먼저 주인공 캐릭터 외형을 그대로 복사해서 시작
2. 그 다음 나레이션에 맞는 자세/표정/행동 추가
3. 마지막으로 배경 묘사

절대 금지:
- 캐릭터 외형 변경 (색깔, 악세사리 등)
- 무서운 요소
- 어두운 색감
- 현실적인 사람"""

        user_prompt = f"""다음 어린이 동화 나레이션 장면을 그려주세요:

나레이션: "{narration}"
장면 유형: {scene_id}

★ 주인공 캐릭터 외형을 반드시 포함하세요:
{character_desc}

이 캐릭터가 나레이션 내용에 맞는 행동을 하는 장면을 영어로 묘사해주세요.
(캐릭터 외형 + 행동/표정 + 배경 순서로)"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=system_prompt
            )

            generated_scene = response.content[0].text.strip()

            # 캐릭터 외형을 한 번 더 강조해서 프롬프트 구성
            final_prompt = f"""Children's picture book illustration, {style}:

MAIN CHARACTER (MUST be exactly this): {character_desc}

SCENE: {generated_scene}

BACKGROUND: {setting}

Style: {style}, soft lighting, pastel colors, no dark shadows
Format: High resolution, {self.aspect_ratio} aspect ratio, no text or watermarks

IMPORTANT: The main character MUST have exactly the same appearance as described above in every detail (fur color, accessories, clothing)."""

            return final_prompt

        except Exception as e:
            print(f"[ImageEngine] Kids prompt generation failed: {e}")
            # 폴백: 기본 구조로 프롬프트 생성
            return f"""Children's picture book illustration, {style}:

{character_desc}, {narration[:100]}

Background: {setting}
Style: {style}, soft lighting, pastel colors
Format: High resolution, {self.aspect_ratio} aspect ratio, no text"""

    def _generate_yadam_contextual_prompt(self, narration: str, scene_id: str, style_guide: dict) -> str:
        """
        야담 모드 전용 프롬프트 생성
        ★ 만화/웹툰 일러스트 스타일 강조
        ★ 한국 전통 배경 + 극적인 명암 대비

        Args:
            narration: 나레이션 텍스트
            scene_id: 장면 ID
            style_guide: 스타일 가이드

        Returns:
            DALL-E용 영문 이미지 프롬프트 (만화/일러스트 스타일)
        """
        # ★ style_guide가 dict인지 확인 (문자열로 전달되는 경우 방지)
        if not isinstance(style_guide, dict):
            style_guide = {
                "mood": "dramatic",
                "composition": "극적인 명암 대비, 실루엣 활용",
                "color_palette": {"기본": "따뜻한 황토색", "긴장": "어두운 먹색", "평화": "부드러운 수묵화 톤"}
            }

        # 주인공 프로필 정보 (★ 강화: 반드시 프롬프트에 포함)
        protagonist_info = ""
        protagonist_direct = ""  # 프롬프트에 직접 삽입할 주인공 설명
        if self._protagonist_profile:
            protagonist_info = f"""
★★★ 주인공 캐릭터 (반드시 일관되게 유지!) ★★★
외형: {self._protagonist_profile['description']}
배경: {self._protagonist_profile['setting']}

⚠️ 경고: 주인공이 다른 사람처럼 보이면 안 됩니다!
- 나이, 체형, 얼굴 특징이 모든 씬에서 동일해야 함
- 젊은 사람이 갑자기 노인으로 바뀌면 안 됨
- 의상 스타일과 색상도 일관성 유지"""
            protagonist_direct = self._protagonist_profile['description']

        # 장면별 색조 가이드
        color_guide = ""
        color_palette = style_guide.get('color_palette', {})
        # ★ color_palette가 문자열인 경우 기본값 사용
        if isinstance(color_palette, str):
            color_guide = color_palette  # 문자열 그대로 사용
        elif isinstance(color_palette, dict):
            if scene_id in ["hook", "conflict", "climax", "climax1", "climax2"]:
                color_guide = color_palette.get('긴장', '어두운 먹색, 강한 명암 대비')
            elif scene_id in ["closing", "resolution"]:
                color_guide = color_palette.get('평화', '부드러운 수묵화 톤')
            else:
                color_guide = color_palette.get('기본', '따뜻한 황토색, 세피아 톤')
        else:
            color_guide = '따뜻한 황토색, 세피아 톤'

        system_prompt = f"""당신은 한국 전통 야담(野談) 만화 일러스트레이터입니다.
나레이션을 읽고, 한국 웹툰/만화 스타일의 일러스트를 묘사해주세요.

★★★ 가장 중요: 만화/일러스트 스타일 ★★★
- 반드시 MANHWA (Korean comic) 일러스트 스타일로!
- 사실적인 사진 스타일 절대 금지!
- 손으로 그린 듯한 만화체, 먹과 붓 느낌
- 극적인 명암 대비, 동양화 영향

{protagonist_info}

★ 필수 스타일 키워드 (반드시 포함):
- "Korean manhwa illustration style"
- "hand-drawn comic art"
- "ink brush strokes"
- "traditional Asian painting influence"
- "NOT photorealistic, NOT 3D render"

★ 구도 가이드:
- 실루엣, 뒷모습, 측면 구도 활용
- 극적인 명암 대비
- 동적인 액션 포즈 (액션 장면일 때)

★ 배경:
- 조선시대 장터, 기와집, 주막, 산속 오두막 등 전통 배경

출력: 영어로 된 만화 일러스트 묘사만 (설명 없이, 2-3문장)
반드시 "Korean manhwa illustration style" 포함!"""

        # ★ 주인공 설명을 직접 프롬프트에 포함
        protagonist_requirement = ""
        if protagonist_direct:
            protagonist_requirement = f"""
★★★ 주인공 외형 (반드시 이대로 그려주세요!):
{protagonist_direct}
★★★"""

        user_prompt = f"""다음 나레이션을 한국 웹툰/만화 스타일로 묘사해주세요:

"{narration}"
{protagonist_requirement}
이 장면은 '{scene_id}' 유형입니다.
색조 가이드: {color_guide}
분위기: {style_guide['mood']}

★ 반드시 "Korean manhwa illustration style, hand-drawn comic art" 스타일로!
★ 사실적인 사진 스타일 절대 금지!
★ 주인공이 등장하면 위 외형대로 정확히 그려야 합니다!"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            generated_prompt = response.content[0].text.strip()

            # 만화 스타일 키워드가 없으면 추가
            if "manhwa" not in generated_prompt.lower() and "comic" not in generated_prompt.lower():
                generated_prompt = f"Korean manhwa illustration style, hand-drawn comic art: {generated_prompt}"

            # ★ 주인공 외형 정보 직접 삽입 (이미지 일관성 강화)
            protagonist_in_prompt = ""
            if protagonist_direct:
                protagonist_in_prompt = f"""
PROTAGONIST CHARACTER (MUST be consistent across all scenes):
{protagonist_direct}
"""

            # 최종 프롬프트 조합
            final_prompt = f"""{generated_prompt}
{protagonist_in_prompt}
Art Style: Korean manhwa/webtoon illustration, hand-drawn comic art with ink brush aesthetic, dramatic shadows, traditional Asian painting influence
Color Palette: {color_guide}
Composition: {style_guide.get('composition', '극적인 명암 대비, 실루엣 활용')}

CRITICAL STYLE REQUIREMENTS:
- Korean manhwa/webtoon illustration style (NOT photorealistic!)
- Hand-drawn comic book aesthetic with ink brush strokes
- Traditional Korean historical setting (Joseon dynasty)
- Dramatic lighting and shadow contrast
- NOT 3D render, NOT anime style, NOT photorealistic
- ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO CHARACTERS anywhere in the image
- PROTAGONIST MUST look exactly the same in every scene (same age, build, face, clothing style)

Format: High resolution, {self.aspect_ratio} aspect ratio
CRITICAL: Do NOT render any text, words, letters, or characters on the image. Pure visual illustration only."""

            return final_prompt

        except Exception as e:
            print(f"[ImageEngine] Yadam prompt generation failed: {e}")
            # 폴백: 기본 만화 스타일 프롬프트
            return f"""Korean manhwa illustration style, hand-drawn comic art with ink brush aesthetic:

{narration[:150]}

Art Style: Korean webtoon/manhwa illustration, dramatic ink brush strokes, traditional Asian painting influence
Setting: Traditional Korean historical background (Joseon dynasty)
Color: {color_guide}
Composition: Dramatic shadows, silhouettes, dynamic poses

CRITICAL: Korean manhwa/webtoon illustration style, NOT photorealistic, NOT 3D render
CRITICAL: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS on the image. Pure visual only.
Format: High resolution, {self.aspect_ratio} aspect ratio"""

    def _build_fallback_prompt(self, base_prompt: str, style_guide,
                              scene_id: str, narration: str = "") -> str:
        """
        폴백용 기본 프롬프트 생성 (Claude API 없을 때 사용)
        ★ 주인공 프로필이 있으면 포함
        """
        # ★ style_guide가 dict가 아니면 기본값 사용
        if not isinstance(style_guide, dict):
            style_guide = {
                "style": "Korean traditional illustration",
                "mood": "dramatic and atmospheric",
                "avoid": "modern settings, text, watermarks",
                "composition": "",
                "color_flow": {},
                "art_direction": ""
            }

        # Scene ID에 따른 추가 가이드
        scene_guides = {
            "hook": "attention-grabbing, intriguing opening scene",
            "empathy": "emotional, relatable, warm connection",
            "point1": "clear illustration, informative",
            "point2": "clear illustration, informative",
            "point3": "clear illustration, informative",
            "point4": "clear illustration, informative",
            "summary": "conclusive, peaceful, satisfying",
            "action": "motivating, encouraging, positive energy",
            "story_intro": "storytelling beginning, narrative",
            "old_days": "vintage Korean, nostalgic 1970s-80s",
            "memories": "sentimental, memory-evoking",
            "climax": "emotional peak, touching moment",
            "lesson": "meaningful, wise, thoughtful",
            "comfort": "comforting, warm embrace feeling",
            "changes": "transformation, before-after",
            "nostalgia": "nostalgic, longing, bittersweet",
            # ★ 드라마 모드 전용 scene 가이드
            "situation": "calm daily life, warm beige tones, side profile or back view",
            "development": "conflict rising, darker gray-blue tones, closed doors, empty spaces, symbolic composition",
            "resolution": "silent ending with lingering emotion, symbolic scene (closing door, distant back view, empty room)",
        }

        # ★ 드라마 모드 색조/구도 가이드 적용
        drama_composition_guide = ""
        if style_guide.get('composition'):
            drama_composition_guide = f"\nComposition Guide: {style_guide['composition']}"
        if style_guide.get('color_flow'):
            color_flow = style_guide['color_flow']
            if scene_id in ["hook", "situation"]:
                drama_composition_guide += f"\nColor Tone: {color_flow.get('평온', 'warm tones')}"
            elif scene_id in ["development", "climax"]:
                drama_composition_guide += f"\nColor Tone: {color_flow.get('갈등', 'dark gray tones')}"
            elif scene_id == "resolution":
                drama_composition_guide += f"\nColor Tone: {color_flow.get('해결', 'warm recovery or cold ending')}"

        scene_mood = scene_guides.get(scene_id, "warm and friendly")

        context_hint = ""
        if narration:
            context_hint = f"Context from narration: {narration[:100]}..."

        # ★ 주인공 프로필 정보 추가
        protagonist_hint = ""
        if self._protagonist_profile:
            protagonist_hint = f"""
★ IMPORTANT - Character Consistency:
Protagonist: {self._protagonist_profile['description']}
Setting: {self._protagonist_profile['setting']}
Mood: {self._protagonist_profile['mood_context']}
"""

        # ★ 야담 모드 감지: art_direction 또는 style에 manhwa/webtoon/comic 키워드가 있으면
        art_direction = style_guide.get('art_direction', '')
        style_text = style_guide.get('style', '')
        is_yadam_mode = any(kw in (art_direction + style_text).lower()
                          for kw in ['manhwa', 'webtoon', 'comic', 'illustration', 'ink brush'])

        if is_yadam_mode:
            # ★ 야담 모드: 만화/일러스트 스타일
            enhanced = f"""Korean manhwa/webtoon illustration style, hand-drawn comic art:

{base_prompt}
{protagonist_hint}

Scene type: {scene_mood}
Art Style: Korean traditional manhwa illustration, ink brush aesthetic, dramatic shadows
Mood: {style_guide.get('mood', 'dramatic and atmospheric')}
{drama_composition_guide}

{context_hint}

CRITICAL STYLE REQUIREMENTS:
- Korean manhwa/webtoon illustration style (NOT photorealistic!)
- Hand-drawn comic book aesthetic with ink brush strokes
- Traditional Korean historical setting (Joseon dynasty)
- Dramatic lighting and shadow contrast
- NOT 3D render, NOT anime style, NOT photorealistic
- ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO CHARACTERS anywhere in the image

Technical requirements:
- High quality illustration
- If people are shown: MUST match the protagonist description above
- CRITICAL: Do NOT render any text, words, or letters on the image. Pure visual only.
- {self.aspect_ratio} aspect ratio

Avoid: {style_guide.get('avoid', 'photorealistic, 3D render, modern settings')}, any text or letters
"""
        else:
            # ★ 일반 모드: 사실적 스타일
            enhanced = f"""Photorealistic image for Korean senior YouTube video:

{base_prompt}
{protagonist_hint}

Scene type: {scene_mood}
Style: {style_guide.get('style', 'warm and realistic')}
Mood: {style_guide.get('mood', 'warm and inviting')}
{drama_composition_guide}

{context_hint}

Technical requirements:
- High quality, photorealistic
- Warm, inviting atmosphere suitable for elderly viewers
- Clear composition with single focal point
- Bright, high-contrast colors for visibility
- If people are shown: MUST match the protagonist description above
- CRITICAL: ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS anywhere in the image
- {self.aspect_ratio} aspect ratio

Avoid: {style_guide.get('avoid', 'text, watermarks, low quality')}, any text or letters on the image
"""
        return enhanced.strip()

    def _generate_single_image(self, idx: int, scene: Scene, image_path: str, enhanced_prompt: str, max_retries: int = 3) -> tuple[str, str]:
        """
        단일 이미지 생성 (병렬 처리용, 재시도 로직 포함, Model Router 적용)

        Args:
            idx: Scene 인덱스
            scene: Scene 객체
            image_path: 저장 경로
            enhanced_prompt: 향상된 프롬프트
            max_retries: 최대 재시도 횟수

        Returns:
            (이미지 경로, 상태 메시지) 튜플

        Raises:
            Exception: 모든 재시도 실패 시
        """
        print(f"[ImageEngine] [{idx}] Starting image generation for {scene.scene_id}")

        # ★ Model Router: Scene별 최적 모델 선택
        selected_model = self._select_model_for_scene(scene)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if not self.enabled:
                    # 플레이스홀더 이미지 생성
                    print(f"  [{idx}] Using placeholder")
                    self._create_placeholder_image(image_path, scene.title, enhanced_prompt)
                    return image_path, "⚠️ Placeholder (API 미설정)"

                if attempt > 0:
                    print(f"  [{idx}] Retry {attempt}/{max_retries}")

                # ★ Model Router: 선택된 모델로 이미지 생성
                if selected_model == "dalle3":
                    print(f"  [{idx}] Using DALL-E 3 ({self.dalle3_size}) [ModelRouter]")
                    print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                    try:
                        self._generate_dalle3_image(enhanced_prompt, image_path, size=self.dalle3_size)
                        print(f"  [{idx}] ✓ Success!")
                        return image_path, "✅ DALL-E 3 성공"
                    except Exception as dalle_error:
                        # ★ DALL-E 3 실패 → Gemini로 폴백
                        error_msg = str(dalle_error)
                        if "billing" in error_msg.lower() or "limit" in error_msg.lower() or "400" in error_msg:
                            print(f"  [{idx}] DALL-E 3 실패 (billing/limit) → Gemini로 폴백")
                            try:
                                self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                                print(f"  [{idx}] ✓ Success (Gemini 폴백)!")
                                return image_path, "✅ Gemini 성공 (DALL-E 폴백)"
                            except Exception as gemini_error:
                                print(f"  [{idx}] Gemini도 실패: {gemini_error}")
                                raise dalle_error
                        else:
                            raise dalle_error

                elif selected_model == "dalle2":
                    print(f"  [{idx}] Using DALL-E 2 [ModelRouter]")
                    print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                    try:
                        self._generate_dalle2_image(enhanced_prompt, image_path)
                        print(f"  [{idx}] ✓ Success!")
                        return image_path, "✅ DALL-E 2 성공"
                    except Exception as dalle_error:
                        # ★ DALL-E 2 실패 → Gemini로 폴백
                        error_msg = str(dalle_error)
                        if "billing" in error_msg.lower() or "limit" in error_msg.lower() or "400" in error_msg:
                            print(f"  [{idx}] DALL-E 2 실패 (billing/limit) → Gemini로 폴백")
                            try:
                                self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                                print(f"  [{idx}] ✓ Success (Gemini 폴백)!")
                                return image_path, "✅ Gemini 성공 (DALL-E 폴백)"
                            except Exception as gemini_error:
                                print(f"  [{idx}] Gemini도 실패: {gemini_error}")
                                raise dalle_error
                        else:
                            raise dalle_error

                elif selected_model in ["gemini_flash", "gemini_pro", "gemini_ultra", "gemini_3_pro_image"]:
                    mode_names = {
                        "gemini_flash": "Fast",
                        "gemini_pro": "Standard",
                        "gemini_ultra": "Ultra",
                        "gemini_3_pro_image": "Gemini 3 Pro"
                    }
                    mode = mode_names.get(selected_model, "Standard")
                    model_label = "Gemini 3 Pro Image" if selected_model == "gemini_3_pro_image" else f"Imagen 4.0 ({mode})"
                    print(f"  [{idx}] Using {model_label} [ModelRouter]")
                    print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                    try:
                        self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                        print(f"  [{idx}] ✓ Success!")
                        return image_path, f"✅ {model_label} 성공"
                    except Exception as imagen_error:
                        # ★ Imagen 실패 → DALL-E 3로 즉시 폴백
                        if self.openai_client:
                            print(f"  [{idx}] Imagen 실패 → DALL-E 3로 폴백")
                            self._generate_dalle3_image(enhanced_prompt, image_path, size=self.dalle3_size)
                            print(f"  [{idx}] ✓ Success (DALL-E 3 폴백)!")
                            return image_path, f"✅ DALL-E 3 성공 (Imagen 폴백)"
                        else:
                            raise imagen_error  # DALL-E도 없으면 원래 에러 발생

                elif selected_model == "gpt_image":
                    print(f"  [{idx}] Using GPT Image (DALL-E 3) [ModelRouter]")
                    print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                    try:
                        self._generate_dalle3_image(enhanced_prompt, image_path, size=self.dalle3_size)
                        print(f"  [{idx}] ✓ Success!")
                        return image_path, "✅ GPT Image 성공"
                    except Exception as dalle_error:
                        # ★ DALL-E 3 실패 → Gemini로 폴백
                        error_msg = str(dalle_error)
                        if "billing" in error_msg.lower() or "limit" in error_msg.lower() or "400" in error_msg:
                            print(f"  [{idx}] GPT Image 실패 (billing/limit) → Gemini로 폴백")
                            try:
                                self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                                print(f"  [{idx}] ✓ Success (Gemini 폴백)!")
                                return image_path, "✅ Gemini 성공 (GPT Image 폴백)"
                            except Exception as gemini_error:
                                print(f"  [{idx}] Gemini도 실패: {gemini_error}")
                                raise dalle_error
                        else:
                            raise dalle_error

                else:
                    # 기본 엔진 사용 (환경변수 기반)
                    if self.engine_type in ["gemini_flash", "gemini_pro", "gemini_ultra", "gemini_3_pro_image"]:
                        mode_names = {
                            "gemini_flash": "Fast",
                            "gemini_pro": "Standard",
                            "gemini_ultra": "Ultra",
                            "gemini_3_pro_image": "Gemini 3 Pro"
                        }
                        mode = mode_names.get(self.engine_type, "Standard")
                        model_label = "Gemini 3 Pro Image" if self.engine_type == "gemini_3_pro_image" else f"Imagen 4.0 ({mode})"
                        print(f"  [{idx}] Using {model_label} [Default]")
                        print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                        try:
                            self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                            print(f"  [{idx}] ✓ Success!")
                            return image_path, f"✅ {model_label} 성공"
                        except Exception as imagen_error:
                            # ★ Imagen 실패 → DALL-E 3로 즉시 폴백
                            if self.openai_client:
                                print(f"  [{idx}] Imagen 실패 → DALL-E 3로 폴백")
                                self._generate_dalle3_image(enhanced_prompt, image_path, size=self.dalle3_size)
                                print(f"  [{idx}] ✓ Success (DALL-E 3 폴백)!")
                                return image_path, f"✅ DALL-E 3 성공 (Imagen 폴백)"
                            else:
                                raise imagen_error
                    elif self.engine_type == "dalle3":
                        print(f"  [{idx}] Using DALL-E 3 [Default]")
                        print(f"  [{idx}] Prompt: {enhanced_prompt[:100]}...")
                        try:
                            self._generate_dalle3_image(enhanced_prompt, image_path, size=self.dalle3_size)
                            print(f"  [{idx}] ✓ Success!")
                            return image_path, "✅ DALL-E 3 성공"
                        except Exception as dalle_error:
                            # ★ DALL-E 3 실패 → Gemini로 폴백
                            error_msg = str(dalle_error)
                            if "billing" in error_msg.lower() or "limit" in error_msg.lower() or "400" in error_msg:
                                print(f"  [{idx}] DALL-E 3 실패 (billing/limit) → Gemini로 폴백")
                                try:
                                    self._generate_imagen_image(enhanced_prompt, image_path, self.aspect_ratio)
                                    print(f"  [{idx}] ✓ Success (Gemini 폴백)!")
                                    return image_path, "✅ Gemini 성공 (DALL-E 폴백)"
                                except Exception as gemini_error:
                                    print(f"  [{idx}] Gemini도 실패: {gemini_error}")
                                    raise dalle_error
                            else:
                                raise dalle_error
                    else:
                        print(f"  [{idx}] Using placeholder")
                        self._create_placeholder_image(image_path, scene.title, enhanced_prompt)
                        return image_path, "⚠️ Placeholder (API 미설정)"

            except Exception as e:
                last_error = e
                print(f"  [{idx}] ✗ Attempt {attempt + 1} failed: {str(e)[:100]}")

                if attempt < max_retries:
                    # 지수 백오프: 2초, 4초
                    wait_time = 2 ** attempt
                    print(f"  [{idx}] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    print(f"  [{idx}] All retries exhausted")

        # 모든 재시도 실패 - Pexels 대체 시도
        print(f"  [{idx}] All retries failed, trying Pexels fallback...")
        return self._fallback_to_pexels_image(scene, image_path, scene.image_prompt)

    def generate_thumbnail(self, prompt: str, text: str, output_path: str,
                          category: str = "general") -> str:
        """
        썸네일 이미지 생성 (텍스트 없는 배경 + 후킹 제목 오버레이)
        ★ 야담 모드: 주인공 프로필을 썸네일에도 적용하여 일관성 유지

        Args:
            prompt: 이미지 프롬프트
            text: 썸네일에 들어갈 후킹 제목 (큰 글씨로 오버레이)
            output_path: 저장 경로
            category: 카테고리

        Returns:
            생성된 썸네일 경로
        """
        if not self.enabled:
            print("[ImageEngine] Skipping thumbnail generation (API not configured)")
            self._create_placeholder_thumbnail(output_path, text)
            return output_path

        # 카테고리별 스타일 가이드
        style_guide = SENIOR_IMAGE_STYLES.get(category, SENIOR_IMAGE_STYLES["general"])

        # ★ 야담 모드: 주인공 프로필을 썸네일에 포함
        protagonist_section = ""
        if category == "yadam" and hasattr(self, '_protagonist_profile') and self._protagonist_profile:
            protagonist_desc = self._protagonist_profile.get('description', '')
            if protagonist_desc:
                protagonist_section = f"""
★★★ PROTAGONIST (Main Character - MUST be in thumbnail):
{protagonist_desc}
The protagonist should be prominently featured in the thumbnail, positioned on the left side.
★★★
"""
                print(f"[ImageEngine] ★ 썸네일에 주인공 프로필 적용: {protagonist_desc[:50]}...")

        # 썸네일용 프롬프트 (텍스트 없이!)
        thumbnail_prompt = f"""YouTube thumbnail background image, NO TEXT, NO LETTERS, NO WORDS:
{prompt}
{protagonist_section}
Style: {style_guide['style']}
Mood: {style_guide['mood']}
Composition: Clean background with space for text overlay, rule of thirds, main character on LEFT side
Colors: High contrast, vibrant, eye-catching
Quality: High resolution, 1280x720 thumbnail format, professional

CRITICAL: Do NOT include any text, letters, numbers, or words in the image.
This is a background image only. Text will be added separately.

Senior-targeted YouTube thumbnail style
"""

        temp_bg_path = output_path.replace(".png", "_bg.png")

        try:
            print(f"[ImageEngine] Generating thumbnail background (no text)")

            # ★ 썸네일은 항상 Gemini/Imagen 우선 사용 (engine_type 무관)
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            thumbnail_generated = False

            if gemini_api_key:
                try:
                    print(f"  ★ Using Gemini/Imagen 4.0 for thumbnail")
                    self._generate_imagen_thumbnail(thumbnail_prompt, temp_bg_path)
                    thumbnail_generated = True
                except Exception as e:
                    print(f"  ⚠️ Gemini/Imagen 실패: {e}")

            # Gemini 실패 시 DALL-E 폴백
            if not thumbnail_generated and self.openai_client:
                try:
                    print(f"  → DALL-E 3로 폴백")
                    self._generate_dalle3_image(thumbnail_prompt, temp_bg_path, size="1024x1024")
                    thumbnail_generated = True
                except Exception as e:
                    print(f"  ⚠️ DALL-E 3 실패: {e}")

            # 모두 실패 시 플레이스홀더
            if not thumbnail_generated:
                print(f"  → 플레이스홀더 사용")
                self._create_placeholder_thumbnail(output_path, text)
                return output_path

            # 배경 이미지에 후킹 제목 오버레이
            print(f"[ImageEngine] Overlaying hooking title: {text}")
            self._overlay_thumbnail_text(temp_bg_path, text, output_path, category)

            # 임시 배경 파일 삭제
            if os.path.exists(temp_bg_path):
                os.remove(temp_bg_path)

        except Exception as e:
            print(f"[ImageEngine] Error generating thumbnail: {e}")
            self._create_placeholder_thumbnail(output_path, text)

        return output_path

    def _overlay_thumbnail_text(self, bg_path: str, text: str, output_path: str, category: str = "general"):
        """
        썸네일 배경에 후킹 제목 오버레이
        ★ 화면 정중앙 배치, 큰 텍스트, 두꺼운 외곽선 강조
        - 텍스트는 화면 정중앙에 크게 배치
        - 두꺼운 외곽선(stroke)으로 가독성 확보
        - 카테고리별 색상 스키마 적용

        Args:
            bg_path: 배경 이미지 경로
            text: 후킹 제목 텍스트
            output_path: 최종 썸네일 저장 경로
            category: 카테고리 (스타일 결정용)
        """
        # 배경 이미지 로드 및 리사이즈
        bg_img = Image.open(bg_path).convert("RGBA")
        bg_img = bg_img.resize((1280, 720), Image.LANCZOS)

        # ★ 모든 모드 통합 템플릿 (중앙 하단, 두꺼운 외곽선)
        templates = {
            # 야담/역사 - 검정 외곽선 + 흰색/노랑 텍스트
            "yadam": {
                "text_main": (255, 255, 100),      # 밝은 노랑
                "text_outline": (0, 0, 0),          # 검정 외곽선
                "stroke_width": 10,                 # 두꺼운 외곽선
                "overlay_alpha": 80
            },
            "history": {
                "text_main": (255, 255, 255),      # 흰색
                "text_outline": (0, 0, 0),          # 검정 외곽선
                "stroke_width": 10,
                "overlay_alpha": 80
            },
            # 드라마 - 흰색 텍스트 + 검정/빨강 외곽선
            "drama": {
                "text_main": (255, 255, 255),
                "text_outline": (50, 0, 0),         # 어두운 빨강 외곽선
                "stroke_width": 10,
                "overlay_alpha": 70
            },
            # 감성/추억 - 따뜻한 크림색 + 갈색 외곽선
            "emotion": {
                "text_main": (255, 255, 200),      # 따뜻한 크림색
                "text_outline": (60, 30, 0),        # 갈색 외곽선
                "stroke_width": 9,
                "overlay_alpha": 60
            },
            "emotional": {
                "text_main": (255, 255, 200),
                "text_outline": (60, 30, 0),
                "stroke_width": 9,
                "overlay_alpha": 60
            },
            "memory": {
                "text_main": (255, 248, 220),
                "text_outline": (80, 40, 0),
                "stroke_width": 9,
                "overlay_alpha": 50
            },
            "nostalgic": {
                "text_main": (255, 248, 220),
                "text_outline": (80, 40, 0),
                "stroke_width": 9,
                "overlay_alpha": 50
            },
            # 건강/재테크/정보 - 흰색 + 네이비 외곽선
            "health": {
                "text_main": (255, 255, 255),
                "text_outline": (0, 30, 60),        # 네이비 외곽선
                "stroke_width": 9,
                "overlay_alpha": 70
            },
            "money": {
                "text_main": (255, 230, 100),      # 골드색
                "text_outline": (0, 30, 60),
                "stroke_width": 9,
                "overlay_alpha": 70
            },
            "knowledge": {
                "text_main": (255, 255, 255),
                "text_outline": (0, 40, 80),
                "stroke_width": 9,
                "overlay_alpha": 65
            },
            "wisdom": {
                "text_main": (255, 255, 220),
                "text_outline": (40, 40, 40),
                "stroke_width": 9,
                "overlay_alpha": 60
            },
            "classic": {
                "text_main": (255, 240, 200),      # 고급스러운 크림색
                "text_outline": (60, 30, 0),
                "stroke_width": 9,
                "overlay_alpha": 60
            },
            # 유아 - 밝은 노랑 + 핫핑크 외곽선
            "kids": {
                "text_main": (255, 255, 0),        # 밝은 노랑
                "text_outline": (200, 50, 100),    # 핫핑크 외곽선
                "stroke_width": 10,
                "overlay_alpha": 30
            },
            # 기본 템플릿
            "general": {
                "text_main": (255, 255, 255),
                "text_outline": (0, 0, 0),
                "stroke_width": 9,
                "overlay_alpha": 70
            }
        }

        style = templates.get(category, templates["general"])

        # 텍스트 레이어 생성
        txt_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        # ★ 한글 손글씨 폰트 우선 (부드러운 느낌)
        # 프로젝트 fonts 폴더 경로
        project_fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        font_paths = [
            # 1순위: 프로젝트 내 손글씨 폰트
            os.path.join(project_fonts_dir, "NanumPenScript.ttf"),
            os.path.join(project_fonts_dir, "NanumBarunPen.ttf"),
            os.path.join(project_fonts_dir, "NanumBrush.ttf"),
            # 2순위: 시스템 손글씨 폰트
            "/usr/share/fonts/truetype/nanum/NanumPen.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBrush.ttf",
            # 3순위: 시스템 고딕 폰트 (폴백)
            "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
            "C:\\Windows\\Fonts\\malgunbd.ttf",  # Windows
        ]

        font = None
        font_size = 110  # ★ 크게 (기존 90 → 110)
        used_font_path = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, font_size)
                    used_font_path = fp
                    print(f"  ✓ 썸네일 폰트 로드: {os.path.basename(fp)}")
                    break
                except Exception as e:
                    print(f"  ⚠️ 폰트 로드 실패 ({os.path.basename(fp)}): {e}")
                    continue

        if font is None:
            font = ImageFont.load_default()
            print("  ⚠️ Using default font (Korean may not render properly)")

        # 텍스트 줄바꿈 처리 (8자 초과 시)
        lines = text.split('\n')
        if len(lines) == 1 and len(text) > 10:
            mid = len(text) // 2
            space_idx = text.find(' ', mid - 3)
            if space_idx != -1 and space_idx < len(text) - 2:
                lines = [text[:space_idx].strip(), text[space_idx:].strip()]
            else:
                lines = [text[:mid].strip(), text[mid:].strip()]

        # 텍스트 크기 계산
        line_heights = []
        line_widths = []
        for line in lines:
            if line:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            else:
                line_widths.append(0)
                line_heights.append(0)

        line_spacing = 15
        total_height = sum(line_heights) + (len(lines) - 1) * line_spacing
        max_width = max(line_widths) if line_widths else 0

        # 텍스트가 너무 넓으면 폰트 크기 조정
        max_text_width = 1180  # 양쪽 여백 50px씩
        if max_width > max_text_width:
            scale = max_text_width / max_width * 0.95
            new_font_size = int(font_size * scale)
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, new_font_size)
                        break
                    except:
                        continue
            # 크기 재계산
            line_heights = []
            line_widths = []
            for line in lines:
                if line:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_widths.append(bbox[2] - bbox[0])
                    line_heights.append(bbox[3] - bbox[1])
            total_height = sum(line_heights) + (len(lines) - 1) * line_spacing

        # ★ 화면 정중앙 배치
        start_y = (720 - total_height) // 2

        # 중앙 그라데이션 오버레이 (텍스트 가독성 향상)
        gradient = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)
        # 중앙 주변에 어두운 띠 추가
        center_y = 360
        band_height = 200
        for y in range(center_y - band_height, center_y + band_height):
            # 중앙으로 갈수록 진해지는 그라데이션
            dist = abs(y - center_y)
            alpha = int(style["overlay_alpha"] * (1 - dist / band_height))
            gradient_draw.line([(0, y), (1280, y)], fill=(0, 0, 0, alpha))
        bg_img = Image.alpha_composite(bg_img, gradient)

        # ★ 텍스트 그리기 (화면 정중앙)
        stroke_width = style["stroke_width"]
        current_y = start_y

        for i, line in enumerate(lines):
            if not line:
                continue

            # 중앙 정렬
            x = (1280 - line_widths[i]) // 2

            # 1. 그림자 (아래로 오프셋)
            shadow_offset = 5
            for dx in range(-2, 3):
                for dy in range(3, 8):
                    draw.text(
                        (x + dx, current_y + dy),
                        line, font=font,
                        fill=(0, 0, 0, 100)
                    )

            # 2. 외곽선 (두꺼운 stroke) - ★ 핵심
            for dx in range(-stroke_width, stroke_width + 1):
                for dy in range(-stroke_width, stroke_width + 1):
                    if dx * dx + dy * dy <= stroke_width * stroke_width:  # 원형 마스크
                        draw.text(
                            (x + dx, current_y + dy),
                            line, font=font,
                            fill=(*style["text_outline"], 255)
                        )

            # 3. 본문 텍스트 (메인 색상)
            draw.text((x, current_y), line, font=font, fill=(*style["text_main"], 255))

            current_y += line_heights[i] + line_spacing

        # 레이어 합성
        final_img = Image.alpha_composite(bg_img, txt_layer)
        final_img = final_img.convert("RGB")
        final_img.save(output_path, quality=95)

        print(f"  ✅ 썸네일 생성 완료")
        print(f"     - 템플릿: {category}")
        print(f"     - 텍스트 위치: 중앙 하단")
        print(f"     - 외곽선 두께: {stroke_width}px")

    def _create_placeholder_image(self, path: str, title: str, prompt: str):
        """
        플레이스홀더 이미지 생성 (이미지 생성 실패 시 사용)
        ★ 텍스트 없이 깔끔한 그라데이션 배경으로 생성
        """
        # 비디오 해상도에 맞게 이미지 생성
        img = Image.new('RGB', (self.video_width, self.video_height))

        # ★ 야담/전통 스타일에 어울리는 그라데이션 배경
        # 위에서 아래로 어두운 네이비 → 검정 그라데이션
        for y in range(self.video_height):
            ratio = y / self.video_height
            # 네이비 블루 → 검정
            r = int(20 * (1 - ratio * 0.7))
            g = int(30 * (1 - ratio * 0.7))
            b = int(50 * (1 - ratio * 0.5))
            for x in range(self.video_width):
                img.putpixel((x, y), (r, g, b))

        # ★ 텍스트 없이 저장 (자막이 대신 보여줄 것임)
        img.save(path)
        print(f"  Created placeholder: {path}")

    def _generate_imagen_thumbnail(self, prompt: str, output_path: str):
        """
        Imagen 4.0으로 썸네일 배경 이미지 생성
        """
        try:
            from google import genai
            from google.genai import types

            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                raise Exception("GEMINI_API_KEY not set")

            client = genai.Client(api_key=gemini_api_key)

            # 썸네일용 1:1 비율로 생성 (나중에 1280x720으로 조정)
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    safety_filter_level="block_low_and_above",
                    person_generation="allow_adult",
                )
            )

            if response.generated_images and len(response.generated_images) > 0:
                response.generated_images[0].image.save(output_path)
                print(f"  ✓ Imagen thumbnail saved: {output_path}")
                return output_path
            else:
                raise Exception("Imagen 응답에 이미지 없음")

        except Exception as e:
            print(f"  ⚠️ Imagen thumbnail 실패: {e}")
            # DALL-E 폴백
            if self.openai_client:
                print(f"  → DALL-E 3로 폴백")
                return self._generate_dalle3_image(prompt, output_path, size="1792x1024")
            raise

    def _create_placeholder_thumbnail(self, path: str, text: str):
        """
        플레이스홀더 썸네일 생성
        ★ CTR 최적화 레이아웃 적용 (인물 왼쪽, 텍스트 오른쪽)
        """
        # 1280x720 썸네일
        img = Image.new('RGBA', (1280, 720), color=(30, 50, 80, 255))  # 네이비 배경
        draw = ImageDraw.Draw(img)

        # 왼쪽에 인물 영역 표시 (회색 원형)
        draw.ellipse([(100, 160), (500, 560)], fill=(60, 80, 110, 255))
        draw.text((230, 340), "👤", fill=(255, 255, 255, 150))

        # 오른쪽 영역 배경 (반투명)
        draw.rectangle([(590, 0), (1280, 720)], fill=(0, 0, 0, 80))

        # ★ 손글씨 폰트 우선 사용
        project_fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        font_paths = [
            os.path.join(project_fonts_dir, "NanumPenScript.ttf"),
            os.path.join(project_fonts_dir, "NanumBarunPen.ttf"),
            os.path.join(project_fonts_dir, "NanumBrush.ttf"),
            "/usr/share/fonts/truetype/nanum/NanumPen.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, 70)
                    break
                except:
                    continue
        if font is None:
            font = ImageFont.load_default()

        # 텍스트 줄바꿈
        lines = text.split('\n')
        if len(lines) == 1 and len(text) > 8:
            mid = len(text) // 2
            lines = [text[:mid], text[mid:]]

        # 텍스트 크기 계산
        line_heights = []
        line_widths = []
        for line in lines:
            if line:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            else:
                line_widths.append(0)
                line_heights.append(0)

        total_height = sum(line_heights) + (len(lines) - 1) * 15

        # ★ 오른쪽 영역에 텍스트 배치
        right_start = 640
        text_area_width = 1230 - right_start
        start_y = (720 - total_height) // 2

        current_y = start_y
        for i, line in enumerate(lines):
            if not line:
                continue

            # 오른쪽 영역에서 중앙 정렬
            x = right_start + (text_area_width - line_widths[i]) // 2

            # 외곽선
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, current_y + dy), line,
                                fill=(0, 51, 102, 255), font=font)

            # 본문 (흰색)
            draw.text((x, current_y), line, fill=(255, 255, 255, 255), font=font)
            current_y += line_heights[i] + 15

        # 하단에 "PLACEHOLDER" 표시
        try:
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            small_font = font
        draw.text((1100, 680), "PLACEHOLDER", fill=(100, 100, 100, 200), font=small_font)

        img = img.convert("RGB")
        img.save(path, quality=95)
        print(f"  Created placeholder thumbnail (CTR layout): {path}")

    def _wrap_text(self, text: str, width: int) -> str:
        """텍스트 줄바꿈"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def _fallback_to_pexels_image(self, scene, output_path: str, search_query: str) -> tuple[str, str]:
        """
        이미지 생성 실패 시 Pexels 스톡 이미지로 대체 + 자막 표시

        Args:
            scene: Scene 객체 (narration 텍스트 포함)
            output_path: 저장 경로
            search_query: Pexels 검색 키워드 (보통 image_prompt)

        Returns:
            (image_path, status_message) 튜플
        """
        print(f"  🔄 [Pexels Fallback] Searching for: '{search_query}'")

        if not self.pexels_enabled:
            print(f"  ⚠️ Pexels API key not configured, using placeholder")
            self._create_placeholder_image(output_path, scene.title, f"No API: {search_query}")
            return output_path, "❌ Pexels API 키 없음 → Placeholder"

        try:
            # 1. Pexels Photos API로 이미지 검색
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": search_query,
                "per_page": 5,
                "orientation": "landscape",  # 1920x1080 가로 이미지
            }

            response = requests.get(
                self.PEXELS_PHOTOS_API_URL,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                raise Exception(f"Pexels API error: {response.status_code}")

            data = response.json()
            photos = data.get("photos", [])

            if not photos:
                raise Exception(f"No photos found for: {search_query}")

            # 첫 번째 이미지 선택 (가장 관련성 높은 것)
            photo = photos[0]
            image_url = photo["src"]["large2x"]  # 1920x1280 크기

            # 2. 이미지 다운로드
            print(f"  ⬇️  Downloading from Pexels...")
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()

            # 임시 파일로 저장
            temp_path = output_path.replace(".png", "_temp.jpg")
            with open(temp_path, 'wb') as f:
                f.write(image_response.content)

            # 3. PIL로 이미지 열기 및 텍스트 오버레이
            img = Image.open(temp_path)

            # 1920x1080으로 리사이즈 (crop)
            img = img.resize((1920, 1080), Image.Resampling.LANCZOS)

            # 반투명 검은색 오버레이 (자막 배경)
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 150))
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)

            draw = ImageDraw.Draw(img)

            # 4. 씬 대사(narration)를 화면 중앙에 표시
            narration = scene.narration if hasattr(scene, 'narration') else scene.title
            wrapped_text = self._wrap_text(narration, width=40)  # 40자마다 줄바꿈

            # 폰트 설정
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
            except:
                font = ImageFont.load_default()

            # 텍스트 중앙 정렬
            bbox = draw.textbbox((0, 0), wrapped_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (1920 - text_width) // 2
            y = (1080 - text_height) // 2

            # 텍스트 그리기 (흰색, 약간의 그림자 효과)
            # 그림자 (검은색)
            draw.text((x+2, y+2), wrapped_text, fill=(0, 0, 0, 255), font=font)
            # 본문 (흰색)
            draw.text((x, y), wrapped_text, fill=(255, 255, 255, 255), font=font)

            # 5. PNG로 저장
            img = img.convert('RGB')
            img.save(output_path)

            # 임시 파일 삭제
            os.remove(temp_path)

            print(f"  ✅ Pexels image saved with subtitle: {output_path}")
            return output_path, f"⚠️ Pexels 대체: '{search_query}'"

        except Exception as e:
            print(f"  ✗ Pexels fallback failed: {e}")
            self._create_placeholder_image(output_path, scene.title, f"Pexels Error: {str(e)[:30]}")
            return output_path, f"❌ Pexels 실패 → Placeholder"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=16),
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def _generate_dalle3_image(self, prompt: str, output_path: str, size: str = "1024x1792") -> str:
        """
        DALL-E 3로 이미지 생성 및 다운로드

        tenacity 재시도 로직:
        - 최대 3회 시도
        - 지수 백오프: 4초 → 8초 → 16초

        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 저장 경로
            size: 이미지 크기 (1024x1024, 1024x1792, 1792x1024)

        Returns:
            저장된 이미지 경로
        """
        try:
            # DALL-E 3 프롬프트는 영어로 번역하면 더 좋은 결과가 나옴
            # 하지만 한국어도 지원하므로 그대로 사용
            # 프롬프트 길이 제한 (4000자)
            if len(prompt) > 4000:
                prompt = prompt[:4000]

            # DALL-E 3 API 호출
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality="standard",  # "standard" or "hd"
                n=1,
            )

            # 생성된 이미지 URL
            image_url = response.data[0].url

            # 이미지 다운로드
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()

            # 파일 저장
            with open(output_path, 'wb') as f:
                f.write(image_response.content)

            print(f"  ✓ DALL-E 3 image saved: {output_path}")
            return output_path

        except Exception as e:
            print(f"  ✗ DALL-E 3 error: {e}")
            # 실패 시 플레이스홀더로 폴백
            self._create_placeholder_image(output_path, "DALL-E Error", str(e))
            return output_path

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=16),
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def _generate_dalle2_image(self, prompt: str, output_path: str, size: str = "1024x1024") -> str:
        """
        DALL-E 2로 이미지 생성 및 다운로드

        DALL-E 2 특징:
        - DALL-E 3보다 빠르고 저렴 ($0.02 vs $0.04)
        - 품질은 약간 낮지만 대부분의 용도에 충분
        - 1024x1024만 지원 (세로/가로 비율 변경 불가)

        tenacity 재시도 로직:
        - 최대 3회 시도
        - 지수 백오프: 4초 → 8초 → 16초

        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 저장 경로
            size: 이미지 크기 (1024x1024만 지원)

        Returns:
            저장된 이미지 경로
        """
        try:
            # 프롬프트 길이 제한 (1000자)
            if len(prompt) > 1000:
                prompt = prompt[:1000]

            # DALL-E 2 API 호출
            response = self.openai_client.images.generate(
                model="dall-e-2",
                prompt=prompt,
                size=size,  # DALL-E 2는 1024x1024, 512x512, 256x256만 지원
                n=1,
            )

            # 생성된 이미지 URL
            image_url = response.data[0].url

            # 이미지 다운로드
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()

            # 파일 저장
            with open(output_path, 'wb') as f:
                f.write(image_response.content)

            print(f"  ✓ DALL-E 2 image saved: {output_path}")
            return output_path

        except Exception as e:
            print(f"  ✗ DALL-E 2 error: {e}")
            # 실패 시 플레이스홀더로 폴백
            self._create_placeholder_image(output_path, "DALL-E 2 Error", str(e))
            return output_path

    def _prepare_prompt_for_imagen(self, prompt: str) -> str:
        """
        ★ Imagen용 프롬프트 사전 순화 (처음부터 적용)

        Imagen은 DALL-E보다 안전 필터가 더 엄격하므로,
        처음부터 순화된 프롬프트를 보내야 성공률이 높음.

        Args:
            prompt: 원본 프롬프트

        Returns:
            순화된 프롬프트 (처음 시도용)
        """
        if not prompt:
            return "Korean traditional manhwa illustration style, beautiful scenic background"

        # 1. 기본 순화 적용 (aggressive=True로 강하게)
        prepared = sanitize_for_dalle(prompt, aggressive=True)

        # 2. [DIALOGUE] 및 기타 태그 제거
        prepared = re.sub(r'\[.*?\]', '', prepared, flags=re.DOTALL)
        prepared = re.sub(r'\(.*?\)', '', prepared)

        # 3. 감정/폭력 관련 영어 단어 제거 (Imagen 필터 우회)
        remove_patterns = [
            # 감정적 표현
            r'\b(fear|scared|terrified|anxious|nervous|worried|sad|crying|tears|anger|angry|rage)\b',
            r'\b(gaunt|pale|hollow|sunken|trembling|shaking|weak|frail|starving)\b',
            r'\b(desperate|despair|hopeless|miserable|wretched|suffering|pain|agony)\b',
            # 폭력/갈등
            r'\b(conflict|struggle|fight|battle|attack|victim|helpless|abuse|violence|violent)\b',
            r'\b(dark|shadow|sinister|ominous|menacing|threatening|evil|wicked|cruel)\b',
            r'\b(blood|bloody|wound|injured|hurt|dead|death|kill|murder|corpse)\b',
            r'\b(ghost|demon|spirit|haunted|curse|cursed|horror|scary|frightening)\b',
            # 신체 관련
            r'\b(naked|nude|bare|exposed|undressed)\b',
        ]

        for pattern in remove_patterns:
            prepared = re.sub(pattern, '', prepared, flags=re.IGNORECASE)

        # 4. 한국어 위험 단어 추가 제거 (sanitize_for_dalle에서 놓친 것들)
        korean_remove = [
            '무서운', '두려운', '공포', '겁에 질린', '불안한',
            '고통', '괴로운', '슬픈', '울며', '눈물',
            '피투성이', '상처투성이', '다친', '죽은', '시체',
            '귀신', '유령', '악령', '저주받은', '무덤',
        ]
        for word in korean_remove:
            prepared = prepared.replace(word, '')

        # 5. 중복 공백/줄바꿈 정리
        prepared = re.sub(r'\s+', ' ', prepared).strip()

        # 6. 프롬프트가 비어버렸으면 기본 프롬프트 반환
        if len(prepared) < 20:
            return "Korean traditional manhwa illustration style, beautiful Joseon era landscape, serene atmosphere"

        # 7. 만화 스타일 프리픽스 추가 (아직 없으면)
        if 'manhwa' not in prepared.lower() and 'anime' not in prepared.lower():
            prepared = "Korean traditional manhwa illustration style, " + prepared

        # 8. 길이 제한 (Imagen은 긴 프롬프트에 민감)
        if len(prepared) > 800:
            prepared = prepared[:800]

        return prepared

    def _simplify_prompt_for_imagen_retry(self, prompt: str) -> str:
        """
        ★ Imagen 재시도용 프롬프트 (더 강력하게 단순화)

        첫 시도가 실패했을 때, 핵심 시각 요소만 남기고
        극도로 단순화한 프롬프트로 재시도.

        Args:
            prompt: 원본 프롬프트

        Returns:
            극도로 단순화된 프롬프트 (재시도용)
        """
        # 1. 핵심 키워드만 추출 시도
        # 배경/장소 관련 단어 추출
        scene_keywords = []

        # 장소 키워드
        place_patterns = [
            r'(marketplace|market|tavern|inn|village|mountain|forest|river|ocean|sea|house|mansion|palace|temple|shrine)',
            r'(hanok|countryside|city|town|road|path|garden|courtyard|room|hall)',
            r'(조선|한옥|시장|마을|산|숲|강|바다|집|궁궐|절|사당)',
        ]

        for pattern in place_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            scene_keywords.extend(matches)

        # 시간/분위기 키워드
        mood_patterns = [
            r'(sunset|sunrise|night|day|morning|evening|dawn|dusk)',
            r'(rainy|sunny|cloudy|foggy|snowy|moonlit)',
        ]

        for pattern in mood_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            scene_keywords.extend(matches)

        # 2. 추출된 키워드로 간단한 프롬프트 구성
        if scene_keywords:
            keywords_str = ", ".join(set(scene_keywords[:5]))  # 최대 5개
            simple_prompt = f"Korean traditional manhwa illustration style, beautiful {keywords_str}, serene atmosphere, detailed background, anime art"
        else:
            # 키워드 추출 실패 시 기본 프롬프트
            simple_prompt = "Korean traditional manhwa illustration style, beautiful Joseon era landscape, traditional Korean village, serene atmosphere, anime background art"

        return simple_prompt

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=16),
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def _generate_imagen_image(self, prompt: str, output_path: str, aspect_ratio: str = "16:9") -> str:
        """
        Imagen 이미지 생성

        두 가지 방법 지원:
        1. GEMINI_API_KEY + google-generativeai의 ImageGenerationModel (Imagen 3)
        2. Vertex AI + key.json (Imagen 2)

        ★ 처음부터 프롬프트를 순화해서 성공률 향상

        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 저장 경로
            aspect_ratio: 이미지 비율 ("9:16", "16:9", "1:1", "4:3", "3:4")

        Returns:
            저장된 이미지 경로
        """
        try:
            # ★ 처음부터 프롬프트 순화 (Imagen 성공률 극대화)
            original_prompt = prompt
            prepared_prompt = self._prepare_prompt_for_imagen(prompt)
            print(f"  📝 원본 프롬프트 ({len(original_prompt)}자) → 순화 ({len(prepared_prompt)}자)")

            # 종횡비 매핑
            aspect_ratio_map = {
                "1:1": "1:1",
                "9:16": "9:16",
                "16:9": "16:9",
                "4:3": "4:3",
                "3:4": "3:4"
            }
            target_aspect_ratio = aspect_ratio_map.get(aspect_ratio, "1:1")

            # ★ 방법 1: google-genai 패키지로 Imagen 4.0 사용 (우선 시도)
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if gemini_api_key:
                # 방법 1-A: google-genai 패키지 (최신)
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=gemini_api_key)

                    # Imagen 4.0 모델 선택 (engine_type 기반) - 2025년 GA 버전
                    # gemini_flash → imagen-4.0-fast-generate-001 (빠른 생성, $0.02/장)
                    # gemini_pro → imagen-4.0-generate-001 (표준 품질, $0.04/장)
                    # gemini_ultra → imagen-4.0-ultra-generate-001 (최고 품질, $0.06/장)
                    # gemini_3_pro_image → gemini-3-pro-image-preview (AI 이미지, $0.134/장)
                    model_map = {
                        "gemini_flash": "imagen-4.0-fast-generate-001",
                        "gemini_pro": "imagen-4.0-generate-001",
                        "gemini_ultra": "imagen-4.0-ultra-generate-001",
                        "gemini_3_pro_image": "gemini-3-pro-image-preview",
                    }
                    model_name = model_map.get(self.engine_type, "imagen-4.0-generate-001")

                    try:
                        print(f"  🎨 Imagen 4.0 ({model_name}) 이미지 생성 중...")

                        # ★ 순화된 프롬프트로 첫 시도
                        response = client.models.generate_images(
                            model=model_name,
                            prompt=prepared_prompt,
                            config=types.GenerateImagesConfig(
                                number_of_images=1,
                                aspect_ratio=target_aspect_ratio,
                                safety_filter_level="block_low_and_above",
                                person_generation="allow_adult",
                            )
                        )

                        if response.generated_images and len(response.generated_images) > 0:
                            response.generated_images[0].image.save(output_path)
                            print(f"  ✓ Imagen 4.0 image saved: {output_path}")
                            return output_path
                        else:
                            print(f"  ⚠️ Imagen 4.0 응답에 이미지 없음 → 극단적 단순화 후 재시도")

                            # ★ 재시도: 원본에서 핵심 키워드만 추출한 완전히 다른 프롬프트 사용
                            retry_prompt = self._simplify_prompt_for_imagen_retry(original_prompt)
                            print(f"  🔄 키워드 기반 재시도 프롬프트 ({len(retry_prompt)}자)")

                            retry_response = client.models.generate_images(
                                model=model_name,
                                prompt=retry_prompt,
                                config=types.GenerateImagesConfig(
                                    number_of_images=1,
                                    aspect_ratio=target_aspect_ratio,
                                    safety_filter_level="block_low_and_above",
                                    person_generation="allow_adult",
                                )
                            )

                            if retry_response.generated_images and len(retry_response.generated_images) > 0:
                                retry_response.generated_images[0].image.save(output_path)
                                print(f"  ✓ Imagen 4.0 재시도 성공: {output_path}")
                                return output_path
                            else:
                                print(f"  ⚠️ Imagen 4.0 재시도도 실패")

                    except Exception as model_error:
                        error_str = str(model_error)
                        if "404" in error_str or "not found" in error_str.lower():
                            print(f"  ⚠️ Imagen 4.0 모델 접근 불가")
                        elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            # ★ 할당량 초과: 바로 DALL-E 폴백 (대기 없음)
                            print(f"  ⚠️ Imagen 할당량 초과 → DALL-E 폴백")
                            print(f"  📋 에러 상세: {error_str[:200]}")
                        else:
                            print(f"  ⚠️ Imagen 4.0 실패: {error_str[:100]}")

                    # Imagen 실패 시 DALL-E 폴백 (배경만 생성)
                    print(f"  🔄 DALL-E 3로 폴백 시도 (배경 전용)...")
                    if self.openai_client:
                        return self._generate_dalle3_image(prompt, output_path, size=self.dalle3_size)
                    else:
                        print(f"  ❌ DALL-E 폴백 불가 (OpenAI API 키 없음)")

                except ImportError:
                    print(f"  ⚠️ google-genai 패키지 없음")
                    print(f"  💡 설치: pip install google-genai")
                    # DALL-E 폴백
                    if self.openai_client:
                        print(f"  [Fallback] DALL-E 3로 대체 생성...")
                        return self._generate_dalle3_image(prompt, output_path, size=self.dalle3_size)
                except Exception as genai_error:
                    print(f"  ⚠️ Imagen 4.0 실패: {genai_error}")
                    # DALL-E 폴백
                    if self.openai_client:
                        print(f"  [Fallback] DALL-E 3로 대체 생성...")
                        return self._generate_dalle3_image(prompt, output_path, size=self.dalle3_size)

            # ★ 방법 2: Vertex AI 사용 (key.json 파일 필요)
            try:
                from vertexai.preview.vision_models import ImageGenerationModel as VertexImageModel

                print(f"  🎨 Imagen 2 (Vertex AI) 이미지 생성 중...")

                # 간소화된 인증 (key.json 파일 사용)
                auth = GoogleAuthManager(
                    key_file="key.json",
                    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                )

                if not auth.authenticate():
                    raise Exception("Vertex AI 인증 실패. key.json 파일을 프로젝트 루트에 넣어주세요.")

                # Imagen 2 모델 로드 (imagegeneration@006)
                model = VertexImageModel.from_pretrained("imagegeneration@006")

                # 이미지 생성
                images = model.generate_images(
                    prompt=prompt,
                    number_of_images=1,
                    aspect_ratio=target_aspect_ratio,
                    safety_filter_level="block_low_and_above",
                    person_generation="allow_adult",
                )

                # 이미지 저장
                images[0].save(location=output_path, include_generation_parameters=False)

                print(f"  ✓ Imagen 2 (Vertex AI) image saved: {output_path}")
                return output_path

            except ImportError:
                raise Exception("vertexai 패키지 미설치. 실행: pip install google-cloud-aiplatform")
            except Exception as vertex_error:
                raise Exception(f"Vertex AI error: {vertex_error}")

        except Exception as e:
            print(f"  ✗ Imagen error: {e}")
            print(f"  💡 설정 방법:")
            print(f"     방법 1 (Gemini API - 권장):")
            print(f"       - GEMINI_API_KEY 환경변수 설정")
            print(f"       - pip install google-genai")
            print(f"     방법 2 (Vertex AI):")
            print(f"       - 프로젝트 루트에 key.json 파일 추가")
            print(f"       - pip install google-cloud-aiplatform")
            print(f"  💡 대안: IMAGE_ENGINE=dalle3 또는 dalle2로 변경")
            # ★ 예외 발생시켜 폴백 로직 작동하도록 함
            raise Exception(f"Imagen 생성 실패: {e}")

    def _generate_nano_banana_image(self, prompt: str, output_path: str, size: str = "1024x1024") -> str:
        """
        Gemini Nano Banana로 이미지 생성 및 저장

        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 저장 경로
            size: 이미지 크기 (1024x1024, 1024x1792 등)

        Returns:
            저장된 이미지 경로
        """
        try:
            # 프롬프트 길이 제한
            if len(prompt) > 4000:
                prompt = prompt[:4000]

            # Gemini API로 이미지 생성
            # Note: Gemini 이미지 생성 API는 generate_content를 사용
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.9,
                    "top_p": 0.95,
                }
            )

            # 생성된 이미지 데이터 추출
            # Gemini API 응답 형식에 따라 수정 필요
            if hasattr(response, 'image'):
                # 이미지를 파일로 저장
                with open(output_path, 'wb') as f:
                    f.write(response.image)
                print(f"  ✓ Nano Banana image saved: {output_path}")
            else:
                # 이미지가 없으면 플레이스홀더 사용
                print(f"  ⚠ No image in response, using placeholder")
                self._create_placeholder_image(output_path, "Nano Banana", prompt[:100])

            return output_path

        except Exception as e:
            print(f"  ✗ Nano Banana error: {e}")
            # 실패 시 플레이스홀더로 폴백
            self._create_placeholder_image(output_path, "Nano Banana Error", str(e))
            return output_path

    # =====================================================================
    # ★ Wrapper Methods for Model Router (with content_policy_violation fallback)
    # =====================================================================

    def _generate_with_dalle3(self, prompt: str, output_path: str, force_manhwa: bool = False, is_fallback: bool = False) -> bool:
        """
        DALL-E 3로 이미지 생성 (순화 + content_policy_violation 폴백 포함)

        Args:
            prompt: 이미지 프롬프트
            output_path: 출력 경로
            force_manhwa: 만화 스타일 강제 여부
            is_fallback: True면 Imagen 실패 후 폴백 (사람 없이 배경만 생성)

        Returns:
            성공 여부 (True/False)
        """
        try:
            # ★ 프롬프트 순화 (content_policy_violation 방지)
            sanitized_prompt = sanitize_for_dalle(prompt)

            if sanitized_prompt != prompt:
                print(f"  [DALL-E] 프롬프트 순화됨 (원본 {len(prompt)}자 → {len(sanitized_prompt)}자)")

            # ★ 야담/만화 스타일 감지 → 만화 스타일 강제 추가 (실사 이미지 방지)
            yadam_keywords = ['anime', 'joseon', 'traditional korean', 'korean historical',
                             'hanbok', 'gisaeng', 'yangban', 'nobleman', 'samurai style',
                             'manhwa', 'manga', 'illustration style', 'cel-shaded',
                             '야담', '조선', '한복', '선비', '양반', '기생', '만화']
            is_yadam_style = force_manhwa or any(kw.lower() in prompt.lower() for kw in yadam_keywords)

            if is_yadam_style:
                # 만화/애니 스타일 프리픽스 추가 (실사 방지) + NO TEXT 추가
                manhwa_prefix = "Korean traditional manhwa illustration style, 2D anime art, cel-shaded, vibrant colors, NOT photorealistic, NOT 3D render, NOT real photo, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO WRITING: "
                sanitized_prompt = manhwa_prefix + sanitized_prompt
                print(f"  [DALL-E] ★ 야담/만화 모드 감지 → 만화 스타일 강제 적용")

            # ★ Imagen 폴백인 경우: 애니메이션 스타일 배경만 생성 (다음 씬과 자연스럽게 연결)
            if is_fallback:
                # 만화 스타일이 아직 적용 안 됐으면 강제 적용
                if not is_yadam_style:
                    anime_prefix = "Korean traditional manhwa illustration style, 2D anime art, cel-shaded, vibrant colors, NOT photorealistic, NOT 3D render, NOT real photo, ABSOLUTELY NO TEXT, NO WORDS, NO LETTERS, NO WRITING: "
                    sanitized_prompt = anime_prefix + sanitized_prompt
                # 사람 없이 애니메이션 배경만
                background_suffix = " IMPORTANT: NO people, NO human figures, NO faces, NO characters. Show ONLY anime-style background scenery, illustrated landscape, painted environment, atmospheric anime scene. Empty scene without any person. NO TEXT anywhere in the image."
                sanitized_prompt = sanitized_prompt + background_suffix
                print(f"  [DALL-E] ★ 폴백 모드 → 애니메이션 스타일 배경만 생성")

            # DALL-E 3 생성 시도
            result = self._generate_dalle3_image(sanitized_prompt, output_path, size=self.dalle3_size)

            if result and os.path.exists(output_path):
                return True
            return False

        except Exception as e:
            error_str = str(e).lower()

            # content_policy_violation 감지 → 강력 순화 후 재시도
            if 'content_policy_violation' in error_str or 'content policy' in error_str or '400' in str(e):
                print(f"  [DALL-E] ⚠️ Content Policy Violation → 강력 순화 후 재시도")

                # ★ 강력 순화 후 재시도
                try:
                    aggressive_prompt = sanitize_for_dalle(prompt, aggressive=True)
                    # 만화 스타일 + 배경만 + NO TEXT
                    safe_prefix = "Korean manhwa illustration style, peaceful scene, NO TEXT, NO WORDS: "
                    safe_suffix = " Show only background scenery, no people, no characters, serene atmosphere."
                    safe_prompt = safe_prefix + aggressive_prompt + safe_suffix
                    print(f"  [DALL-E] 재시도: 강력 순화 프롬프트 ({len(safe_prompt)}자)")
                    result = self._generate_dalle3_image(safe_prompt, output_path, size=self.dalle3_size)
                    if result and os.path.exists(output_path):
                        print(f"  [DALL-E] ✓ 강력 순화 재시도 성공!")
                        return True
                except Exception as retry_error:
                    print(f"  [DALL-E] 강력 순화 재시도도 실패: {retry_error}")

                # ★ 마지막 시도: 매우 안전한 기본 프롬프트
                try:
                    fallback_prompt = "Korean traditional manhwa illustration, beautiful scenery background, mountains and sky, peaceful atmosphere, NO TEXT, NO WORDS, no people"
                    print(f"  [DALL-E] 최후 시도: 안전한 기본 프롬프트")
                    result = self._generate_dalle3_image(fallback_prompt, output_path, size=self.dalle3_size)
                    if result and os.path.exists(output_path):
                        print(f"  [DALL-E] ✓ 안전 프롬프트 성공!")
                        return True
                except Exception as final_error:
                    print(f"  [DALL-E] 안전 프롬프트도 실패: {final_error}")

            print(f"  [DALL-E] Error: {e}")
            return False

    def _generate_with_dalle2(self, prompt: str, output_path: str) -> bool:
        """
        DALL-E 2로 이미지 생성 (순화 포함)

        Args:
            prompt: 이미지 프롬프트
            output_path: 출력 경로

        Returns:
            성공 여부 (True/False)
        """
        try:
            # ★ 프롬프트 순화
            sanitized_prompt = sanitize_for_dalle(prompt)

            result = self._generate_dalle2_image(sanitized_prompt, output_path)

            if result and os.path.exists(output_path):
                return True
            return False

        except Exception as e:
            error_str = str(e).lower()

            # content_policy_violation → Gemini 폴백
            if 'content_policy_violation' in error_str or 'content policy' in error_str:
                print(f"  [DALL-E 2] ⚠️ Content Policy Violation → Gemini 폴백 시도")

                if self.gemini_api_key:
                    try:
                        return self._generate_with_gemini(prompt, output_path)
                    except Exception as gemini_error:
                        print(f"  [Gemini] 폴백도 실패: {gemini_error}")

            print(f"  [DALL-E 2] Error: {e}")
            return False

    def _generate_with_gemini(self, prompt: str, output_path: str) -> bool:
        """
        Gemini (Imagen)로 이미지 생성

        Args:
            prompt: 이미지 프롬프트
            output_path: 출력 경로

        Returns:
            성공 여부 (True/False)
        """
        try:
            # Imagen 이미지 생성
            result = self._generate_imagen_image(prompt, output_path, aspect_ratio=self.aspect_ratio)

            if result and os.path.exists(output_path):
                return True
            return False

        except Exception as e:
            print(f"  [Gemini] Error: {e}")

            # Gemini 실패 시 DALL-E 폴백 (역방향)
            # ★ is_fallback=True로 사람 없이 배경만 생성 (다음 씬과 자연스럽게 연결)
            if self.openai_client:
                print(f"  [Gemini] → DALL-E 3 폴백 시도 (배경 전용)")
                try:
                    return self._generate_with_dalle3(prompt, output_path, is_fallback=True)
                except Exception as dalle_error:
                    print(f"  [DALL-E] 폴백도 실패: {dalle_error}")

            return False
