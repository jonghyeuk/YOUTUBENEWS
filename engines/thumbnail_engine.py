"""
썸네일 생성 엔진 - PIL 기반
한글 텍스트 오버레이 + 그림자/외곽선 효과
"""
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import List, Tuple, Optional

from config import (
    YOUTUBE_THUMBNAIL_TEXT_TEMPLATES,
    YOUTUBE_THUMBNAIL_HOOK_SNIPPETS,
    YOUTUBE_THUMBNAIL_FORBIDDEN_WORDS,
    YOUTUBE_THUMBNAIL_RULES,
)


class ThumbnailEngine:
    """YouTube 썸네일 생성 엔진"""

    # 기본 설정
    THUMBNAIL_SIZE = (1280, 720)  # YouTube 권장 크기

    # 스타일별 색상 프리셋
    COLOR_PRESETS = {
        "불교강의": {
            "primary": "#FFFFFF",    # 흰색 (참고 이미지 스타일)
            "secondary": "#FFD700",  # 금색
            "outline": "#000000",    # 검정 외곽선
            "shadow": "#000000",     # 그림자
        },
        "불교종교": {
            "primary": "#FFD700",    # 금색
            "secondary": "#FFFFFF",  # 흰색
            "outline": "#000000",    # 검정 외곽선
            "shadow": "#000000",     # 그림자
        },
        "불교명상": {
            "primary": "#FFFFFF",    # 흰색
            "secondary": "#FFD700",  # 금색
            "outline": "#000000",
            "shadow": "#000000",
        },
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

    def create_thumbnail(
        self,
        background_image: str,
        main_text: str,
        sub_text: str = "",
        bottom_text: str = "",
        style: str = "불교종교",
        darken: float = 0.5,
        output_path: str = None
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

        # 폰트 로드 (ExtraBold 우선 사용으로 더 두꺼운 글씨)
        try:
            # 메인 텍스트: ExtraBold + 큰 사이즈 + 두꺼운 외곽선
            main_font = ImageFont.truetype(self.font_paths["extrabold"] or self.font_paths["bold"] or "arial.ttf", 100)
            sub_font = ImageFont.truetype(self.font_paths["extrabold"] or self.font_paths["bold"] or "arial.ttf", 56)
            bottom_font = ImageFont.truetype(self.font_paths["bold"] or "arial.ttf", 40)
        except Exception:
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

    def create_from_project(
        self,
        project,
        main_text: str = None,
        output_path: str = None,
        auto_generate: bool = True
    ) -> str:
        """
        프로젝트에서 썸네일 생성 (메인 텍스트만 자동 생성)

        Args:
            project: Project 객체
            main_text: 메인 텍스트 (None이면 자동 생성)
            output_path: 출력 경로
            auto_generate: main_text 없을 때 자동 생성 여부

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

        # 메인 텍스트 자동 생성 (초단문 템플릿 사용)
        if not main_text:
            if auto_generate:
                main_text = self.generate_thumbnail_text(
                    style=style,
                    duration=duration
                )
            elif project.script:
                # 폴백: 스크립트 제목 사용 (권장하지 않음)
                main_text = project.script.title

        # 출력 경로
        if not output_path:
            output_path = os.path.join("projects", project.project_id, "thumbnail.jpg")

        return self.create_thumbnail(
            background_image=background,
            main_text=main_text,
            style=style,
            output_path=output_path
        )
