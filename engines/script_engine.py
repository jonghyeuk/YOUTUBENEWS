import os
import re
import json
from anthropic import Anthropic
from models.types import ContentProfile, ScriptResult, Scene, CharacterProfile, TitleThumbnailResult


class ScriptEngine:
    """
    뉴스 시나리오 생성 엔진
    - Claude API를 사용하여 뉴스 대본 생성
    - 사건사고 뉴스: 객관적 보도 스타일
    - 카더라 뉴스: 흥미 위주 각색 스타일
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            print("[ScriptEngine] Warning: No API key provided.")

    def generate_news_script(
        self,
        news_content: str,
        news_mode: str,
        profile: ContentProfile,
        title_block: TitleThumbnailResult
    ) -> ScriptResult:
        """
        뉴스 콘텐츠 기반 스크립트 생성

        Args:
            news_content: 원본 뉴스 내용 (사용자 입력)
            news_mode: 뉴스 모드 (accident_news / rumor_news)
            profile: 콘텐츠 프로필
            title_block: 제목/썸네일 정보

        Returns:
            ScriptResult: 생성된 스크립트
        """
        if not self.client:
            print("[ScriptEngine] No API client - using dummy data")
            return self._generate_dummy_script(profile, title_block)

        # 이미지 스타일 가져오기
        image_style = os.getenv("IMAGE_STYLE", "realistic")

        # 뉴스 모드별 프롬프트 생성
        prompt = self._build_news_prompt(
            news_content=news_content,
            news_mode=news_mode,
            profile=profile,
            image_style=image_style
        )

        # Claude API 호출
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=profile.extra.get("max_tokens", 8000),
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            scenes = self._parse_response(response_text, image_style)

            print(f"[ScriptEngine] Generated {len(scenes)} scenes")

        except Exception as e:
            print(f"[ScriptEngine] API Error: {e}")
            scenes = self._generate_fallback_scenes(news_content, profile)

        return ScriptResult(
            profile=profile,
            final_title=title_block.final_title,
            scenes=scenes,
            character_profile=CharacterProfile()
        )

    def _build_news_prompt(
        self,
        news_content: str,
        news_mode: str,
        profile: ContentProfile,
        image_style: str
    ) -> str:
        """뉴스 모드별 프롬프트 생성"""

        duration_minutes = profile.duration_sec // 60
        chars_per_second = 7  # TTS 기준
        total_chars = profile.duration_sec * chars_per_second

        # 씬 개수 계산 (1분당 약 2개 씬)
        scene_count = max(3, min(15, duration_minutes * 2))

        # 이미지 스타일 지침
        if image_style == "anime":
            image_style_guide = """
이미지 스타일: 한국 웹툰/만화 스타일
- Korean webtoon illustration style
- Clean line art, expressive characters
- Dramatic composition
- 절대 실사 사진 스타일 금지
"""
        else:
            image_style_guide = """
이미지 스타일: 실사 사진 스타일
- Photorealistic style, like news photography
- Professional journalism photography
- Realistic lighting and composition
- 절대 만화/애니메이션 스타일 금지
"""

        # 뉴스 모드별 지침
        if news_mode == "accident_news":
            mode_guide = """
★ 사건사고 뉴스 모드 ★
- 객관적이고 중립적인 보도체로 작성
- 사실에 기반한 정확한 정보 전달
- 뉴스 앵커가 읽는 것처럼 작성
- 감정적 표현 최소화
- "~했습니다", "~한 것으로 전해졌습니다" 어미 사용

나레이션 톤: 뉴스 앵커처럼 정확하고 신뢰감 있게
"""
        else:  # rumor_news
            mode_guide = """
★ 카더라 뉴스 모드 ★
- 흥미롭고 자극적이지만 품위 유지
- 소문과 풍문을 기반으로 각색
- 독자의 호기심을 자극하는 서술
- 적절한 반전과 충격 요소 포함
- "~라고 합니다", "~라는 소문이 있었습니다" 어미 사용

나레이션 톤: 미스터리하고 흥미진진하게
"""

        prompt = f"""당신은 뉴스 영상 대본 작가입니다. 아래 뉴스 내용을 바탕으로 유튜브 뉴스 영상 대본을 작성해주세요.

{mode_guide}

{image_style_guide}

## 원본 뉴스 내용
{news_content}

## 요구사항
- 영상 길이: {duration_minutes}분 ({profile.duration_sec}초)
- 총 나레이션 글자수: 약 {total_chars}자
- 씬 개수: {scene_count}개
- 나레이터: 1명 (중립적인 뉴스 앵커 톤)

## 출력 형식 (JSON)
다음 JSON 형식으로만 응답해주세요:

```json
{{
  "title": "영상 제목",
  "scenes": [
    {{
      "scene_id": "scene_1",
      "title": "씬 제목",
      "narration": "나레이션 텍스트 (최소 {total_chars // scene_count}자)",
      "image_prompt": "영어로 작성된 이미지 생성 프롬프트",
      "duration_sec": {profile.duration_sec // scene_count},
      "emotion_tag": "neutral"
    }}
  ]
}}
```

