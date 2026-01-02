"""
StoryMaker 엔진 - 스토리텔링 전용 이미지 생성
OpenAI gpt-image-1.5 백엔드 사용
"""

import os
import base64
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from .compiler import compile_prompt, compile_prompt_simple
from .postprocess import crop_to_16x9, process_for_video


class StoryMakerEngine:
    """
    스토리텔링 전용 이미지 생성 엔진

    특징:
    - 캐릭터/세계관/카메라/세트 프리셋 시스템
    - 일관된 프롬프트 컴파일
    - 1536x1024 생성 → 16:9 크롭
    - OpenAI gpt-image-1.5 백엔드
    """

    # 프리셋 경로
    PRESETS_DIR = Path(__file__).parent / "presets"

    def __init__(self, model: str = "gpt-image-1.5"):
        """
        Args:
            model: OpenAI 이미지 모델 (gpt-image-1.5, gpt-image-1 또는 dall-e-3)
        """
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model

        # 프리셋 로드
        self.characters = self._load_preset("characters.yaml")
        self.worlds = self._load_preset("worlds.yaml")
        self.cameras = self._load_preset("cameras.yaml")
        self.sets = self._load_preset("sets.yaml")

        print(f"[StoryMaker] 초기화 완료 - 모델: {model}")
        print(f"[StoryMaker] 캐릭터: {len(self.characters)}개, 세계관: {len(self.worlds)}개")

    def _load_preset(self, filename: str) -> Dict[str, Any]:
        """프리셋 YAML 파일 로드"""
        filepath = self.PRESETS_DIR / filename
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    def generate(
        self,
        prompt: str,
        output_path: str,
        size: str = "1536x1024",
        quality: str = "low"
    ) -> str:
        """
        이미지 생성 (단일)

        Args:
            prompt: 이미지 프롬프트
            output_path: 저장 경로
            size: 이미지 크기 (1536x1024 권장)
            quality: 품질 (low/medium/high)

        Returns:
            저장된 파일 경로
        """
        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )

            # base64 디코딩
            if hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                image_bytes = base64.b64decode(response.data[0].b64_json)
            elif hasattr(response.data[0], 'url') and response.data[0].url:
                # URL인 경우 다운로드
                import requests
                image_bytes = requests.get(response.data[0].url, timeout=60).content
            else:
                raise ValueError("이미지 데이터를 받지 못했습니다")

            # 16:9 크롭
            cropped = crop_to_16x9(image_bytes)

            # 저장
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(cropped)

            return output_path

        except Exception as e:
            print(f"[StoryMaker] 이미지 생성 오류: {e}")
            raise

    def generate_scene(
        self,
        scene_action: str,
        output_path: str,
        character: str = "old_monk",
        world: str = "joseon_minhwa_day",
        camera: str = "MEDIUM",
        place: str = "mountain_temple",
        quality: str = "low"
    ) -> str:
        """
        씬 기반 이미지 생성 (프리셋 사용)

        Args:
            scene_action: 씬 설명 (2문장 이내)
            output_path: 저장 경로
            character: 캐릭터 프리셋 키
            world: 세계관 프리셋 키
            camera: 카메라 프리셋 키
            place: 세트장 프리셋 키
            quality: 품질

        Returns:
            저장된 파일 경로
        """
        # 프리셋 가져오기
        char_preset = self.characters.get(character, {})
        world_preset = self.worlds.get(world, {})
        cam_preset = self.cameras.get(camera, {})
        set_preset = self.sets.get(place, {})

        # 프리셋이 없으면 간단 컴파일러 사용
        if not char_preset:
            prompt = compile_prompt_simple(
                scene_action=scene_action,
                style=world,
                character=character,
                camera=camera,
                place=place
            )
        else:
            prompt = compile_prompt(
                scene_action=scene_action,
                character=char_preset,
                world=world_preset,
                camera=cam_preset,
                place=place,
                place_props=set_preset.get('props', [])
            )

        print(f"[StoryMaker] 프롬프트: {prompt[:100]}...")
        return self.generate(prompt, output_path, quality=quality)

    def generate_from_script(
        self,
        scenes: List[Dict[str, Any]],
        output_dir: str,
        default_character: str = "old_monk",
        default_world: str = "joseon_minhwa_day",
        quality: str = "low"
    ) -> List[str]:
        """
        대본(씬 리스트)에서 이미지 일괄 생성

        Args:
            scenes: 씬 리스트 [{id, action, character, world, camera, place}, ...]
            output_dir: 출력 디렉토리
            default_character: 기본 캐릭터
            default_world: 기본 세계관
            quality: 품질

        Returns:
            생성된 이미지 경로 리스트
        """
        output_paths = []
        os.makedirs(output_dir, exist_ok=True)

        for i, scene in enumerate(scenes):
            scene_id = scene.get('id', f'S{i+1:03d}')
            action = scene.get('action', scene.get('text', ''))
            character = scene.get('character', default_character)
            world = scene.get('world', default_world)
            camera = scene.get('camera', 'MEDIUM')
            place = scene.get('place', 'temple_hall')

            output_path = os.path.join(output_dir, f"scene_{scene_id}.png")

            try:
                self.generate_scene(
                    scene_action=action,
                    output_path=output_path,
                    character=character,
                    world=world,
                    camera=camera,
                    place=place,
                    quality=quality
                )
                output_paths.append(output_path)
                print(f"[StoryMaker] {scene_id} 완료")
            except Exception as e:
                print(f"[StoryMaker] {scene_id} 실패: {e}")
                output_paths.append(None)

        return output_paths

    def get_available_presets(self) -> Dict[str, List[str]]:
        """사용 가능한 프리셋 목록 반환"""
        return {
            "characters": list(self.characters.keys()),
            "worlds": list(self.worlds.keys()),
            "cameras": list(self.cameras.keys()),
            "sets": list(self.sets.keys()),
        }
