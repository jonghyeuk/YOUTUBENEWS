from typing import Dict, Any
from models.types import ContentProfile


class ContentProfileEngine:
    """
    콘텐츠 프로필 엔진 - 뉴스/사건사고 전용

    ★ 사건사고 뉴스 (accident_news) ★
    - 실제 뉴스 기사 기반 재구성
    - 객관적이고 중립적인 나레이션
    - 뉴스 앵커 스타일의 전달

    ★ 카더라 뉴스 (rumor_news) ★
    - 소문/풍문 기반 각색
    - 자극적이지만 사실에 기반
    - 흥미 유발 요소 강화
    """

    def __init__(self):
        self.modes: Dict[str, Dict[str, Any]] = {
            # 사건사고 뉴스 - 객관적 보도 스타일
            "accident_news": {
                "language": "ko-KR",
                "voice_tone": "neutral_anchor",       # 뉴스 앵커 스타일
                "speech_speed": 1.0,                  # 표준 속도
                "text_density": "medium",             # 적절한 정보 밀도
                "cut_change_speed": "medium",         # 중간 장면 전환
                "max_points": 8,                      # 뉴스 구조
                "max_tokens": 8000,
                "tts_engine": "google",               # Google TTS만 사용
                "tts_voice": "ko-KR-Wavenet-A",       # 여성 아나운서 톤
                "genre_style": "news_report",
                "core_emotion": ["객관성", "긴장감", "정보 전달", "신뢰성"],
                "structure": "헤드라인 → 개요 → 상세내용 → 배경설명 → 전문가의견 → 전망 → 마무리",
                "narration_style": "journalistic",    # 보도체

                # ★ 뉴스 스타일 특징
                "news_style": {
                    "language_style": "보도체 (~했습니다, ~한 것으로 전해졌습니다)",
                    "tone": "객관적, 중립적, 신뢰성 있는",
                    "transition_patterns": [
                        "이어서 전해드립니다.",
                        "관계자에 따르면,",
                        "한편,",
                        "이에 대해 전문가들은,",
                        "현재까지 확인된 바에 따르면,"
                    ],
                    "ending_style": "마무리형 (지금까지 ~였습니다)",
                },

                # ★ 이미지 스타일 (뉴스 보도 스타일)
                "image_style": {
                    "realistic": {
                        "art_style": "photorealistic news photography style, professional journalism",
                        "composition": "뉴스 보도 사진 스타일, 현장감 있는 구도",
                        "color_palette": "차분한 톤, 사실적인 색감",
                    },
                    "anime": {
                        "art_style": "Korean webtoon news illustration style, clean line art, professional",
                        "composition": "뉴스 일러스트 스타일, 명확한 정보 전달",
                        "color_palette": "선명하고 깔끔한 색상",
                    }
                },
            },

            # 카더라 뉴스 - 흥미 위주 각색 스타일
            "rumor_news": {
                "language": "ko-KR",
                "voice_tone": "dramatic_storyteller",  # 드라마틱한 전달
                "speech_speed": 0.95,                  # 약간 느리게
                "text_density": "high",                # 풍부한 묘사
                "cut_change_speed": "medium",          # 중간 장면 전환
                "max_points": 10,                      # 더 많은 전개
                "max_tokens": 10000,
                "tts_engine": "google",                # Google TTS만 사용
                "tts_voice": "ko-KR-Wavenet-A",        # 여성 아나운서 톤
                "genre_style": "tabloid_story",
                "core_emotion": ["호기심", "긴장감", "놀라움", "흥미"],
                "structure": "후킹 → 소문소개 → 배경설명 → 진실파헤치기 → 충격적사실 → 반전 → 결론",
                "narration_style": "storytelling",     # 이야기체

                # ★ 카더라 스타일 특징
                "news_style": {
                    "language_style": "이야기체 (~했다고 합니다, ~라는 소문이 있었습니다)",
                    "tone": "흥미롭고 자극적이지만 품위 유지",
                    "transition_patterns": [
                        "그런데 여기서 충격적인 사실이 밝혀졌습니다.",
                        "소문에 따르면,",
                        "믿기 어렵겠지만,",
                        "이 이야기의 반전은,",
                        "진실은 이랬습니다."
                    ],
                    "ending_style": "여운형 (과연 진실은 무엇이었을까요?)",
                },

                # ★ 이미지 스타일 (드라마틱 스타일)
                "image_style": {
                    "realistic": {
                        "art_style": "dramatic photorealistic style, cinematic lighting, mysterious atmosphere",
                        "composition": "영화적 구도, 극적인 조명, 미스터리한 분위기",
                        "color_palette": "대비가 강한 색감, 어두운 톤",
                    },
                    "anime": {
                        "art_style": "Korean webtoon thriller illustration, dramatic shadows, expressive style",
                        "composition": "웹툰 스릴러 스타일, 극적인 그림자, 표현적",
                        "color_palette": "강렬한 색상 대비",
                    }
                },
            },
        }

    def build_news_profile(
        self,
        news_mode: str = "accident_news",
        duration_minutes: float = 5
    ) -> ContentProfile:
        """
        뉴스 프로필 생성

        Args:
            news_mode: 뉴스 모드 (accident_news / rumor_news)
            duration_minutes: 영상 길이 (분)

        Returns:
            ContentProfile 객체
        """
        mode = self.modes.get(news_mode, self.modes["accident_news"])
        duration_sec = int(duration_minutes * 60)

        # 템플릿 ID 결정
        if news_mode == "accident_news":
            template_id = "news_report_short" if duration_sec <= 180 else "news_report"
            category = "accident_news"
        else:
            template_id = "rumor_story_short" if duration_sec <= 180 else "rumor_story"
            category = "rumor_news"

        # extra 필드 구성
        extra = {
            "text_density": mode["text_density"],
            "cut_change_speed": mode["cut_change_speed"],
            "max_points": mode["max_points"],
            "is_shorts": duration_sec <= 60,
            "genre_style": mode["genre_style"],
            "max_tokens": self._get_max_tokens(duration_sec),
            "news_style": mode.get("news_style", {}),
            "image_style_options": mode.get("image_style", {}),
            "core_emotion": mode.get("core_emotion", []),
            "structure": mode.get("structure", ""),
            "narration_style": mode.get("narration_style", "journalistic"),
        }

        # TTS 설정
        extra["tts_config"] = {
            "engine": "google",  # Google TTS만 사용
            "voice": mode.get("tts_voice", "ko-KR-Wavenet-A"),
            "speed": mode.get("speech_speed", 1.0),
        }

        return ContentProfile(
            mode_id=news_mode,
            category=category,
            template_id=template_id,
            duration_sec=duration_sec,
            language=mode["language"],
            voice_tone=mode["voice_tone"],
            speech_speed=mode["speech_speed"],
            extra=extra
        )

    def _get_max_tokens(self, duration_sec: int) -> int:
        """영상 길이에 따른 max_tokens 결정"""
        if duration_sec >= 900:  # 15분 이상
            return 12000
        elif duration_sec >= 600:  # 10분 이상
            return 8000
        elif duration_sec >= 300:  # 5분 이상
            return 5000
        elif duration_sec >= 180:  # 3분 이상
            return 3000
        else:
            return 2000

    def get_image_style_config(self, news_mode: str, image_style: str) -> Dict[str, Any]:
        """
        이미지 스타일 설정 반환

        Args:
            news_mode: 뉴스 모드 (accident_news / rumor_news)
            image_style: 이미지 스타일 (anime / realistic)

        Returns:
            이미지 스타일 설정 딕셔너리
        """
        mode = self.modes.get(news_mode, self.modes["accident_news"])
        image_styles = mode.get("image_style", {})

        if image_style == "anime":
            return image_styles.get("anime", {
                "art_style": "Korean webtoon illustration style",
                "composition": "웹툰 스타일",
                "color_palette": "선명한 색상"
            })
        else:  # realistic
            return image_styles.get("realistic", {
                "art_style": "photorealistic style",
                "composition": "사실적인 구도",
                "color_palette": "자연스러운 색감"
            })

    def build_profile(self, keyword: str, mode_id: str = "accident_news",
                     duration_minutes: float = None) -> ContentProfile:
        """
        기존 호환성을 위한 build_profile 메서드
        (내부적으로 build_news_profile 호출)
        """
        return self.build_news_profile(
            news_mode=mode_id,
            duration_minutes=duration_minutes or 5
        )
