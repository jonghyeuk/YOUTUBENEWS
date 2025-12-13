from typing import Dict, Any
from models.types import ContentProfile
from engines.topic_engine import TOPIC_RULES


class ContentProfileEngine:
    """
    콘텐츠 프로필 엔진 - 야담 전용

    ★ 야담형 (yadam_kr_v1) ★
    - 조선시대/역사적 배경의 전통 이야기
    - 문어체 나레이션 + 만화/일러스트 이미지
    - 긴 서사 (10~50분)
    - 참조 채널: 설희야담 스타일

    ★ 콘텐츠 철학 ★
    - 삶의 깊이와 교훈, 감정적 몰입이 핵심
    - 서사 중심 구성, 감정선을 따라가는 연출
    - 권선징악, 반전, 여운 있는 마무리
    """

    def __init__(self):
        # 야담 모드만 정의
        self.modes: Dict[str, Dict[str, Any]] = {
            # 야담형 (Traditional Korean Storytelling) - 설희야담 스타일
            # 목표: 조선시대/역사적 배경의 전통 이야기를 문학적으로 풀어냄
            # 형식: 긴 서사 (10~50분), 문어체 나레이션 + 만화/일러스트 이미지
            # 참조 채널: 설희야담 (구독자 3.4만, 영상당 50분 내외)
            "yadam_kr_v1": {
                "language": "ko-KR",
                "voice_tone": "literary_calm",        # 문학적이고 차분한 톤
                "speech_speed": 0.95,                 # 살짝 느리게 (기본)
                "text_density": "high",               # 풍부한 묘사
                "cut_change_speed": "slow",           # 느린 장면 전환 (몰입 유지)
                "max_points": 11,                     # 긴 서사 구조
                "max_tokens": 16000,                  # ★ 30분+ 영상용 긴 나레이션 생성
                "tts_engine": "google",               # Google TTS (차분한 한국어)
                "dialogue_voice": "ko-KR-Wavenet-C",  # 남성 차분한 목소리
                "genre_style": "yadam_story",
                "core_emotion": ["긴장감", "몰입", "권선징악", "여운", "카타르시스"],
                "structure": "오프닝 → 후킹 → 인물소개 → 갈등고조 → 정체암시 → 정체공개 → 위기 → 클라이맥스 → 해결 → 여운",
                "narration_style": "literary",        # 문어체 (존댓말, 비유 풍부)

                # ★ 야담 스타일 특징
                "yadam_style": {
                    "language_style": "문어체 존댓말 (~했습니다, ~이었지요)",
                    "literary_devices": ["비유", "의성어/의태어", "전환점 표현"],
                    "transition_patterns": [
                        "바로 그때였습니다.",
                        "그 순간이었습니다.",
                        "하지만 그들은 몰랐습니다.",
                        "정확히 말하면~"
                    ],
                    "ending_style": "여운형 (~뿐이었습니다, 직접적 교훈 금지)",
                },

                # ★ 이미지 연출 가이드 (야담/만화 스타일)
                "image_style": {
                    "art_style": "Korean traditional manhwa/webtoon illustration, hand-drawn comic art style with ink brush aesthetic",
                    "composition": "극적인 명암 대비, 실루엣, 뒷모습, 클로즈업",
                    "background": "한국 전통 배경 (조선시대 장터, 기와집, 산속 오두막)",
                    "color_palette": {
                        "기본": "따뜻한 황토색, 세피아 톤",
                        "긴장": "어두운 먹색, 강한 명암 대비",
                        "평화": "부드러운 수묵화 톤"
                    },
                    "style_keywords": ["manhwa", "webtoon", "comic", "illustration", "ink brush", "korean traditional"],
                },

                # ★ 캐릭터 유형
                "character_types": {
                    "protagonist": "평범해 보이지만 전설적 과거를 가진 인물 (은퇴한 무사, 늙은 목수 등)",
                    "antagonist": "마을/장터를 괴롭히는 악당 (왈패 두목, 탐관오리 등)",
                    "protected": "주인공이 지키는 소중한 존재 (손녀, 제자, 마을 사람들)",
                },

                # ★ 후킹 예시
                "hook_examples": [
                    "장터의 질서를 비웃기라도 하듯 거대한 몸뚱이를 버티고 선 사내가 있었습니다.",
                    "그날, 마을에 낯선 노인이 나타났습니다.",
                    "아무도 그의 과거를 알지 못했습니다. 단 한 사람만 빼고.",
                ],
            }
        }
        self.topic_rules = TOPIC_RULES

    def _detect_topic_rule(self, keyword: str) -> Dict[str, Any]:
        kw = keyword.strip()
        for rule in self.topic_rules:
            if any(k in kw for k in rule["keywords"]):
                return rule
        return {
            "category": "general",
            "recommended_duration": 300,
            "template_id": "senior_story"
        }

    def build_profile(self, keyword: str, mode_id: str = "yadam_kr_v1",
                     duration_minutes: float = None) -> ContentProfile:
        """
        프로필 생성

        Args:
            keyword: 주제어
            mode_id: 모드 ID (기본: yadam_kr_v1)
            duration_minutes: 영상 길이 (분)
        """
        mode = self.modes.get(mode_id, self.modes["yadam_kr_v1"])
        topic_rule = self._detect_topic_rule(keyword)

        # 사용자가 길이를 선택했으면 그것을 사용
        if duration_minutes:
            duration_sec = int(duration_minutes * 60)
        else:
            duration_sec = topic_rule["recommended_duration"]

        # 모드별 템플릿 선택
        genre_style = mode.get("genre_style", "senior_story")

        if mode_id == "emotional_kr_v1":
            # 감동 실화형
            template_id = "emotional_story_short" if duration_sec <= 180 else "emotional_story"
            topic_rule["category"] = "emotional"

        elif mode_id == "nostalgic_kr_v1":
            # 회상·향수형
            template_id = "nostalgic_story_short" if duration_sec <= 180 else "nostalgic_story"
            topic_rule["category"] = "nostalgic"

        elif mode_id == "wisdom_kr_v1":
            # 교훈·명언형
            template_id = "wisdom_story_short" if duration_sec <= 180 else "wisdom_story"
            topic_rule["category"] = "wisdom"

        elif mode_id == "knowledge_kr_v1":
            # 지식·정보형
            template_id = "knowledge_info_short" if duration_sec <= 180 else "knowledge_info"
            topic_rule["category"] = "knowledge"

        elif mode_id == "classic_kr_v1":
            # 명작·음악 해설형
            template_id = "classic_review_short" if duration_sec <= 180 else "classic_review"
            topic_rule["category"] = "classic"

        elif mode_id == "kids_kr_v1":
            # 유아 모드
            template_id = "kids_story_short" if duration_sec <= 180 else "kids_story"
            topic_rule["category"] = "kids"

        elif mode_id == "drama_kr_v1":
            # 드라마형 서사
            template_id = "drama_story_short" if duration_sec <= 180 else "drama_story"
            topic_rule["category"] = "drama"

        elif mode_id == "yadam_kr_v1":
            # 야담형 (전통 이야기) - 5분 초과면 긴 버전 사용
            template_id = "yadam_story_short" if duration_sec <= 300 else "yadam_story"
            topic_rule["category"] = "yadam"
        else:
            # 기본값
            template_id = "emotional_story"

        # extra 필드 구성
        extra = {
            "text_density": mode["text_density"],
            "cut_change_speed": mode["cut_change_speed"],
            "max_points": mode["max_points"],
            "is_shorts": duration_sec <= 60,
            "genre_style": genre_style,
        }

        # ★★★ 통합 설정: 모든 엔진이 profile.extra에서 읽음 ★★★

        # 1. 이미지 스타일 설정 (image_engine에서 사용)
        extra["image_style"] = self._get_image_style_for_mode(mode_id, mode)

        # 2. 스크립트 설정 (script_engine에서 사용)
        extra["max_tokens"] = self._get_max_tokens_for_mode(mode_id, duration_sec)

        # 3. TTS 설정 (tts_engine에서 사용)
        extra["tts_config"] = {
            "engine": mode.get("tts_engine", "openai"),
            "voice": mode.get("dialogue_voice", "alloy"),
            "speed": mode.get("speech_speed", 1.0),
        }

        # 장르별 추가 설정
        if mode.get("core_emotion"):
            extra["core_emotion"] = mode["core_emotion"]
        if mode.get("structure"):
            extra["structure"] = mode["structure"]
        if mode.get("dialogue_voice"):
            extra["dialogue_voice"] = mode["dialogue_voice"]
            extra["tts_engine"] = mode.get("tts_engine", "openai")

        # 유아 모드 특수 설정
        if mode.get("narrator_style") == "storyteller":
            extra["narrator_style"] = "storyteller"
            extra["target_age"] = mode.get("target_age", "4-7")
            extra["character_consistency"] = mode.get("character_consistency", True)

        # 드라마 모드 특수 설정
        if mode.get("narration_style"):
            extra["narration_style"] = mode["narration_style"]
        if mode.get("drama_themes"):
            extra["drama_themes"] = mode["drama_themes"]

        # 야담 모드 특수 설정
        if mode.get("yadam_style"):
            extra["yadam_style"] = mode["yadam_style"]
        if mode.get("character_types"):
            extra["character_types"] = mode["character_types"]

        return ContentProfile(
            mode_id=mode_id,
            category=topic_rule.get("category", "general"),
            template_id=template_id,
            duration_sec=duration_sec,
            language=mode["language"],
            voice_tone=mode["voice_tone"],
            speech_speed=mode["speech_speed"],
            extra=extra
        )

    def _get_image_style_for_mode(self, mode_id: str, mode: dict) -> dict:
        """
        모드별 이미지 스타일 설정 반환
        ★ image_engine에서 SENIOR_IMAGE_STYLES 대신 이 설정을 사용
        """
        # 모드에 image_style이 정의되어 있으면 그것을 기반으로
        if mode.get("image_style"):
            base_style = mode["image_style"]
            # image_engine이 필요로 하는 형태로 변환
            return {
                "base_prompt": base_style.get("background", ""),
                "style": base_style.get("art_style", "realistic photo"),
                "mood": base_style.get("composition", "natural mood"),
                "avoid": "text, watermarks, low quality",
                "composition": base_style.get("composition", ""),
                "color_palette": base_style.get("color_palette", {}),
                "art_direction": base_style.get("art_style", ""),
                "style_keywords": base_style.get("style_keywords", []),
            }

        # 모드별 기본 이미지 스타일 정의
        default_styles = {
            "emotional_kr_v1": {
                "base_prompt": "따뜻한 가족, 감동적인 장면",
                "style": "따뜻하고 서정적인 색감, 부드러운 조명",
                "mood": "감동적이고 따뜻한",
                "avoid": "너무 슬프거나 우울한 분위기",
            },
            "nostalgic_kr_v1": {
                "base_prompt": "옛날 한국의 풍경과 사람들",
                "style": "빈티지 사진 느낌, 세피아 톤",
                "mood": "향수 어린, 추억을 소환하는",
                "avoid": "너무 현대적인 요소",
            },
            "wisdom_kr_v1": {
                "base_prompt": "사려 깊은 인물, 명상적 분위기",
                "style": "차분하고 깊이 있는 색감",
                "mood": "통찰력 있는, 성찰적인",
                "avoid": "산만한 배경",
            },
            "knowledge_kr_v1": {
                "base_prompt": "편안하고 이해하기 쉬운 장면",
                "style": "밝고 명확한 색감, 높은 명도 대비",
                "mood": "친근하고 편안한",
                "avoid": "복잡하거나 산만한 구도",
            },
            "classic_kr_v1": {
                "base_prompt": "역사적 장면, 고전적 분위기",
                "style": "드라마틱하고 영화적인 분위기",
                "mood": "웅장하고 극적인",
                "avoid": "현대적 요소, 애니메이션 스타일",
            },
            "drama_kr_v1": {
                "base_prompt": "시니어 드라마 스틸컷 느낌, 한국 일상 배경",
                "style": "한국 멜로/가족 드라마 색감, 시네마틱 조명",
                "mood": "드라마틱하고 감정적인, 몰입감 있는",
                "avoid": "과도하게 선정적이거나 폭력적인 장면, 만화 스타일",
                "composition": "정면보다 측면/뒷모습, 부분 초점",
                "color_flow": {
                    "평온": "따뜻한 밝은 톤",
                    "갈등": "어두운 톤, 회색",
                    "해결": "따뜻함 회복",
                },
            },
            "kids_kr_v1": {
                "base_prompt": "귀여운 동물 캐릭터, 어린이 동화 일러스트 스타일",
                "style": "밝고 화사한 파스텔 색감, 동화책 그림체, 3D 애니메이션",
                "mood": "밝고 즐거운, 따뜻하고 포근한",
                "avoid": "무서운 장면, 어두운 색감, 현실적인 사람",
            },
            "yadam_kr_v1": {
                "base_prompt": "한국 전통 야담 일러스트, 만화/웹툰 스타일, 조선시대 배경",
                "style": "Korean manhwa illustration style, webtoon art, dramatic ink brush strokes, NOT photorealistic",
                "mood": "극적이고 긴장감 있는, 권선징악",
                "avoid": "photorealistic style, 3D rendering, modern settings, anime style",
                "composition": "극적인 명암 대비, 실루엣 활용, 뒷모습/측면 구도",
                "color_palette": {
                    "기본": "따뜻한 황토색, 세피아 톤",
                    "긴장": "어두운 먹색, 강한 명암 대비",
                    "평화": "부드러운 수묵화 톤",
                },
                "art_direction": "Korean traditional manhwa/webtoon illustration, hand-drawn comic art style",
                "style_keywords": ["만화", "일러스트", "웹툰", "동양화", "극적", "한국전통"],
            },
        }

        return default_styles.get(mode_id, {
            "base_prompt": "편안하고 이해하기 쉬운 장면",
            "style": "밝고 명확한 색감",
            "mood": "친근하고 편안한",
            "avoid": "복잡하거나 산만한 구도",
        })

    def _get_max_tokens_for_mode(self, mode_id: str, duration_sec: int) -> int:
        """
        모드별 max_tokens 설정 반환
        ★ script_engine에서 이 설정을 사용
        """
        # ★ self.modes에 명시된 값이 있으면 그것을 우선 사용
        mode = self.modes.get(mode_id, {})
        if "max_tokens" in mode:
            return mode["max_tokens"]

        # 기본값 (MODE_PROFILES에 없는 경우)
        base_tokens = 4000

        # 긴 서사가 필요한 모드
        long_narrative_modes = ["yadam_kr_v1", "drama_kr_v1", "classic_kr_v1"]

        if mode_id in long_narrative_modes:
            base_tokens = 12000  # 긴 서사 모드는 12000

        # 영상 길이에 따른 추가 조정
        if duration_sec >= 1800:  # 30분 이상
            base_tokens = max(base_tokens, 16000)
        elif duration_sec >= 900:  # 15분 이상
            base_tokens = max(base_tokens, 10000)

        return base_tokens

    def detect_mode_from_keyword(self, keyword: str) -> tuple:
        """
        키워드 분석으로 최적의 콘텐츠 모드를 자동 판별

        Args:
            keyword: 사용자 입력 주제어

        Returns:
            (mode_id, reason): 추천 모드 ID와 판별 이유
        """
        kw = keyword.lower().strip()

        # ★ 키워드 기반 장르 판별 규칙
        mode_rules = {
            # 드라마형 서사 (갈등, 막장, 인간관계)
            "drama_kr_v1": {
                "keywords": [
                    "불륜", "외도", "바람", "이혼", "황혼이혼", "재혼", "시어머니", "며느리",
                    "유산", "상속", "유언장", "가족싸움", "형제갈등", "부부싸움", "부부갈등",
                    "배신", "사기", "뒤통수", "복수", "층간소음", "이웃갈등", "아파트",
                    "직장상사", "괴롭힘", "왕따", "은퇴", "퇴직", "해고", "실화", "막장",
                    "남편", "아내", "시집", "친정", "고부갈등", "시댁", "돈문제", "빚",
                    "사건", "사고", "범죄", "살인", "폭행", "협박", "스토킹",
                    # ★ 로맨스/연애 키워드 추가
                    "연애", "비밀연애", "사랑", "첫사랑", "재회", "로맨스", "삼각관계",
                    "아이돌", "연예인", "스타", "매니저", "소속사", "데뷔", "팬",
                    "비밀", "스캔들", "열애", "결혼", "약혼", "청혼",
                ],
                "reason": "🎭 드라마형 서사 (갈등/인간관계/로맨스 키워드 감지)"
            },

            # 역사/인물 (고전, 역사 인물)
            "classic_kr_v1": {
                "keywords": [
                    "세종대왕", "이순신", "정조", "영조", "태종", "연산군", "광해군",
                    "을지문덕", "강감찬", "신사임당", "허준", "장영실", "정약용",
                    "조선", "고려", "삼국시대", "백제", "신라", "고구려", "임진왜란",
                    "동학", "독립운동", "일제강점기", "한국전쟁", "6.25",
                    "왕", "장군", "역사", "고전", "문학", "시", "소설", "명작",
                    "클래식", "베토벤", "모차르트", "바흐", "쇼팽",
                ],
                "reason": "🎵 명작·음악형 (역사/고전/문학 키워드 감지)"
            },

            # 감동 실화형 (따뜻한 이야기, 헌신, 감사)
            "emotional_kr_v1": {
                "keywords": [
                    "감동", "눈물", "헌신", "사랑", "효도", "부모님", "어머니", "아버지",
                    "은혜", "감사", "희생", "봉사", "기부", "나눔", "치료", "극복",
                    "장애", "병", "암", "투병", "완치", "기적", "구조", "영웅",
                    "입양", "고아원", "할머니", "할아버지", "노부부", "행복",
                ],
                "reason": "💝 감동 실화형 (감동/헌신 키워드 감지)"
            },

            # 회상/향수형 (추억, 옛날)
            "nostalgic_kr_v1": {
                "keywords": [
                    "추억", "옛날", "그시절", "80년대", "90년대", "70년대", "60년대",
                    "어린시절", "고향", "시골", "전교생", "국민학교", "다방", "LP",
                    "카세트", "워크맨", "삐삐", "공중전화", "연탄", "새마을", "이발소",
                    "비디오방", "오락실", "만화방", "문방구", "뽑기", "달고나",
                ],
                "reason": "📻 회상·향수형 (추억/과거 키워드 감지)"
            },

            # 교훈/명언형 (철학, 지혜)
            "wisdom_kr_v1": {
                "keywords": [
                    "명언", "교훈", "지혜", "철학", "인생", "성공", "실패", "명상",
                    "공자", "맹자", "노자", "석가모니", "부처", "예수", "성경",
                    "좌우명", "격언", "속담", "조언", "멘토", "깨달음", "성찰",
                ],
                "reason": "📖 교훈·명언형 (철학/명언 키워드 감지)"
            },

            # 지식/정보형 (실용 정보, 건강)
            "knowledge_kr_v1": {
                "keywords": [
                    "방법", "하는법", "꿀팁", "노하우", "정보", "가이드", "설명",
                    "건강", "고혈압", "당뇨", "관절", "무릎", "허리", "어깨", "운동",
                    "다이어트", "식단", "영양", "비타민", "약", "병원", "검진",
                    "재테크", "저축", "투자", "연금", "보험", "절세", "부동산",
                    "스마트폰", "컴퓨터", "앱", "인터넷", "사용법", "활용",
                ],
                "reason": "💡 지식·정보형 (실용/건강 키워드 감지)"
            },

            # 야담형 (전통 이야기, 무협, 권선징악)
            "yadam_kr_v1": {
                "keywords": [
                    "야담", "전래동화", "옛이야기", "전설", "민담", "설화",
                    "무사", "검객", "호랑이", "도적", "왈패", "의적", "협객",
                    "권선징악", "원수", "복수", "은원", "기연", "무공",
                    "도인", "스승", "제자", "비기", "절기", "무예",
                    "장터", "주막", "객주", "포도청", "암행어사",
                    "기생", "선비", "양반", "상놈", "노비", "천민",
                    "구미호", "귀신", "도깨비", "산신령", "용왕",
                ],
                "reason": "📜 야담형 (전통 이야기/무협/권선징악 키워드 감지)"
            },

            # 유아 동화 (★ "아이"는 "아이돌"과 혼동되므로 더 구체적으로)
            "kids_kr_v1": {
                "keywords": [
                    "동화", "어린이동화", "유아동화", "아기동화", "유아", "애기",
                    "4세", "5세", "6세", "7세", "어린이날",
                    "토끼", "곰돌이", "사자왕", "아기호랑이", "강아지친구", "고양이",
                    "공주님", "왕자님", "요정", "마법사", "숲속친구", "동물친구",
                ],
                "reason": "🧒 유아 동화 (어린이/동화 키워드 감지)"
            },
        }

        # 키워드 매칭으로 모드 판별
        for mode_id, rule in mode_rules.items():
            for kw_pattern in rule["keywords"]:
                if kw_pattern in kw:
                    return (mode_id, rule["reason"])

        # 기본값: 야담형
        return ("yadam_kr_v1", "📜 야담형 (기본값)")
