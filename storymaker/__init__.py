"""
StoryMaker - 스토리텔링 전용 이미지 공장
같은 배우 · 같은 세계관 · 같은 연출로 스토리 이미지를 자동 생산

지원 스타일:
- 스토리텔링:한국불교 - 민화풍, 조선시대, 산사
- 스토리텔링:중국불교 - 수묵화풍, 당송명청, 소림사
- 스토리텔링:인도불교 - 간다라 미술, 붓다 시대, 녹야원
"""

from .engine import StoryMakerEngine
from .compiler import compile_prompt, compile_hybrid_prompt
from .postprocess import crop_to_16x9
from .ai_prompt_generator import AIPromptGenerator, generate_prompts_for_script

__all__ = [
    "StoryMakerEngine",
    "compile_prompt",
    "compile_hybrid_prompt",
    "crop_to_16x9",
    "AIPromptGenerator",
    "generate_prompts_for_script",
]
