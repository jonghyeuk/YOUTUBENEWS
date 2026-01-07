"""
스타일별 프롬프트 템플릿
각 스타일은 별도 파일로 관리됩니다.
"""

from .news import PROMPT as NEWS_PROMPT
from .info import PROMPT as INFO_PROMPT
from .buddhist import PROMPT as BUDDHIST_PROMPT

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

# 스타일 프롬프트 딕셔너리
STYLE_PROMPTS = {
    "뉴스": NEWS_PROMPT,
    "정보": INFO_PROMPT,
    "불교명상": BUDDHIST_PROMPT,
    # 스토리텔링 지역별 버전
    "스토리텔링:한국불교": STORYTELLING_KOREA_PROMPT,
    "스토리텔링:중국불교": STORYTELLING_CHINA_PROMPT,
    "스토리텔링:인도불교": STORYTELLING_INDIA_PROMPT,
    # 일본텔링 (일본어 전용)
    "일본텔링": STORYTELLING_JAPAN_PROMPT,
}

# 스토리텔링 세계관 가이드 (StoryMaker AI용)
WORLD_STYLE_GUIDES = {
    "스토리텔링:한국불교": KOREA_WORLD_GUIDE,
    "스토리텔링:중국불교": CHINA_WORLD_GUIDE,
    "스토리텔링:인도불교": INDIA_WORLD_GUIDE,
    "일본텔링": JAPAN_WORLD_GUIDE,
}

__all__ = ["STYLE_PROMPTS", "WORLD_STYLE_GUIDES"]
