"""
대본 생성 엔진 - Claude API 사용
"""
import os
import json
from typing import Optional
from anthropic import Anthropic

from models.types import Script, Scene
from config import DURATION_SPECS


class ScriptEngine:
    """Claude API를 사용한 대본 생성"""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def generate(self, topic: str, duration_min: int) -> Script:
        """
        주제와 길이를 받아 대본 생성

        Args:
            topic: 영상 주제
            duration_min: 영상 길이 (5, 10, 15, 20)

        Returns:
            Script 객체
        """
        spec = DURATION_SPECS.get(duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {duration_min}분")

        num_scenes = spec["scenes"]

        prompt = self._build_prompt(topic, duration_min, num_scenes)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # JSON 파싱
        script_data = self._parse_response(content)

        # Script 객체 생성
        scenes = []
        for i, scene_data in enumerate(script_data["scenes"]):
            panel_start = i * spec["panels_per_scene"] + 1
            panel_end = panel_start + spec["panels_per_scene"]

            scene = Scene(
                scene_id=i + 1,
                title=scene_data.get("title", f"씬 {i + 1}"),
                text=scene_data["text"],
                panel_ids=list(range(panel_start, panel_end))
            )
            scenes.append(scene)

        return Script(
            title=script_data.get("title", topic),
            scenes=scenes,
            duration_min=duration_min,
            total_panels=spec["panels"]
        )

    def _build_prompt(self, topic: str, duration_min: int, num_scenes: int) -> str:
        """대본 생성 프롬프트 구성"""
        return f"""당신은 유튜브 스토리 영상 대본 작가입니다.
다음 주제로 {duration_min}분 분량의 나레이션 대본을 작성해주세요.

주제: {topic}

요구사항:
1. 총 {num_scenes}개의 씬으로 구성
2. 각 씬은 자연스럽게 연결되어야 함
3. 나레이션 형식 (대화체 X, 이야기체 O)
4. 시청자를 몰입시키는 흥미로운 전개
5. 각 씬은 약 {duration_min * 60 // num_scenes}초 분량

JSON 형식으로 응답:
```json
{{
  "title": "영상 제목",
  "scenes": [
    {{"title": "씬 제목", "text": "나레이션 텍스트..."}},
    ...
  ]
}}
```

대본만 JSON으로 출력하세요."""

    def _parse_response(self, content: str) -> dict:
        """Claude 응답에서 JSON 추출"""
        # JSON 블록 추출
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            json_str = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            json_str = content[start:end].strip()
        else:
            json_str = content.strip()

        return json.loads(json_str)
