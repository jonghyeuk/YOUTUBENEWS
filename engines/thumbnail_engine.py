"""
썸네일 생성 엔진 - PIL 기반
한글 텍스트 오버레이 + 그림자/외곽선 효과
"""
import os
import re
import json
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import List, Tuple, Optional
from anthropic import Anthropic

from config import (
    YOUTUBE_THUMBNAIL_TEXT_TEMPLATES,
    YOUTUBE_THUMBNAIL_HOOK_SNIPPETS,
    YOUTUBE_THUMBNAIL_FORBIDDEN_WORDS,
    YOUTUBE_THUMBNAIL_RULES,
)

# ═══════════════════════════════════════════════════════════════
# LLM 프롬프트: 후킹 썸네일 메시지 생성
# ═══════════════════════════════════════════════════════════════
THUMBNAIL_HOOK_PROMPT = """당신은 유튜브 썸네일 카피라이터입니다.
주어진 유튜브 콘텐츠를 분석하여 **클릭을 유발하는 썸네일 문구**를 생성합니다.

## 출력 형식 (JSON)
```json
{
  "sub_text": "상단 메시지 (5-8자)",
  "main_text": "메인 메시지 (4-7자)"
}
```

## 핵심 규칙
1. **상단(sub_text) + 메인(main_text)이 연결되어 하나의 메시지**가 되어야 함
   - 예: "이 승려의 정체" + "충격적 비밀"
   - 예: "1500년 전" + "왕자의 선택"
   - 예: "마음이 힘들 때" + "이 한마디"

2. **궁금증 유발 필수**
   - 핵심 정보는 숨기고 힌트만 제공
   - "뭐지?" "왜?" 궁금하게 만들기
   - 결론을 말하지 말 것

3. **글자 수 제한 (필수)**
   - sub_text: 5~8자
   - main_text: 4~7자
   - 합쳐서 최대 15자 이내

4. **후킹 패턴** (하나 선택)
   - 미스터리형: "아무도 몰랐던" + "숨겨진 진실"
   - 경고형: "이것만은" + "하지 마세요"
   - 질문형: "왜 마음이" + "불안한가"
   - 역사형: "1500년 전" + "그날의 선택"
   - 공감형: "잠 못 드는 밤" + "들어야 할 말"

5. **금지사항**
   - 구두점 사용 금지 (!, ?, . 등)
   - 숫자는 최소화
   - 과장 금지 (충격, 경악, 대박 등 남발 금지)
"""

# ═══════════════════════════════════════════════════════════════
# 후킹 썸네일 메시지 템플릿 (상단 + 메인 연결형)
# 패턴: 상단(호기심 유발) → 메인(핵심 메시지)
# ═══════════════════════════════════════════════════════════════
THUMBNAIL_HOOK_TEMPLATES = {
    "불교종교": [
        # 역사/인물 미스터리형
        {"sub": "이 승려의 정체", "main": "충격적 비밀"},
        {"sub": "1500년 전", "main": "왕자의 선택"},
        {"sub": "황제가 숨긴", "main": "진짜 이유"},
        {"sub": "아무도 몰랐던", "main": "숨겨진 역사"},
        {"sub": "경전이 말하지 않은", "main": "그날의 진실"},
        # 감정/공감형
        {"sub": "마음이 힘들 때", "main": "이 한마디"},
        {"sub": "잠 못 드는 밤", "main": "들어야 할 말"},
        {"sub": "불안이 심할 때", "main": "부처님 답"},
        {"sub": "생각이 많은 밤", "main": "마음 정리법"},
        {"sub": "화가 치밀 때", "main": "하지 말 것"},
        # 경고/조언형
        {"sub": "이것만은", "main": "하지 마세요"},
        {"sub": "50대 이후", "main": "꼭 알아야 할"},
        {"sub": "인연 정리가", "main": "필요한 순간"},
        {"sub": "놓아야", "main": "편해지는 것"},
        # 질문/호기심형
        {"sub": "왜 마음이", "main": "불안한가"},
        {"sub": "부처님은 왜", "main": "이렇게 말했나"},
        {"sub": "깨달음의", "main": "진짜 의미"},
    ],
    "믿거나말거나": [
        {"sub": "충격 실화", "main": "믿기 어려운"},
        {"sub": "소름 주의", "main": "실제 일어난 일"},
        {"sub": "끝까지 보세요", "main": "반전 있음"},
        {"sub": "아무도 모르는", "main": "숨겨진 진실"},
    ],
    "정보": [
        {"sub": "모르면 손해", "main": "꼭 알아야 할"},
        {"sub": "이것만 알면", "main": "인생이 편해짐"},
        {"sub": "알면 유리한", "main": "핵심 정보"},
    ],
}


