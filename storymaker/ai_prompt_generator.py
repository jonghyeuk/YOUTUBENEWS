"""
AI 기반 동적 이미지 프롬프트 생성기
- 대본 내용 분석 → 맥락에 맞는 이미지 프롬프트 생성
- 지역별 세계관 가이드 적용 (한국/중국/인도불교)
- 엔진별 최적화 (fal/gpt-image-1/dall-e)
"""

import os
import json
from typing import List, Dict, Optional
from anthropic import Anthropic


# ═══════════════════════════════════════════════════════════════
# 엔진별 최적화 가이드 (공식 정의)
# ═══════════════════════════════════════════════════════════════

ENGINE_OPTIMIZATION = {
    "gpt-image-1": {
        "name": "GPT-Mini Narrative Illustration",
        "max_length": 1000,
        "aspect_ratio": "1536x1024 → 16:9 crop",
        "primary_use": "빠른 러프 컷, 콘텐츠 아이디어, 배경 설명형 컷",
        "detail_level": "낮음",
        "style_hint": "단순 라인 + 최소 음영, 저해상 디테일, 스토리 톤 유지 중심",
        "avoid": "heavy realism, excessive detail",
        "prompt_structure": "style first, then scene, then character",
        "style_block": "style: mini narrative illustration, simple linework, minimal shading, low detail, story driven composition, no heavy realism, soft muted tones",
    },
    "dalle": {
        "name": "DALL-E Narrative Poster Illustration",
        "max_length": 4000,
        "aspect_ratio": "1792x1024 (native 16:9)",
        "primary_use": "표지, 썸네일, 타이틀 컷, 상징/시각 해설 이미지",
        "detail_level": "중간",
        "style_hint": "종합 일러스트레이션, 배경+인물 조화, 선명한 심볼 중심, 중간 대비",
        "avoid": "Copyrighted characters, real celebrities",
        "prompt_structure": "Descriptive narrative style, balanced composition",
        "style_block": "style: narrative poster illustration, balanced composition, medium detail, clear subject focus, moderate contrast, storytelling symbolism, clean narrative foreground",
    },
    "fal": {
        "name": "Flux (fal.ai) Buddhist Style",
        "max_length": 500,
        "aspect_ratio": "landscape_16_9 (native)",
        "primary_use": "불교 설화, 교리 설명, 성화, 사찰 벽화 스타일",
        "detail_level": "중간-높음",
        "style_hint": "짧고 집중된 프롬프트, 불화/탱화 스타일에 강함",
        "avoid": "Very long prompts, anime style",
        "prompt_structure": "Concise: style, subject, setting, mood",
        "style_block": "style: buddhist icon narrative painting, flat symbolic composition, traditional temple painting style, strong primary colors, no perspective realism, spiritual sacred mood, storytelling iconography, no anime, no modern illustration",
    },
    "imagen": {
        "name": "Google Imagine Cinematic Narrative",
        "max_length": 1000,
        "aspect_ratio": "16:9 (native)",
        "primary_use": "영상컷 감성 샘플, 씬 전환 컷, 장면 분위기 연출",
        "detail_level": "높음",
        "style_hint": "영화적 프레이밍, 카메라 깊이+공간감, 장면 전환형 조도 처리",
        "avoid": "Faces of real people, cartoonish exaggeration",
        "prompt_structure": "cinematic composition, depth of field, emotional framing",
        "style_block": "style: cinematic narrative illustration, cinematic composition, depth of field, realistic lighting, moderate detail, emotional scene framing, no cartoonish exaggeration",
    },
}

# 엔진별 용도 요약
ENGINE_USE_CASES = {
    "gpt-image-1": "시퀀스 초안, 빠른 러프",
    "dalle": "표지/썸네일, 상징적 이미지",
    "fal": "불교 도상화, 사찰 벽화 스타일",
    "imagen": "영상 컷, 카메라 연출",
}


