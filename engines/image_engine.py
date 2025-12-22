"""
이미지 생성 엔진 - DALL·E 합본 이미지 생성
정서 전환점 기반 상세 프롬프트 지원
"""
import os
import requests
from typing import Optional, List
from openai import OpenAI

from models.types import Script
from config import DURATION_SPECS, DALLE_MASTER_PROMPT, IMAGE_CONFIG, IMAGE_STYLE_GUIDES


class ImageEngine:
    """DALL·E를 사용한 스토리보드 합본 이미지 생성"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_sheet(
        self,
        script: Script,
        output_path: str,
        style: str = "cinematic",
        beats_list: Optional[str] = None
    ) -> str:
        """
        대본 기반으로 합본 스토리보드 이미지 생성

        Args:
            script: Script 객체
            output_path: 출력 이미지 경로
            style: 그림 스타일 (cinematic, oil_painting, watercolor, anime, webtoon, realistic)
            beats_list: 정서 전환점 기반 비트 리스트 (없으면 대본에서 자동 생성)

        Returns:
            생성된 이미지 경로
        """
        spec = DURATION_SPECS.get(script.duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {script.duration_min}분")

        # 프롬프트 구성 (정서 전환점 비트 리스트 우선 사용)
        prompt = self._build_prompt(script, spec, style, beats_list)

        print(f"[ImageEngine] Generating {spec['panels']} panel sheet...")
        print(f"[ImageEngine] Grid: {spec['rows']}x{spec['cols']}")
        print(f"[ImageEngine] Style: {style}")

        # DALL-E 3 호출
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=IMAGE_CONFIG["size_landscape"],
            quality=IMAGE_CONFIG["quality"],
            style=IMAGE_CONFIG["style"],
            n=1
        )

        # 이미지 다운로드 및 저장
        image_url = response.data[0].url
        self._download_image(image_url, output_path)

        print(f"[ImageEngine] Sheet saved: {output_path}")
        return output_path

    def generate_sheet_with_transitions(
        self,
        script: Script,
        output_path: str,
        transition_descriptions: List[str],
        style: str = "cinematic"
    ) -> str:
        """
        정서 전환점 설명 리스트로 스토리보드 생성

        Args:
            script: Script 객체
            output_path: 출력 이미지 경로
            transition_descriptions: 각 패널의 영어 설명 리스트
            style: 그림 스타일

        Returns:
            생성된 이미지 경로
        """
        spec = DURATION_SPECS.get(script.duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {script.duration_min}분")

        # 비트 리스트 생성
        beats = []
        for i, desc in enumerate(transition_descriptions, 1):
            beats.append(f"{i}. {desc}")
        beats_list = "\n".join(beats)

        return self.generate_sheet(
            script=script,
            output_path=output_path,
            style=style,
            beats_list=beats_list
        )

    def _build_prompt(
        self,
        script: Script,
        spec: dict,
        style: str,
        beats_list: Optional[str] = None
    ) -> str:
        """DALL-E 프롬프트 구성"""

        # 비트 리스트: 제공된 것 사용 또는 대본에서 생성
        if beats_list is None:
            beats_list = self._generate_beats_from_script(script, spec["panels"])

        # 스타일 가이드 가져오기
        style_guide = IMAGE_STYLE_GUIDES.get(style, IMAGE_STYLE_GUIDES["cinematic"])

        # 마스터 프롬프트에 값 채우기
        prompt = DALLE_MASTER_PROMPT.format(
            rows=spec["rows"],
            cols=spec["cols"],
            panels=spec["panels"],
            beats_list=beats_list
        )

        # 스타일 추가
        prompt += f"\n\nArt style: {style_guide}"
        prompt += "\nMaintain consistent world-building, character appearance, and color palette across ALL panels."

        return prompt

    def _generate_beats_from_script(self, script: Script, num_panels: int) -> str:
        """
        대본에서 비트 리스트 생성 (폴백용)
        각 씬의 내용을 기반으로 패널 설명 생성
        """
        beats = []
        panels_per_scene = max(1, num_panels // len(script.scenes))

        beat_num = 1
        for scene in script.scenes:
            # 씬 텍스트를 문장으로 분할
            sentences = [s.strip() for s in scene.text.split('.') if s.strip()]

            # 씬당 할당된 패널 수만큼 비트 생성
            for i in range(panels_per_scene):
                if beat_num > num_panels:
                    break

                # 문장 선택 (순환)
                sentence_idx = i % len(sentences) if sentences else 0
                sentence = sentences[sentence_idx] if sentences else scene.title

                # 영어 설명 생성 (간단한 변환)
                # 실제로는 EmotionalTransitionEngine에서 생성된 영어 설명 사용
                beat_desc = f"Scene from story: {sentence[:100]}"
                beats.append(f"{beat_num}. {beat_desc}")
                beat_num += 1

        # 남은 패널 채우기
        while len(beats) < num_panels:
            beats.append(f"{len(beats)+1}. Continuation of the story scene")

        return "\n".join(beats[:num_panels])

    def _download_image(self, url: str, output_path: str):
        """URL에서 이미지 다운로드"""
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(response.content)
