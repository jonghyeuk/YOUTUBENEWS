"""
데이터 타입 정의
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class DurationOption(Enum):
    MIN_5 = 5
    MIN_10 = 10
    MIN_15 = 15
    MIN_20 = 20


class TTSEngine(Enum):
    WAVENET = "wavenet"
    ELEVENLABS = "elevenlabs"


@dataclass
class Scene:
    """씬 정보"""
    scene_id: int
    title: str
    text: str  # 나레이션 텍스트

    # 이미지 배분 (균등 X, 감정/중요도 기반)
    image_count: int = 1  # 이 씬에 필요한 이미지 개수
    importance: int = 1   # 중요도 (1~5, 5가 가장 중요)

    # 이미지 프롬프트들 (image_count만큼)
    image_prompts: List[str] = field(default_factory=list)
    image_prompt: str = ""  # 단일 프롬프트 (호환성)

    # 시간 정보
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0  # 씬 길이 (초)

    # 생성된 이미지 경로들
    panel_ids: List[int] = field(default_factory=list)
    image_paths: List[str] = field(default_factory=list)

    # 영어Saying전용: 화면 중앙 표시용 핵심 문장
    key_sentence: str = ""


@dataclass
class Script:
    """대본 전체"""
    title: str
    scenes: List[Scene]
    duration_min: int
    total_panels: int

    @property
    def full_text(self) -> str:
        return "\n\n".join([s.text for s in self.scenes])

    @property
    def beats_list(self) -> str:
        """DALL-E 프롬프트용 비트 리스트"""
        beats = []
        beat_num = 1
        for scene in self.scenes:
            # 씬당 2개 비트로 분할
            sentences = scene.text.split('. ')
            mid = len(sentences) // 2
            beat1 = '. '.join(sentences[:mid]) if mid > 0 else sentences[0]
            beat2 = '. '.join(sentences[mid:]) if mid < len(sentences) else sentences[-1]

            beats.append(f"{beat_num}. {beat1.strip()}")
            beat_num += 1
            beats.append(f"{beat_num}. {beat2.strip()}")
            beat_num += 1

        return "\n".join(beats)


@dataclass
class AudioSegment:
    """오디오 세그먼트"""
    scene_id: int
    start_time: float
    end_time: float
    duration: float
    file_path: Optional[str] = None


@dataclass
class Project:
    """프로젝트 전체 상태"""
    project_id: str
    title: str
    duration_min: int
    topic: str

    # 생성된 자산들
    script: Optional[Script] = None
    audio_path: Optional[str] = None
    audio_segments: List[AudioSegment] = field(default_factory=list)
    sheet_image_path: Optional[str] = None
    cut_paths: List[str] = field(default_factory=list)
    subtitle_path: Optional[str] = None
    video_path: Optional[str] = None
    final_video_path: Optional[str] = None

    # 상태
    current_step: int = 0
    status: str = "initialized"
