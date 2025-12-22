"""
이미지 생성 엔진 - DALL·E 합본 이미지 생성
"""
import os
import requests
from openai import OpenAI

from models.types import Script
from config import DURATION_SPECS, DALLE_MASTER_PROMPT, IMAGE_CONFIG


class ImageEngine:
    """DALL·E를 사용한 스토리보드 합본 이미지 생성"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_sheet(
        self,
        script: Script,
        output_path: str,
        style: str = "korean webtoon"
    ) -> str:
        """
        대본 기반으로 합본 스토리보드 이미지 생성

        Args:
            script: Script 객체
            output_path: 출력 이미지 경로
            style: 그림 스타일

        Returns:
            생성된 이미지 경로
        """
        spec = DURATION_SPECS.get(script.duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {script.duration_min}분")

        # 프롬프트 구성
        prompt = self._build_prompt(script, spec, style)

        print(f"[ImageEngine] Generating {spec['panels']} panel sheet...")
        print(f"[ImageEngine] Grid: {spec['rows']}x{spec['cols']}")

        # DALL-E 3 호출
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=IMAGE_CONFIG["size"],
            quality=IMAGE_CONFIG["quality"],
            n=1
        )

        # 이미지 다운로드 및 저장
        image_url = response.data[0].url
        self._download_image(image_url, output_path)

        print(f"[ImageEngine] Sheet saved: {output_path}")
        return output_path

    def _build_prompt(self, script: Script, spec: dict, style: str) -> str:
        """DALL-E 프롬프트 구성"""
        # 비트 리스트 생성
        beats_list = script.beats_list

        # 마스터 프롬프트에 값 채우기
        prompt = DALLE_MASTER_PROMPT.format(
            rows=spec["rows"],
            cols=spec["cols"],
            panels=spec["panels"],
            beats_list=beats_list
        )

        # 스타일 추가
        prompt += f"\n\nArt style: {style}, consistent across all panels."

        return prompt

    def _download_image(self, url: str, output_path: str):
        """URL에서 이미지 다운로드"""
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(response.content)