class ThumbnailEngine:
    """YouTube 썸네일 생성 엔진"""

    # 기본 설정
    THUMBNAIL_SIZE = (1280, 720)  # YouTube 권장 크기

    # 언어별 썸네일 전용 폰트 (절대 경로로 변환)
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    KOREAN_THUMBNAIL_FONT = os.path.join(_BASE_DIR, "fonts/GapyeongHanseokbongB.ttf")      # 한국어: 가평한석봉체
    ENGLISH_THUMBNAIL_FONT = os.path.join(_BASE_DIR, "fonts/PlayfairDisplay-Italic.ttf")  # 영어: Playfair Display Italic
    JAPANESE_THUMBNAIL_FONT = os.path.join(_BASE_DIR, "fonts/YujiSyuku-Regular.ttf")      # 일본어: 佑字肅 (서예체)

    # 스타일별 색상 프리셋 (모든 스타일에 두꺼운 외곽선 적용)
    COLOR_PRESETS = {
        # === 불교 스타일 ===
        "불교강의": {
            "primary": "#FFFFFF",    # 흰색 메인
            "secondary": "#FFD700",  # 금색 서브
            "outline": "#000000",    # 검정 외곽선
            "shadow": "#000000",
        },
        "불교명상": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#FFD700",  # 금색
            "outline": "#000000",
            "shadow": "#000000",
        },
        "불교종교": {
            "primary": "#FFD700",    # 금색
            "secondary": "#FFFFFF",  # 흰색
            "outline": "#000000",
            "shadow": "#000000",
        },
        # === 스토리텔링 (지역별) ===
        "스토리텔링:한국불교": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#C9A96E",  # 전통 황토색
            "outline": "#1A1A1A",    # 진한 먹색
            "shadow": "#000000",
        },
        "스토리텔링:중국불교": {
            "primary": "#FFD700",    # 금색
            "secondary": "#FF4444",  # 붉은색
            "outline": "#000000",
            "shadow": "#000000",
        },
        "스토리텔링:인도불교": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#FF9933",  # 사프란 오렌지
            "outline": "#4A2C2A",    # 갈색
            "shadow": "#000000",
        },
        # === 언어별 전용 ===
        "일본텔링": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#E8B4B8",  # 벚꽃 핑크
            "outline": "#2D2D2D",    # 진한 회색
            "shadow": "#000000",
        },
        "영어Saying전용": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#FFD700",  # 금색
            "outline": "#000000",
            "shadow": "#000000",
        },
        # === 기타 ===
        "믿거나말거나": {
            "primary": "#FF6600",    # 주황
            "secondary": "#FFFF00",  # 노랑
            "outline": "#000000",
            "shadow": "#000000",
        },
    }

    def __init__(self):
        self.font_paths = self._find_korean_fonts()

    def _find_korean_fonts(self) -> dict:
        """시스템에서 한글 폰트 찾기"""
        font_paths = {
            "bold": None,
            "extrabold": None,  # 더 두꺼운 폰트
            "regular": None,
        }

        # 가능한 폰트 경로들 (우선순위: ExtraBold > Bold > Regular)
        possible_paths = [
            # Linux - ExtraBold/Black
            "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Black.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
            # Linux - Bold
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            # Windows
            "C:/Windows/Fonts/malgunbd.ttf",  # 맑은 고딕 볼드
            "C:/Windows/Fonts/malgun.ttf",
            # Mac
            "/Library/Fonts/AppleGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            # 프로젝트 폴더
            "assets/fonts/NanumGothicExtraBold.ttf",
            "assets/fonts/NanumGothicBold.ttf",
            "assets/fonts/NanumGothic.ttf",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                if "ExtraBold" in path or "Black" in path:
                    font_paths["extrabold"] = font_paths["extrabold"] or path
                elif "Bold" in path or "bd" in path.lower():
                    font_paths["bold"] = font_paths["bold"] or path
                else:
                    font_paths["regular"] = font_paths["regular"] or path

        # 폴백 체인: extrabold → bold → regular
        if not font_paths["extrabold"]:
            font_paths["extrabold"] = font_paths["bold"]
        if not font_paths["bold"]:
            font_paths["bold"] = font_paths["regular"]

        return font_paths

    def _get_font_for_language(self, language: str = "ko") -> str:
        """언어별 폰트 경로 반환"""
        # 한국어: 가평한석봉체
        if language == "ko" and os.path.exists(self.KOREAN_THUMBNAIL_FONT):
            return self.KOREAN_THUMBNAIL_FONT
        # 영어: Playfair Display Italic (우아한 세리프체)
        if language == "en" and os.path.exists(self.ENGLISH_THUMBNAIL_FONT):
            return self.ENGLISH_THUMBNAIL_FONT
        # 일본어: 佑字肅 (서예체)
        if language == "ja" and os.path.exists(self.JAPANESE_THUMBNAIL_FONT):
            return self.JAPANESE_THUMBNAIL_FONT
        # 폰트 없을 때: 기존 시스템 폰트
        return self.font_paths["extrabold"] or self.font_paths["bold"] or "arial.ttf"

    def create_thumbnail(
        self,
        background_image: str,
        main_text: str,
        sub_text: str = "",
        bottom_text: str = "",
        style: str = "불교종교",
        darken: float = 0.5,
        output_path: str = None,
        language: str = "ko"
    ) -> str:
        """
        썸네일 생성

        Args:
            background_image: 배경 이미지 경로
            main_text: 메인 텍스트 (큰 글씨)
            sub_text: 서브 텍스트 (위에 작은 글씨)
            bottom_text: 하단 텍스트
            style: 색상 스타일 (불교종교/뉴스/정보/믿거나말거나)
            darken: 배경 어둡게 (0.0~1.0)
            output_path: 출력 경로
            language: 언어 코드 (ko/en/ja) - 한국어만 전용 폰트 사용

        Returns:
            생성된 썸네일 경로
        """
        # 배경 이미지 로드 및 리사이즈
        bg = Image.open(background_image).convert("RGBA")
        bg = self._resize_and_crop(bg, self.THUMBNAIL_SIZE)

        # 배경 어둡게
        if darken > 0:
            enhancer = ImageEnhance.Brightness(bg)
            bg = enhancer.enhance(1 - darken)

        # 색상 가져오기
        colors = self.COLOR_PRESETS.get(style, self.COLOR_PRESETS["불교강의"])

        # 텍스트 오버레이
        draw = ImageDraw.Draw(bg)

        # 폰트 로드 (언어별 전용 폰트)
        try:
            font_path = self._get_font_for_language(language)
            print(f"[ThumbnailEngine] 폰트 로드 시도: {font_path} (language={language})")

            if not os.path.exists(font_path):
                raise FileNotFoundError(f"폰트 파일 없음: {font_path}")

            main_font = ImageFont.truetype(font_path, 100)
            sub_font = ImageFont.truetype(font_path, 56)
            bottom_font = ImageFont.truetype(font_path, 40)
            print(f"[ThumbnailEngine] ✅ 폰트 로드 성공: {os.path.basename(font_path)}")
        except Exception as e:
            print(f"[ThumbnailEngine] ⚠️ 폰트 로드 실패: {e}")
            # 폴백: 시스템 폰트 시도
            fallback_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                "arial.ttf",
            ]
            loaded = False
            for fb_font in fallback_fonts:
                if os.path.exists(fb_font):
                    try:
                        main_font = ImageFont.truetype(fb_font, 100)
                        sub_font = ImageFont.truetype(fb_font, 56)
                        bottom_font = ImageFont.truetype(fb_font, 40)
                        print(f"[ThumbnailEngine] 폴백 폰트 사용: {fb_font}")
                        loaded = True
                        break
                    except Exception:
                        continue
            if not loaded:
                print(f"[ThumbnailEngine] ❌ 모든 폰트 로드 실패, 기본 폰트 사용")
                main_font = ImageFont.load_default()
                sub_font = ImageFont.load_default()
                bottom_font = ImageFont.load_default()

        # 텍스트 위치 계산
        width, height = self.THUMBNAIL_SIZE

        # 서브 텍스트 (상단)
        if sub_text:
            self._draw_text_with_outline(
                draw, sub_text, sub_font,
                position=(width // 2, height // 3 - 50),
                fill=colors["secondary"],
                outline=colors["outline"],
                outline_width=6  # 두꺼운 외곽선
            )

        # 메인 텍스트 (중앙) - 멀티라인 지원
        if "\n" in main_text:
            # 2줄 텍스트: 같은 크기로 각 줄 렌더링
            lines = main_text.split("\n")
            line_height = 110  # 줄 간격 (폰트 크기 증가로 조정)
            total_height = len(lines) * line_height
            start_y = height // 2 - total_height // 2 + line_height // 2

            for i, line in enumerate(lines):
                self._draw_text_with_outline(
                    draw, line, main_font,
                    position=(width // 2, start_y + i * line_height),
                    fill=colors["primary"],
                    outline=colors["outline"],
                    outline_width=8  # 두꺼운 외곽선
                )
        else:
            # 1줄 텍스트
            self._draw_text_with_outline(
                draw, main_text, main_font,
                position=(width // 2, height // 2),
                fill=colors["primary"],
                outline=colors["outline"],
                outline_width=8  # 두꺼운 외곽선
            )

        # 하단 텍스트
        if bottom_text:
            self._draw_text_with_outline(
                draw, bottom_text, bottom_font,
                position=(width // 2, height - 80),
                fill=colors["secondary"],
                outline=colors["outline"],
                outline_width=4  # 두꺼운 외곽선
            )

        # RGB로 변환 (저장용)
        bg = bg.convert("RGB")

        # 저장
        if not output_path:
            output_path = "thumbnail_output.jpg"

        bg.save(output_path, "JPEG", quality=95)
        print(f"[ThumbnailEngine] 썸네일 생성: {output_path}")

        return output_path

    def _resize_and_crop(self, img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
        """이미지를 타겟 크기에 맞게 리사이즈 및 크롭"""
        target_w, target_h = target_size
        img_w, img_h = img.size

        # 비율 계산
        ratio = max(target_w / img_w, target_h / img_h)
        new_size = (int(img_w * ratio), int(img_h * ratio))

        img = img.resize(new_size, Image.Resampling.LANCZOS)

        # 중앙 크롭
        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2

        return img.crop((left, top, left + target_w, top + target_h))

    def _draw_text_with_outline(
        self,
        draw: ImageDraw.Draw,
        text: str,
        font: ImageFont.FreeTypeFont,
        position: Tuple[int, int],
        fill: str,
        outline: str,
        outline_width: int = 3
    ):
        """외곽선이 있는 텍스트 그리기"""
        x, y = position

        # 텍스트 바운딩 박스
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 중앙 정렬
        x = x - text_width // 2
        y = y - text_height // 2

        # 외곽선 그리기 (8방향)
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline)

        # 메인 텍스트
        draw.text((x, y), text, font=font, fill=fill)

    def generate_thumbnail_text(
        self,
        style: str = "정보",
        duration: int = 10,
        hook_type: str = None
    ) -> str:
        """
        썸네일 텍스트 자동 생성 (초단문)

        Args:
            style: 콘텐츠 스타일 (불교종교/뉴스/정보/믿거나말거나)
            duration: 영상 길이 (분)
            hook_type: 후킹 타입 (None이면 랜덤)

        Returns:
            생성된 썸네일 텍스트 (8~16자)
        """
        # 1. 템플릿 풀에서 1개 선택
        templates = YOUTUBE_THUMBNAIL_TEXT_TEMPLATES.get(
            style,
            YOUTUBE_THUMBNAIL_TEXT_TEMPLATES.get("정보", ["정보"])
        )
        text = random.choice(templates)

        # 2. {duration} 치환
        text = text.format(duration=duration)

        # 3. 금지어 필터링 (걸리면 다시 뽑기, 최대 5회)
        attempts = 0
        while attempts < 5:
            has_forbidden = False
            for forbidden in YOUTUBE_THUMBNAIL_FORBIDDEN_WORDS:
                if forbidden in text:
                    has_forbidden = True
                    break

            if not has_forbidden:
                break

            text = random.choice(templates).format(duration=duration)
            attempts += 1

        # 4. 길이 제한 (max_chars)
        max_chars = YOUTUBE_THUMBNAIL_RULES.get("max_chars", 16)
        if len(text) > max_chars:
            text = text[:max_chars]

        # 5. 구두점 제거 (avoid_punctuation)
        if YOUTUBE_THUMBNAIL_RULES.get("avoid_punctuation", True):
            text = text.rstrip(".!?。！？")

        print(f"[ThumbnailEngine] 썸네일 텍스트 생성: '{text}' ({len(text)}자)")
        return text

    def generate_hook_message_from_content(
        self,
        title: str = None,
        description: str = None,
        style: str = "불교종교"
    ) -> Tuple[str, str]:
        """
        LLM을 사용하여 유튜브 제목/설명 분석 후 후킹 썸네일 메시지 생성

        Args:
            title: 유튜브 제목
            description: 유튜브 설명
            style: 콘텐츠 스타일

        Returns:
            (sub_text, main_text) - 상단 메시지, 메인 메시지
        """
        # LLM에 보낼 콘텐츠 구성 (제목 + 설명만)
        content_parts = []
        if title:
            content_parts.append(f"[유튜브 제목]\n{title}")
        if description:
            # 설명은 처음 500자만
            desc_preview = description[:500] + ("..." if len(description) > 500 else "")
            content_parts.append(f"[유튜브 설명]\n{desc_preview}")

        if not content_parts:
            # 콘텐츠가 없으면 폴백
            print("[ThumbnailEngine] ⚠️ 콘텐츠 없음, 기본 템플릿 사용")
            return self._fallback_hook_message(style)

        user_content = "\n\n".join(content_parts)
        user_content += f"\n\n[콘텐츠 스타일: {style}]"

        try:
            # Anthropic API 호출
            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                system=THUMBNAIL_HOOK_PROMPT,
                messages=[
                    {"role": "user", "content": f"다음 유튜브 콘텐츠를 분석하여 후킹 썸네일 문구를 생성해주세요:\n\n{user_content}"}
                ]
            )

            # 응답 파싱
            response_text = response.content[0].text
            sub_text, main_text = self._parse_hook_response(response_text)

            print(f"[ThumbnailEngine] 🎯 LLM 후킹 메시지 생성: '{sub_text}' + '{main_text}'")
            return sub_text, main_text

        except Exception as e:
            print(f"[ThumbnailEngine] ❌ LLM 호출 실패: {e}, 폴백 사용")
            return self._fallback_hook_message(style)

    def _parse_hook_response(self, response_text: str) -> Tuple[str, str]:
        """LLM 응답에서 sub_text, main_text 추출"""
        try:
            # JSON 블록 찾기
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                sub_text = data.get("sub_text", "").strip()
                main_text = data.get("main_text", "").strip()

                # 구두점 제거
                sub_text = sub_text.rstrip(".!?。！？")
                main_text = main_text.rstrip(".!?。！？")

                if sub_text and main_text:
                    return sub_text, main_text
        except json.JSONDecodeError:
            pass

        # JSON 파싱 실패 시 텍스트에서 직접 추출 시도
        lines = [l.strip() for l in response_text.split('\n') if l.strip()]
        if len(lines) >= 2:
            return lines[0][:10], lines[1][:10]

        return "오늘 밤", "이 이야기"

    def _fallback_hook_message(self, style: str) -> Tuple[str, str]:
        """LLM 실패 시 템플릿 기반 폴백"""
        templates = THUMBNAIL_HOOK_TEMPLATES.get(style, THUMBNAIL_HOOK_TEMPLATES.get("불교종교", []))
        if templates:
            chosen = random.choice(templates)
            return chosen["sub"], chosen["main"]
        return "오늘 밤", "이 이야기"

    def _detect_content_category(self, content: str) -> str:
        """콘텐츠 카테고리 감지"""
        content_lower = content.lower()

        # 역사/인물 키워드
        history_keywords = ["왕", "황제", "태자", "승려", "스님", "대사", "년전", "시대", "역사", "경전", "부처님"]
        # 감정/공감 키워드
        emotion_keywords = ["불안", "걱정", "힘들", "외로", "슬픔", "화", "분노", "마음", "잠", "밤"]
        # 조언/경고 키워드
        advice_keywords = ["하지마", "조심", "끊어", "놓아", "정리", "이후", "나이"]
        # 질문/호기심 키워드
        question_keywords = ["왜", "어떻게", "무엇", "진짜", "비밀", "숨겨", "몰랐"]

        scores = {
            "history": sum(1 for k in history_keywords if k in content),
            "emotion": sum(1 for k in emotion_keywords if k in content),
            "advice": sum(1 for k in advice_keywords if k in content),
            "question": sum(1 for k in question_keywords if k in content),
        }

        # 가장 높은 점수의 카테고리 반환
        max_category = max(scores, key=scores.get)
        if scores[max_category] > 0:
            return max_category
        return "general"

    def _filter_templates_by_category(
        self,
        templates: List[dict],
        category: str,
        content: str
    ) -> List[dict]:
        """카테고리에 맞는 템플릿 필터링"""
        category_keywords = {
            "history": ["승려", "왕", "년 전", "황제", "경전", "역사", "숨긴", "비밀"],
            "emotion": ["마음", "밤", "불안", "힘들", "생각", "화"],
            "advice": ["하지", "꼭", "정리", "놓아", "이후"],
            "question": ["왜", "진짜", "의미", "깨달음"],
        }

        keywords = category_keywords.get(category, [])
        if not keywords:
            return templates

        filtered = []
        for t in templates:
            combined = f"{t['sub']} {t['main']}"
            if any(k in combined for k in keywords):
                filtered.append(t)

        return filtered if filtered else templates

    def _personalize_hook(
        self,
        sub_text: str,
        main_text: str,
        content: str,
        style: str
    ) -> Tuple[str, str]:
        """콘텐츠 키워드로 메시지 개인화"""
        # 인물명 추출 시도
        import re
        person_match = re.search(r'([가-힣]{2,4})(태자|대사|스님|왕|황제)', content)

        if person_match and "승려" in sub_text:
            person_name = person_match.group(0)
            sub_text = sub_text.replace("이 승려", person_name)
        elif person_match and "왕자" in sub_text:
            person_name = person_match.group(0)
            sub_text = sub_text.replace("왕자", person_name)

        return sub_text, main_text

    def create_thumbnail_with_hook(
        self,
        background_image: str,
        title: str = None,
        description: str = None,
        style: str = "불교종교",
        darken: float = 0.5,
        output_path: str = None,
        language: str = "ko"
    ) -> str:
        """
        유튜브 업로드 내용 기반 후킹 썸네일 생성

        Args:
            background_image: 배경 이미지 경로
            title: 유튜브 제목
            description: 유튜브 설명
            style: 콘텐츠 스타일
            darken: 배경 어둡게 (0.0~1.0)
            output_path: 출력 경로
            language: 언어 코드

        Returns:
            생성된 썸네일 경로
        """
        # 후킹 메시지 자동 생성
        sub_text, main_text = self.generate_hook_message_from_content(
            title=title,
            description=description,
            style=style
        )

        # 썸네일 생성
        return self.create_thumbnail(
            background_image=background_image,
            main_text=main_text,
            sub_text=sub_text,
            style=style,
            darken=darken,
            output_path=output_path,
            language=language
        )

    def create_from_project(
        self,
        project,
        main_text: str = None,
        sub_text: str = None,
        output_path: str = None,
        auto_generate: bool = True,
        use_hook: bool = True
    ) -> str:
        """
        프로젝트에서 썸네일 생성 (후킹 메시지 자동 생성)

        Args:
            project: Project 객체
            main_text: 메인 텍스트 (None이면 자동 생성)
            sub_text: 상단 텍스트 (None이면 자동 생성)
            output_path: 출력 경로
            auto_generate: main_text 없을 때 자동 생성 여부
            use_hook: 후킹 메시지 사용 여부 (True면 상단+메인 연결형)

        Returns:
            썸네일 이미지 경로
        """
        # 첫 번째 이미지를 배경으로 사용
        if project.cut_paths:
            background = project.cut_paths[0]
        else:
            raise ValueError("프로젝트에 이미지가 없습니다")

        # 스타일
        style = getattr(project, 'style', '정보')
        duration = getattr(project, 'duration_min', 10)
        language = getattr(project, 'language', 'ko')

        # 메인/서브 텍스트 자동 생성
        if not main_text and auto_generate:
            if use_hook and project.script:
                # 후킹 메시지 생성 (제목 + 설명 기반)
                sub_text, main_text = self.generate_hook_message_from_content(
                    title=project.script.title if project.script else None,
                    description=getattr(project, 'description', None),
                    style=style
                )
            else:
                # 기존 방식 (단순 템플릿)
                main_text = self.generate_thumbnail_text(
                    style=style,
                    duration=duration
                )

        # 출력 경로
        if not output_path:
            output_path = os.path.join("projects", project.project_id, "thumbnail.jpg")

        return self.create_thumbnail(
            background_image=background,
            main_text=main_text,
            sub_text=sub_text or "",
            style=style,
            output_path=output_path,
            language=language
        )
