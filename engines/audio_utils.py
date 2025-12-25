"""
오디오 유틸리티 - 길이 측정 및 분석
"""
import subprocess
import json
from typing import Optional


def get_audio_duration(audio_path: str) -> float:
    """
    오디오 파일 길이 측정 (초 단위)

    Args:
        audio_path: 오디오 파일 경로

    Returns:
        길이 (초)
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        audio_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

    if not result.stdout:
        raise RuntimeError(f"ffprobe 오류: {result.stderr or '출력 없음'}")

    data = json.loads(result.stdout)

    return float(data["format"]["duration"])


def calculate_image_durations(
    total_audio_duration: float,
    num_images: int,
    min_duration: float = 3.0
) -> list:
    """
    오디오 길이를 이미지 개수로 균등 분배

    Args:
        total_audio_duration: 전체 오디오 길이 (초)
        num_images: 이미지 개수
        min_duration: 이미지당 최소 노출 시간

    Returns:
        각 이미지별 노출 시간 리스트
    """
    duration_per_image = total_audio_duration / num_images

    # 최소 시간 보장
    if duration_per_image < min_duration:
        duration_per_image = min_duration

    return [duration_per_image] * num_images
