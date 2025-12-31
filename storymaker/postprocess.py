"""
후처리 모듈 - 16:9 크롭, 리사이즈, 압축
OpenAI는 1536x1024 생성 → 16:9(1536x864)로 크롭
"""

import io
from PIL import Image
from typing import Tuple


def crop_to_16x9(image_bytes: bytes) -> bytes:
    """
    이미지를 16:9 비율로 크롭

    Args:
        image_bytes: 원본 이미지 바이트

    Returns:
        크롭된 이미지 바이트 (PNG)
    """
    im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = im.size

    # 16:9 비율 계산
    target_h = int(w * 9 / 16)

    if target_h > h:
        # 세로가 더 짧으면 가로를 줄임
        target_w = int(h * 16 / 9)
        left = (w - target_w) // 2
        im = im.crop((left, 0, left + target_w, h))
    else:
        # 일반적인 경우: 위아래를 자름
        top = (h - target_h) // 2
        im = im.crop((0, top, w, top + target_h))

    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def resize_image(image_bytes: bytes, size: Tuple[int, int] = (1920, 1080)) -> bytes:
    """
    이미지 리사이즈

    Args:
        image_bytes: 원본 이미지 바이트
        size: 목표 크기 (width, height)

    Returns:
        리사이즈된 이미지 바이트 (PNG)
    """
    im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    im = im.resize(size, Image.Resampling.LANCZOS)

    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def compress_image(image_bytes: bytes, quality: int = 85) -> bytes:
    """
    이미지 압축 (JPEG)

    Args:
        image_bytes: 원본 이미지 바이트
        quality: JPEG 품질 (1-100)

    Returns:
        압축된 이미지 바이트 (JPEG)
    """
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    out = io.BytesIO()
    im.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def process_for_video(image_bytes: bytes, target_size: Tuple[int, int] = (1920, 1080)) -> bytes:
    """
    영상용 이미지 처리 파이프라인
    1. 16:9 크롭
    2. 목표 크기로 리사이즈
    3. PNG로 저장 (무손실)

    Args:
        image_bytes: 원본 이미지 바이트
        target_size: 목표 크기

    Returns:
        처리된 이미지 바이트 (PNG)
    """
    # 1. 16:9 크롭
    cropped = crop_to_16x9(image_bytes)

    # 2. 리사이즈
    resized = resize_image(cropped, target_size)

    return resized
