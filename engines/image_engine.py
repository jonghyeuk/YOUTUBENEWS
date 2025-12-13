import os
import re
import base64
import io
import time
from typing import List, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont
from models.types import Scene, ContentProfile

# Google Generative AI (Gemini/Imagen)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[ImageEngine] Warning: google-generativeai not installed")


class ImageEngine:
    """
    이미지 생성 엔진 - Google Gemini/Imagen 전용

    뉴스 영상을 위한 이미지 생성
    - 애니 스타일: 한국 웹툰/만화 스타일
    - 실사 스타일: 뉴스 보도 사진 스타일
    """

    def __init__(self):
        """Gemini 클라이언트 초기화"""
        self.api_key = os.getenv("GEMINI_API_KEY")

        if self.api_key and GEMINI_AVAILABLE:
            genai.configure(api_key=self.api_key)
            print("[ImageEngine] Gemini initialized")
        else:
            print("[ImageEngine] Warning: Gemini API not available")

    def generate_scene_images(
        self,
        scenes: List[Scene],
        output_dir: str,
        category: str = "news",
        profile: ContentProfile = None
    ) -> Tuple[List[str], List[Dict]]:
        """
        씬별 이미지 생성

        Args:
            scenes: Scene 객체 리스트
            output_dir: 출력 디렉토리
            category: 카테고리
            profile: 콘텐츠 프로필

        Returns:
            (이미지 경로 리스트, 이벤트 로그 리스트)
        """
        os.makedirs(output_dir, exist_ok=True)

        image_paths = []
        event_logs = []
        image_style = os.getenv("IMAGE_STYLE", "realistic")

        for idx, scene in enumerate(scenes):
            output_path = os.path.join(output_dir, f"scene_{idx:03d}.png")

            try:
                # 이미지 생성
                self._generate_image(
                    prompt=scene.image_prompt,
                    output_path=output_path,
                    image_style=image_style
                )

                image_paths.append(output_path)
                event_logs.append({
                    "scene_idx": idx,
                    "scene_id": scene.scene_id,
                    "status": "success",
                    "path": output_path
                })

                print(f"[ImageEngine] Scene {idx}: Generated - {output_path}")

                # API 레이트 리밋 방지
                time.sleep(1)

            except Exception as e:
                print(f"[ImageEngine] Scene {idx} Error: {e}")

                # 플레이스홀더 생성
                placeholder_path = self._create_placeholder(
                    output_path=output_path,
                    scene_id=scene.scene_id,
                    text=f"Scene {idx + 1}"
                )

                image_paths.append(placeholder_path)
                event_logs.append({
                    "scene_idx": idx,
                    "scene_id": scene.scene_id,
                    "status": "error",
                    "error": str(e),
                    "path": placeholder_path
                })

        return image_paths, event_logs

    def _generate_image(
        self,
        prompt: str,
        output_path: str,
        image_style: str = "realistic"
    ) -> str:
        """
        Gemini/Imagen으로 이미지 생성

        Args:
            prompt: 이미지 프롬프트
            output_path: 출력 경로
            image_style: 스타일 (anime / realistic)

        Returns:
            생성된 이미지 경로
        """
        if not self.api_key or not GEMINI_AVAILABLE:
            raise RuntimeError("Gemini API not available")

        # 스타일에 따른 프롬프트 강화
        enhanced_prompt = self._enhance_prompt(prompt, image_style)

        # 프롬프트 안전화
        safe_prompt = self._sanitize_prompt(enhanced_prompt)

        try:
            # Imagen 3 모델 사용
            model = genai.ImageGenerationModel("imagen-3.0-generate-002")

            response = model.generate_images(
                prompt=safe_prompt,
                number_of_images=1,
                aspect_ratio="16:9",  # 가로 영상용
                safety_filter_level="block_few",
                person_generation="allow_adult"
            )

            if response.images:
                # 이미지 저장
                image_data = response.images[0]._pil_image
                image_data.save(output_path, "PNG")
                return output_path

        except Exception as e:
            print(f"[ImageEngine] Imagen error: {e}")
            raise

        raise RuntimeError("Failed to generate image")

    def _enhance_prompt(self, prompt: str, image_style: str) -> str:
        """스타일에 따른 프롬프트 강화"""
        if not prompt:
            prompt = "News scene"

        if image_style == "anime":
            style_prefix = "Korean webtoon illustration style, clean line art, professional manhwa art, vibrant colors, "
            style_suffix = ", NOT photorealistic, NOT 3D render"
        else:
            style_prefix = "Photorealistic news photography style, professional journalism, realistic lighting, "
            style_suffix = ", NOT cartoon, NOT anime, NOT illustration"

        return f"{style_prefix}{prompt}{style_suffix}"

    def _sanitize_prompt(self, prompt: str) -> str:
        """프롬프트 안전화 - 위험한 단어 제거/치환"""
        if not prompt:
            return prompt

        # 위험 단어 치환 맵
        sanitize_map = {
            # 폭력 관련
            '피': 'red liquid',
            '피투성이': 'injured',
            '살인': 'incident',
            '살해': 'conflict',
            '죽음': 'end',
            '시체': 'figure',
            # 학대 관련
            '학대': 'hardship',
            '폭행': 'conflict',
            '구타': 'conflict',
            # 영어
            'blood': 'red',
            'murder': 'incident',
            'death': 'end',
            'corpse': 'figure',
            'abuse': 'hardship',
        }

        for bad_word, safe_word in sanitize_map.items():
            prompt = prompt.replace(bad_word, safe_word)

        # 중복 공백 제거
        prompt = re.sub(r'\s+', ' ', prompt).strip()

        # 길이 제한
        if len(prompt) > 2000:
            prompt = prompt[:2000]

        return prompt

    def _create_placeholder(
        self,
        output_path: str,
        scene_id: str,
        text: str = ""
    ) -> str:
        """플레이스홀더 이미지 생성"""
        width, height = 1920, 1080

        # 그라데이션 배경 생성
        image = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(image)

        # 간단한 그라데이션 효과
        for y in range(height):
            r = int(26 + (y / height) * 30)
            g = int(26 + (y / height) * 20)
            b = int(46 + (y / height) * 40)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 텍스트 추가
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 48)
        except:
            font = ImageFont.load_default()

        display_text = text or scene_id
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), display_text, fill='white', font=font)

        image.save(output_path, "PNG")
        return output_path

    def generate_thumbnail(
        self,
        prompt: str,
        text: str,
        output_path: str,
        category: str = "news"
    ) -> str:
        """
        썸네일 이미지 생성

        Args:
            prompt: 이미지 프롬프트
            text: 썸네일 텍스트
            output_path: 출력 경로
            category: 카테고리

        Returns:
            생성된 썸네일 경로
        """
        image_style = os.getenv("IMAGE_STYLE", "realistic")

        try:
            # 배경 이미지 생성
            self._generate_image(
                prompt=f"YouTube thumbnail background, {prompt}",
                output_path=output_path,
                image_style=image_style
            )

            # 텍스트 오버레이
            if text:
                self._add_thumbnail_text(output_path, text)

            return output_path

        except Exception as e:
            print(f"[ImageEngine] Thumbnail error: {e}")
            return self._create_placeholder(output_path, "thumbnail", text or "뉴스")

    def _add_thumbnail_text(self, image_path: str, text: str):
        """썸네일에 텍스트 오버레이"""
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 80)
        except:
            font = ImageFont.load_default()

        # 텍스트 위치 계산
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (image.width - text_width) // 2
        y = image.height - text_height - 100

        # 그림자 효과
        draw.text((x + 3, y + 3), text, fill='black', font=font)
        draw.text((x, y), text, fill='white', font=font)

        image.save(image_path, "PNG")