## 중요 규칙
1. 나레이션은 모두 한국어로 작성
2. image_prompt는 반드시 영어로 작성
3. 각 씬의 나레이션은 최소 {total_chars // scene_count}자 이상
4. emotion_tag는 항상 "neutral" (뉴스 톤)
5. 절대 [DIALOGUE] 태그 사용 금지 - 모든 텍스트는 나레이션으로
6. JSON만 출력, 다른 설명 없이

지금 JSON 형식으로 대본을 작성해주세요:
"""

        return prompt

    def _parse_response(self, response_text: str, image_style: str) -> list:
        """Claude 응답을 Scene 객체 리스트로 파싱"""
        scenes = []

        # JSON 블록 추출
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # JSON 블록 없으면 전체 텍스트 시도
            json_text = response_text

        try:
            data = json.loads(json_text)
            scenes_data = data.get("scenes", [])

            for i, scene_data in enumerate(scenes_data):
                scene = Scene(
                    scene_id=scene_data.get("scene_id", f"scene_{i+1}"),
                    title=scene_data.get("title", f"Scene {i+1}"),
                    narration=scene_data.get("narration", ""),
                    image_prompt=self._enhance_image_prompt(
                        scene_data.get("image_prompt", ""),
                        image_style
                    ),
                    duration_sec=scene_data.get("duration_sec", 30),
                    broll_query="",
                    use_video=False,
                    highlight_keywords=self._extract_keywords(scene_data.get("narration", "")),
                    emotion_tag=scene_data.get("emotion_tag", "neutral")
                )
                scenes.append(scene)

        except json.JSONDecodeError as e:
            print(f"[ScriptEngine] JSON Parse Error: {e}")
            scenes = self._parse_markdown_fallback(response_text, image_style)

        return scenes

    def _enhance_image_prompt(self, prompt: str, image_style: str) -> str:
        """이미지 프롬프트에 스타일 추가"""
        if not prompt:
            return prompt

        if image_style == "anime":
            style_suffix = ", Korean webtoon illustration style, clean line art, professional manhwa art, NOT photorealistic"
        else:
            style_suffix = ", photorealistic news photography style, professional journalism, realistic lighting, NOT cartoon or anime style"

        return prompt + style_suffix

    def _extract_keywords(self, narration: str) -> list:
        """나레이션에서 핵심 키워드 추출"""
        if not narration:
            return []

        # 간단한 키워드 추출 (명사 위주)
        keywords = []
        # 따옴표 안의 내용
        quotes = re.findall(r'"([^"]+)"', narration)
        keywords.extend(quotes[:2])

        # 숫자 + 단위
        numbers = re.findall(r'\d+[명만원억%]', narration)
        keywords.extend(numbers[:2])

        return keywords[:5]

    def _parse_markdown_fallback(self, text: str, image_style: str) -> list:
        """JSON 파싱 실패 시 마크다운 형식으로 파싱"""
        scenes = []

        # Scene 패턴 찾기
        scene_pattern = r'(?:Scene|씬)\s*(\d+)[:\s]*(.*?)(?=(?:Scene|씬)\s*\d+|$)'
        matches = re.findall(scene_pattern, text, re.DOTALL | re.IGNORECASE)

        for i, (num, content) in enumerate(matches):
            narration = content.strip()
            scene = Scene(
                scene_id=f"scene_{num}",
                title=f"Scene {num}",
                narration=narration,
                image_prompt=self._generate_fallback_image_prompt(narration, image_style),
                duration_sec=30,
                broll_query="",
                use_video=False,
                highlight_keywords=[],
                emotion_tag="neutral"
            )
            scenes.append(scene)

        return scenes

    def _generate_fallback_image_prompt(self, narration: str, image_style: str) -> str:
        """나레이션 기반 기본 이미지 프롬프트 생성"""
        base_prompt = "News scene illustration"

        if image_style == "anime":
            return f"{base_prompt}, Korean webtoon style, clean illustration"
        else:
            return f"{base_prompt}, photorealistic news photography style"

    def _generate_fallback_scenes(self, news_content: str, profile: ContentProfile) -> list:
        """API 실패 시 기본 씬 생성"""
        duration = profile.duration_sec
        scene_count = max(3, duration // 60)

        # 뉴스 내용을 문단별로 분할
        paragraphs = [p.strip() for p in news_content.split('\n') if p.strip()]

        scenes = []
        scene_duration = duration // scene_count

        for i in range(scene_count):
            if i < len(paragraphs):
                narration = paragraphs[i]
            else:
                narration = f"뉴스 내용 {i+1}번째 부분입니다."

            scene = Scene(
                scene_id=f"scene_{i+1}",
                title=f"Scene {i+1}",
                narration=narration,
                image_prompt="News scene, professional journalism photography style",
                duration_sec=scene_duration,
                broll_query="",
                use_video=False,
                highlight_keywords=[],
                emotion_tag="neutral"
            )
            scenes.append(scene)

        return scenes

    def _generate_dummy_script(self, profile: ContentProfile, title_block: TitleThumbnailResult) -> ScriptResult:
        """더미 스크립트 생성 (테스트용)"""
        scenes = [
            Scene(
                scene_id="scene_1",
                title="뉴스 시작",
                narration="오늘의 뉴스를 전해드립니다.",
                image_prompt="News anchor desk, professional studio",
                duration_sec=profile.duration_sec,
                broll_query="",
                use_video=False,
                highlight_keywords=["뉴스"],
                emotion_tag="neutral"
            )
        ]

        return ScriptResult(
            profile=profile,
            final_title=title_block.final_title,
            scenes=scenes,
            character_profile=CharacterProfile()
        )

    # 기존 호환성을 위한 generate 메서드
    def generate(self, profile: ContentProfile, title_block: TitleThumbnailResult) -> ScriptResult:
        """기존 호환성을 위한 generate 메서드"""
        return self._generate_dummy_script(profile, title_block)
