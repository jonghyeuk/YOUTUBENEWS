"""
스타일별 프롬프트 템플릿
각 스타일은 별도 파일로 관리됩니다.
"""

from .news import PROMPT as NEWS_PROMPT
from .info import PROMPT as INFO_PROMPT
from .storytelling import PROMPT as STORYTELLING_PROMPT
from .buddhist import PROMPT as BUDDHIST_PROMPT

# 스타일 프롬프트 딕셔너리
STYLE_PROMPTS = {
    "뉴스": NEWS_PROMPT,
    "정보": INFO_PROMPT,
    "스토리텔링": STORYTELLING_PROMPT,
    "불교명상": BUDDHIST_PROMPT,
}

__all__ = ["STYLE_PROMPTS"]
