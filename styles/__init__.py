"""
스타일별 프롬프트 템플릿
각 스타일은 별도 파일로 관리됩니다.
"""

from .buddhist import PROMPT as BUDDHIST_PROMPT

# 불교명상 (옵션 A - 진짜 가이드 명상)
from .buddhist_meditation import PROMPT as BUDDHIST_MEDITATION_PROMPT
from .buddhist_meditation import IMAGE_STYLE_GUIDE as BUDDHIST_MEDITATION_IMAGE_GUIDE

# 불교강의 v2 (역사 미스터리형)
from .buddhist_lecture import PROMPT as BUDDHIST_LECTURE_PROMPT
from .buddhist_lecture import WORLD_STYLE_GUIDE as BUDDHIST_LECTURE_WORLD_GUIDE
from .buddhist_lecture import EPISODE_TYPES as BUDDHIST_LECTURE_EPISODE_TYPES
from .buddhist_lecture import get_full_prompt as get_buddhist_lecture_prompt

# 스토리텔링 지역별 버전
from .storytelling_korea import PROMPT as STORYTELLING_KOREA_PROMPT
from .storytelling_korea import WORLD_STYLE_GUIDE as KOREA_WORLD_GUIDE
from .storytelling_china import PROMPT as STORYTELLING_CHINA_PROMPT
from .storytelling_china import WORLD_STYLE_GUIDE as CHINA_WORLD_GUIDE
from .storytelling_india import PROMPT as STORYTELLING_INDIA_PROMPT
from .storytelling_india import WORLD_STYLE_GUIDE as INDIA_WORLD_GUIDE

# 일본텔링 (일본어 전용)
from .storytelling_japan import PROMPT as STORYTELLING_JAPAN_PROMPT
from .storytelling_japan import WORLD_STYLE_GUIDE as JAPAN_WORLD_GUIDE

# 영어Saying전용 (English Only)
from .english_saying import PROMPT as ENGLISH_SAYING_PROMPT
from .english_saying import WORLD_STYLE_GUIDE as ENGLISH_SAYING_WORLD_GUIDE

# 스타일 프롬프트 딕셔너리
STYLE_PROMPTS = {
    "불교강의": BUDDHIST_LECTURE_PROMPT,
    "불교명상": BUDDHIST_MEDITATION_PROMPT,
    # 스토리텔링 지역별 버전
    "스토리텔링:한국불교": STORYTELLING_KOREA_PROMPT,
    "스토리텔링:중국불교": STORYTELLING_CHINA_PROMPT,
    "스토리텔링:인도불교": STORYTELLING_INDIA_PROMPT,
    # 일본텔링 (일본어 전용)
    "일본텔링": STORYTELLING_JAPAN_PROMPT,
    # 영어Saying전용 (English Only)
    "영어Saying전용": ENGLISH_SAYING_PROMPT,
}

# 스토리텔링 세계관 가이드 (StoryMaker AI용)
WORLD_STYLE_GUIDES = {
    "불교강의": BUDDHIST_LECTURE_WORLD_GUIDE,
    "불교명상": BUDDHIST_MEDITATION_IMAGE_GUIDE,
    "스토리텔링:한국불교": KOREA_WORLD_GUIDE,
    "스토리텔링:중국불교": CHINA_WORLD_GUIDE,
    "스토리텔링:인도불교": INDIA_WORLD_GUIDE,
    "일본텔링": JAPAN_WORLD_GUIDE,
    "영어Saying전용": ENGLISH_SAYING_WORLD_GUIDE,
}

__all__ = [
    "STYLE_PROMPTS",
    "WORLD_STYLE_GUIDES",
    "BUDDHIST_LECTURE_EPISODE_TYPES",
    "get_buddhist_lecture_prompt",
]