class AIPromptGenerator:
    """
    AI 기반 이미지 프롬프트 생성기

    대본 씬을 분석하여 세계관에 맞는 이미지 프롬프트를 동적으로 생성
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        print(f"[AIPromptGenerator] 초기화 완료 - 모델: {model}")

    def generate_scene_prompts(
        self,
        scenes: List[Dict],
        world_style_guide: str,
        target_engine: str = "gpt-image-1",
        character_consistency: bool = True
    ) -> List[str]:
        """
        씬 리스트에서 이미지 프롬프트 일괄 생성

        Args:
            scenes: 씬 리스트 [{scene_id, title, text}, ...]
            world_style_guide: 세계관 스타일 가이드 (WORLD_STYLE_GUIDE)
            target_engine: 대상 이미지 엔진 (gpt-image-1, dalle, fal, imagen)
            character_consistency: 캐릭터 일관성 유지 여부

        Returns:
            이미지 프롬프트 리스트
        """
        engine_config = ENGINE_OPTIMIZATION.get(target_engine, ENGINE_OPTIMIZATION["gpt-image-1"])

        # 카메라 순환 패턴
        camera_cycle = ["wide shot", "medium shot", "close-up", "medium shot"]

        system_prompt = self._build_system_prompt(
            world_style_guide=world_style_guide,
            engine_config=engine_config,
            character_consistency=character_consistency
        )

        # 씬 정보 포맷팅
        scenes_text = self._format_scenes(scenes, camera_cycle)

        user_prompt = f"""다음 {len(scenes)}개의 씬에 대해 이미지 프롬프트를 생성해주세요.

## 씬 목록
{scenes_text}

## 출력 형식 (JSON)
각 씬에 대해 영어 프롬프트를 생성하세요:
```json
[
  {{"scene_id": 1, "prompt": "..."}},
  {{"scene_id": 2, "prompt": "..."}},
  ...
]
```

중요:
- 프롬프트는 반드시 영어로 작성
- 각 프롬프트는 {engine_config['max_length']}자 이내
- 세계관 가이드의 시각 스타일을 철저히 따르기
- 캐릭터 외모/의상을 일관되게 유지
- 지정된 카메라 샷 타입 반영"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
            ]
        )

        content = response.content[0].text
        prompts = self._parse_prompts(content, len(scenes))

        print(f"[AIPromptGenerator] {len(prompts)}개 프롬프트 생성 완료")
        return prompts

    def generate_single_prompt(
        self,
        scene_text: str,
        world_style_guide: str,
        target_engine: str = "gpt-image-1",
        camera: str = "medium shot"
    ) -> str:
        """
        단일 씬에서 이미지 프롬프트 생성

        Args:
            scene_text: 씬 텍스트 (나레이션/설명)
            world_style_guide: 세계관 스타일 가이드
            target_engine: 대상 이미지 엔진
            camera: 카메라 샷 타입

        Returns:
            이미지 프롬프트 (영어)
        """
        engine_config = ENGINE_OPTIMIZATION.get(target_engine, ENGINE_OPTIMIZATION["gpt-image-1"])

        prompt = f"""당신은 전문 영화 스토리보드 아티스트입니다.
다음 씬 설명을 읽고, 이미지 생성 AI용 프롬프트를 영어로 작성하세요.

## 세계관 스타일 가이드
{world_style_guide}

## 이미지 엔진: {engine_config['name']}
- 최대 길이: {engine_config['max_length']}자
- 권장: {engine_config['style_hint']}
- 피하기: {engine_config['avoid']}
- 구조: {engine_config['prompt_structure']}

## 씬 설명
{scene_text}

## 카메라
{camera}

위 내용을 바탕으로 이미지 프롬프트를 영어로 작성하세요.
세계관 가이드의 시각 스타일(미술 스타일, 인물 특징, 배경, 조명)을 철저히 반영하세요.
프롬프트만 출력하세요 (설명 없이):"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text.strip()

    def _build_system_prompt(
        self,
        world_style_guide: str,
        engine_config: Dict,
        character_consistency: bool
    ) -> str:
        """시스템 프롬프트 생성"""

        consistency_note = ""
        if character_consistency:
            consistency_note = """
