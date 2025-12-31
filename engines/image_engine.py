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

    # 사용 가능한 모델들
    MODELS = {
        "flux-schnell": "fal-ai/flux/schnell",       # 빠름, 저렴
        "flux-dev": "fal-ai/flux/dev",               # 균형
        "flux-pro": "fal-ai/flux-pro",               # 고품질
        "flux-pro-v1.1": "fal-ai/flux-pro/v1.1",     # 최신 프로
        "flux-ultra": "fal-ai/flux-pro/v1.1-ultra",  # 최고 품질
    }

    def __init__(self, model: str = "flux-schnell"):
        import fal_client
        self.client = fal_client
        self.model = self.MODELS.get(model, self.MODELS["flux-schnell"])
        print(f"[FalGenerator] 모델: {model} → {self.model}")

    def generate(self, prompt: str, output_path: str) -> str:
        """fal.ai로 이미지 생성"""
        result = self.client.subscribe(
            self.model,
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

    # 사용 가능한 모델들
    MODELS = {
        "imagen-3": "imagen-3.0-generate-001",       # 고품질
        "imagen-3-fast": "imagen-3.0-fast-generate-001",  # 빠름, 저렴
    }

    def __init__(self, model: str = "imagen-3"):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model_id = self.MODELS.get(model, self.MODELS["imagen-3"])
        self.model = genai.ImageGenerationModel(model_id)
        print(f"[ImagenGenerator] 모델: {model} → {model_id}")

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
    - fal.ai (기본), DALL-E, Imagen, StoryMaker 지원
    """

    GENERATORS = {
        "fal": FalGenerator,
        "dalle": DalleGenerator,
        "imagen": ImagenGenerator,
        "storymaker": None,  # 별도 처리 (StoryMakerEngine 사용)
    }

    # 엔진별 모델 옵션
    MODEL_OPTIONS = {
        "fal": {
            "flux-schnell": "빠름/저렴 ($0.003)",
            "flux-dev": "균형 ($0.025)",
            "flux-pro": "고품질 ($0.05)",
            "flux-pro-v1.1": "최신 프로 ($0.05)",
            "flux-ultra": "최고 품질 ($0.06)",
        },
        "imagen": {
            "imagen-3-fast": "빠름/저렴",
            "imagen-3": "고품질",
        },
        "dalle": {
            "dall-e-3": "DALL-E 3",
        },
        "storymaker": {
            "gpt-image-1": "스토리텔링전용 (GPT Image)",
        },
    }

    def __init__(self, engine: str = "fal", model: str = None):
        """
        Args:
            engine: 이미지 생성 엔진 (fal, dalle, imagen)
            model: 사용할 모델 (엔진별 기본값 사용 가능)
        """
        self.engine_name = engine
        self.model = model
        self._generator: Optional[ImageGenerator] = None

    @property
    def generator(self):
        """지연 초기화된 생성기"""
        if self._generator is None:
            # StoryMaker는 별도 엔진 사용
            if self.engine_name == "storymaker":
                from storymaker import StoryMakerEngine
                model = self.model or "gpt-image-1"
                self._generator = StoryMakerEngine(model=model)
                return self._generator

            generator_class = self.GENERATORS.get(self.engine_name)
            if not generator_class:
                raise ValueError(f"지원하지 않는 엔진: {self.engine_name}")

            # 모델 파라미터가 있는 경우 전달
            if self.model and self.engine_name in ["fal", "imagen"]:
                self._generator = generator_class(model=self.model)
            else:
                self._generator = generator_class()
        return self._generator

    @property
    def is_storymaker(self) -> bool:
        """StoryMaker 엔진 사용 여부"""
        return self.engine_name == "storymaker"

    def generate_scene_images(
        self,
        script: Script,
        output_dir: str,
        style_prefix: str = "",
        storymaker_config: dict = None
    ) -> List[str]:
        """
        각 씬별로 이미지 생성

        Args:
            script: Script 객체
            output_dir: 출력 디렉토리
            style_prefix: 공통 스타일 접두사
            storymaker_config: StoryMaker 설정 (character, world 등)

        Returns:
            생성된 이미지 경로 리스트
        """
        os.makedirs(output_dir, exist_ok=True)
        image_paths = []

        # StoryMaker 엔진 사용 시 별도 처리
        if self.is_storymaker:
            return self._generate_with_storymaker(
                script, output_dir, storymaker_config or {}
            )

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

    def _generate_with_storymaker(
        self,
        script: Script,
        output_dir: str,
        config: dict
    ) -> List[str]:
        """
        StoryMaker 엔진으로 이미지 생성

        Args:
            script: Script 객체
            output_dir: 출력 디렉토리
            config: StoryMaker 설정 (character, world, camera 등)

        Returns:
            생성된 이미지 경로 리스트
        """
        image_paths = []
        engine = self.generator  # StoryMakerEngine

        # 기본 설정
        default_character = config.get("character", "young_monk")
        default_world = config.get("world", "buddha_era_night")
        default_camera = config.get("camera", "MEDIUM")
        default_place = config.get("place", "temple_hall")
        quality = config.get("quality", "low")

        # 카메라 순환 패턴: WIDE → MEDIUM → CLOSE → MEDIUM
        camera_cycle = ["WIDE", "MEDIUM", "CLOSE", "MEDIUM"]

        for i, scene in enumerate(script.scenes):
            output_path = os.path.join(output_dir, f"scene_{scene.scene_id:02d}.png")

            # 씬 텍스트 추출 (image_prompt 우선, 없으면 text 사용)
            scene_action = scene.image_prompt or scene.text or scene.title
            # 2문장 이내로 자르기
            if scene_action:
                sentences = scene_action.split('.')
                scene_action = '. '.join(sentences[:2]).strip()
                if not scene_action.endswith('.'):
                    scene_action += '.'

            # 카메라 순환
            camera = camera_cycle[i % len(camera_cycle)]

            print(f"[StoryMaker] Scene {scene.scene_id}: {scene.title}")
            print(f"[StoryMaker] Action: {scene_action[:80]}...")
            print(f"[StoryMaker] Camera: {camera}, Character: {default_character}")

            try:
                engine.generate_scene(
                    scene_action=scene_action,
                    output_path=output_path,
                    character=default_character,
                    world=default_world,
                    camera=camera,
                    place=default_place,
                    quality=quality
                )
                image_paths.append(output_path)
                print(f"[StoryMaker] ✓ Saved: {output_path}")
            except Exception as e:
                print(f"[StoryMaker] ✗ Error: {e}")
                image_paths.append(None)

        return image_paths

    def generate_images_from_prompts(
        self,
        prompts: List[str],
        output_dir: str,
        storymaker_config: dict = None
    ) -> List[str]:
        """
        프롬프트 리스트로 이미지 생성

        Args:
            prompts: 이미지 프롬프트 리스트
            output_dir: 출력 디렉토리
            storymaker_config: StoryMaker 설정 (character_type, world_style 등)

        Returns:
            생성된 이미지 경로 리스트
        """
        os.makedirs(output_dir, exist_ok=True)
        image_paths = []

        # StoryMaker 엔진 사용 시 하이브리드 컴파일러 적용
        if self.is_storymaker:
            from storymaker.compiler import compile_hybrid_prompt
            config = storymaker_config or {}
            character_type = config.get("character_type", "old_grandfather")
            world_style = config.get("world_style", "korean_minhwa")

            # 카메라 순환 패턴
            camera_cycle = ["WIDE", "MEDIUM", "CLOSE", "MEDIUM"]

        for i, prompt in enumerate(prompts, 1):
            output_path = os.path.join(output_dir, f"image_{i:02d}.png")

            # StoryMaker: 하이브리드 프롬프트 컴파일
            if self.is_storymaker:
                camera = camera_cycle[(i - 1) % len(camera_cycle)]
                compiled_prompt = compile_hybrid_prompt(
                    original_prompt=prompt,
                    character_type=character_type,
                    world_style=world_style,
                    camera=camera
                )
                print(f"[StoryMaker] Image {i}/{len(prompts)} (Camera: {camera})")
                print(f"[StoryMaker] Original: {prompt[:60]}...")
                print(f"[StoryMaker] Compiled: {compiled_prompt[:80]}...")
                prompt_to_use = compiled_prompt
            else:
                print(f"[ImageEngine] Image {i}/{len(prompts)}")
                print(f"[ImageEngine] Prompt: {prompt[:80]}...")
                prompt_to_use = prompt

            try:
                self.generator.generate(prompt_to_use, output_path)
                image_paths.append(output_path)
                print(f"[{'StoryMaker' if self.is_storymaker else 'ImageEngine'}] ✓ Saved")
            except Exception as e:
                print(f"[{'StoryMaker' if self.is_storymaker else 'ImageEngine'}] ✗ Error: {e}")

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
