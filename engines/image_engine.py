"""
이미지 생성 엔진 - 개별 이미지 생성
- fal.ai (기본)
- DALL-E 3
- Google Imagen
각 씬별 개별 이미지 생성, 400자 이내 프롬프트
"""
import os
import requests
import base64
from typing import List, Optional
from abc import ABC, abstractmethod

from models.types import Script, Scene
from config import DURATION_SPECS, IMAGE_CONFIG


class ImageGenerator(ABC):
    """이미지 생성기 추상 클래스"""

    @abstractmethod
    def generate(self, prompt: str, output_path: str) -> str:
        """이미지 생성"""
        pass


class FalGenerator(ImageGenerator):
    """fal.ai 이미지 생성기 (기본)"""

    def __init__(self):
        import fal_client
        self.client = fal_client

    def generate(self, prompt: str, output_path: str) -> str:
        """fal.ai로 이미지 생성"""
        result = self.client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "image_size": "landscape_16_9",
                "num_images": 1,
                "enable_safety_checker": False,
            },
        )

        image_url = result["images"][0]["url"]
        self._download(image_url, output_path)
        return output_path

    def _download(self, url: str, output_path: str):
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)


class DalleGenerator(ImageGenerator):
    """DALL-E 3 이미지 생성기"""

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(self, prompt: str, output_path: str) -> str:
        """DALL-E 3로 이미지 생성"""
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=IMAGE_CONFIG.get("size_landscape", "1792x1024"),
            quality=IMAGE_CONFIG.get("quality", "hd"),
            style=IMAGE_CONFIG.get("style", "vivid"),
            n=1
        )

        image_url = response.data[0].url
        self._download(image_url, output_path)
        return output_path

    def _download(self, url: str, output_path: str):
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)


class ImagenGenerator(ImageGenerator):
    """Google Imagen 이미지 생성기"""

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.ImageGenerationModel("imagen-3.0-generate-001")

    def generate(self, prompt: str, output_path: str) -> str:
        """Imagen으로 이미지 생성"""
        response = self.model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
        )

        # 이미지 저장
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        response.images[0].save(output_path)
        return output_path


class ImageEngine:
    """
    개별 이미지 생성 엔진
    - 씬별로 개별 이미지 생성
    - fal.ai (기본), DALL-E, Imagen 지원
    """

    GENERATORS = {
        "fal": FalGenerator,
        "dalle": DalleGenerator,
        "imagen": ImagenGenerator,
    }

    def __init__(self, engine: str = "fal"):
        """
        Args:
            engine: 이미지 생성 엔진 (fal, dalle, imagen)
        """
        self.engine_name = engine
        self._generator: Optional[ImageGenerator] = None

    @property
    def generator(self) -> ImageGenerator:
        """지연 초기화된 생성기"""
        if self._generator is None:
            generator_class = self.GENERATORS.get(self.engine_name)
            if not generator_class:
                raise ValueError(f"지원하지 않는 엔진: {self.engine_name}")
            self._generator = generator_class()
        return self._generator

    def generate_scene_images(
        self,
        script: Script,
        output_dir: str,
        style_prefix: str = ""
    ) -> List[str]:
        """
        각 씬별로 이미지 생성

        Args:
            script: Script 객체
            output_dir: 출력 디렉토리
            style_prefix: 공통 스타일 접두사

        Returns:
            생성된 이미지 경로 리스트
        """
        os.makedirs(output_dir, exist_ok=True)
        image_paths = []

        for scene in script.scenes:
            # 씬별 이미지 생성
            prompt = self._build_scene_prompt(scene, style_prefix)
            output_path = os.path.join(output_dir, f"scene_{scene.scene_id:02d}.png")

            print(f"[ImageEngine] Scene {scene.scene_id}: {scene.title}")
            print(f"[ImageEngine] Prompt: {prompt[:100]}...")

            try:
                self.generator.generate(prompt, output_path)
                image_paths.append(output_path)
                print(f"[ImageEngine] ✓ Saved: {output_path}")
            except Exception as e:
                print(f"[ImageEngine] ✗ Error: {e}")

        return image_paths

    def generate_images_from_prompts(
        self,
        prompts: List[str],
        output_dir: str
    ) -> List[str]:
        """
        프롬프트 리스트로 이미지 생성

        Args:
            prompts: 이미지 프롬프트 리스트
            output_dir: 출력 디렉토리

        Returns:
            생성된 이미지 경로 리스트
        """
        os.makedirs(output_dir, exist_ok=True)
        image_paths = []

        for i, prompt in enumerate(prompts, 1):
            output_path = os.path.join(output_dir, f"image_{i:02d}.png")

            print(f"[ImageEngine] Image {i}/{len(prompts)}")
            print(f"[ImageEngine] Prompt: {prompt[:80]}...")

            try:
                self.generator.generate(prompt, output_path)
                image_paths.append(output_path)
                print(f"[ImageEngine] ✓ Saved")
            except Exception as e:
                print(f"[ImageEngine] ✗ Error: {e}")

        return image_paths

    def generate_single(self, prompt: str, output_path: str) -> str:
        """단일 이미지 생성"""
        print(f"[ImageEngine] Generating with {self.engine_name}...")
        return self.generator.generate(prompt, output_path)

    def _build_scene_prompt(self, scene: Scene, style_prefix: str = "") -> str:
        """
        씬에서 이미지 프롬프트 생성 (400자 이내)

        Args:
            scene: Scene 객체
            style_prefix: 공통 스타일 접두사

        Returns:
            이미지 프롬프트 (400자 이내)
        """
        # 씬에 image_prompt가 있으면 사용
        if scene.image_prompt:
            prompt = scene.image_prompt
        else:
            # 씬 텍스트에서 핵심 내용 추출 (첫 2문장)
            sentences = [s.strip() for s in scene.text.split('.') if s.strip()]
            core_content = '. '.join(sentences[:2]) if sentences else scene.title

            prompt = f"{scene.title}. {core_content}"

        # 스타일 프리픽스 추가
        if style_prefix:
            prompt = f"{style_prefix}. {prompt}"

        # 400자 제한
        if len(prompt) > 400:
            prompt = prompt[:397] + "..."

        return prompt