## 캐릭터 일관성 규칙
- 모든 씬에서 동일한 주인공 외모 유지
- 의상, 헤어스타일, 체형, 나이 일관성
- 첫 씬에서 정의한 캐릭터 설명을 이후 모든 씬에 반복"""

        return f"""당신은 전문 영화 스토리보드 아티스트이자 이미지 프롬프트 엔지니어입니다.
불교 스토리텔링 영상을 위한 이미지 프롬프트를 생성합니다.

## 세계관 스타일 가이드 (반드시 준수)
{world_style_guide}

## 대상 이미지 엔진: {engine_config['name']}
- 화면비: {engine_config['aspect_ratio']}
- 최대 길이: {engine_config['max_length']}자
- 프롬프트 권장: {engine_config['style_hint']}
- 피해야 할 것: {engine_config['avoid']}
- 프롬프트 구조: {engine_config['prompt_structure']}
{consistency_note}

## 프롬프트 작성 규칙
1. 반드시 영어로 작성
2. 세계관 가이드의 "미술 스타일", "인물 특징", "공간/배경", "조명/분위기" 요소를 반영
3. "금지 요소"에 나열된 것은 절대 포함하지 않음
4. 텍스트, 워터마크, 서명 금지 명시
5. 씬의 감정과 분위기를 시각적 요소로 표현"""

    def _format_scenes(self, scenes: List[Dict], camera_cycle: List[str]) -> str:
        """씬 리스트 포맷팅"""
        formatted = []
        for i, scene in enumerate(scenes):
            scene_id = scene.get('scene_id', i + 1)
            title = scene.get('title', f'씬 {scene_id}')
            text = scene.get('text', '')[:500]  # 500자 제한
            camera = camera_cycle[i % len(camera_cycle)]

            formatted.append(f"""### 씬 {scene_id}: {title}
- 카메라: {camera}
- 내용: {text}""")

        return "\n\n".join(formatted)

    def _parse_prompts(self, content: str, expected_count: int) -> List[str]:
        """AI 응답에서 프롬프트 파싱"""
        try:
            # JSON 추출
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

            data = json.loads(json_str)

            # 프롬프트 추출
            prompts = []
            for item in data:
                if isinstance(item, dict) and 'prompt' in item:
                    prompts.append(item['prompt'])
                elif isinstance(item, str):
                    prompts.append(item)

            return prompts

        except json.JSONDecodeError as e:
            print(f"[AIPromptGenerator] JSON 파싱 실패: {e}")
            # 폴백: 줄 단위로 분리
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
            return lines[:expected_count]


def generate_prompts_for_script(
    script,
    style: str,
    target_engine: str = "gpt-image-1"
) -> List[str]:
    """
    대본 객체에서 이미지 프롬프트 생성 (편의 함수)

    Args:
        script: Script 객체
        style: 스타일 키 (스토리텔링:한국불교, 스토리텔링:중국불교, 스토리텔링:인도불교)
        target_engine: 대상 이미지 엔진

    Returns:
        이미지 프롬프트 리스트
    """
    from styles import WORLD_STYLE_GUIDES

    # 세계관 가이드 가져오기
    world_guide = WORLD_STYLE_GUIDES.get(style)
    if not world_guide:
        raise ValueError(f"지원하지 않는 스타일: {style}. 사용 가능: {list(WORLD_STYLE_GUIDES.keys())}")

    # 씬 데이터 준비
    scenes = []
    for scene in script.scenes:
        scenes.append({
            'scene_id': scene.scene_id,
            'title': scene.title,
            'text': scene.text
        })

    # AI 프롬프트 생성
    generator = AIPromptGenerator()
    prompts = generator.generate_scene_prompts(
        scenes=scenes,
        world_style_guide=world_guide,
        target_engine=target_engine,
        character_consistency=True
    )

    return prompts
