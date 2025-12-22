"""
이미지 분할기 - 합본 이미지를 그리드 기반으로 컷 분할
"""
import os
from typing import List
from PIL import Image

from config import DURATION_SPECS


class ImageSplitter:
    """그리드 기반 합본 이미지 분할"""

    def __init__(self, margin_ratio: float = 0.02, gutter_ratio: float = 0.02):
        """
        Args:
            margin_ratio: 외곽 여백 비율 (기본 2%)
            gutter_ratio: 패널 간 거터 비율 (기본 2%)
        """
        self.margin_ratio = margin_ratio
        self.gutter_ratio = gutter_ratio

    def split(
        self,
        sheet_path: str,
        output_dir: str,
        duration_min: int
    ) -> List[str]:
        """
        합본 이미지를 컷 단위로 분할

        Args:
            sheet_path: 합본 이미지 경로
            output_dir: 출력 디렉토리
            duration_min: 영상 길이 (그리드 규격 결정용)

        Returns:
            분할된 컷 이미지 경로 리스트
        """
        spec = DURATION_SPECS.get(duration_min)
        if not spec:
            raise ValueError(f"지원하지 않는 길이: {duration_min}분")

        rows = spec["rows"]
        cols = spec["cols"]
        total_panels = spec["panels"]

        # 이미지 로드
        sheet = Image.open(sheet_path)
        width, height = sheet.size

        print(f"[ImageSplitter] Sheet size: {width}x{height}")
        print(f"[ImageSplitter] Grid: {rows}x{cols} = {total_panels} panels")

        # 여백/거터 계산
        margin_x = int(width * self.margin_ratio)
        margin_y = int(height * self.margin_ratio)
        gutter_x = int(width * self.gutter_ratio)
        gutter_y = int(height * self.gutter_ratio)

        # 실제 콘텐츠 영역
        content_width = width - (2 * margin_x) - ((cols - 1) * gutter_x)
        content_height = height - (2 * margin_y) - ((rows - 1) * gutter_y)

        # 패널 크기
        panel_width = content_width // cols
        panel_height = content_height // rows

        print(f"[ImageSplitter] Panel size: {panel_width}x{panel_height}")

        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)

        cut_paths = []
        panel_num = 1

        for row in range(rows):
            for col in range(cols):
                # 패널 좌표 계산
                x1 = margin_x + col * (panel_width + gutter_x)
                y1 = margin_y + row * (panel_height + gutter_y)
                x2 = x1 + panel_width
                y2 = y1 + panel_height

                # 크롭
                panel = sheet.crop((x1, y1, x2, y2))

                # 저장
                output_path = os.path.join(output_dir, f"cut_{panel_num:02d}.png")
                panel.save(output_path, "PNG")

                cut_paths.append(output_path)
                print(f"[ImageSplitter] Cut {panel_num}: {output_path}")

                panel_num += 1

        return cut_paths

    def assign_to_scenes(
        self,
        cut_paths: List[str],
        scenes_dir: str,
        duration_min: int
    ) -> dict:
        """
        컷을 씬별로 배분

        Args:
            cut_paths: 컷 이미지 경로 리스트
            scenes_dir: 씬 디렉토리 기본 경로
            duration_min: 영상 길이

        Returns:
            씬별 이미지 경로 딕셔너리
        """
        spec = DURATION_SPECS.get(duration_min)
        panels_per_scene = spec["panels_per_scene"]
        num_scenes = spec["scenes"]

        scene_images = {}

        for scene_id in range(1, num_scenes + 1):
            scene_dir = os.path.join(scenes_dir, f"scene_{scene_id:02d}")
            os.makedirs(scene_dir, exist_ok=True)

            start_idx = (scene_id - 1) * panels_per_scene
            end_idx = start_idx + panels_per_scene

            scene_cuts = cut_paths[start_idx:end_idx]

            # 씬 디렉토리에 복사/링크
            scene_paths = []
            for i, cut_path in enumerate(scene_cuts):
                # 심볼릭 링크 대신 경로만 저장 (효율성)
                scene_paths.append(cut_path)

            scene_images[scene_id] = scene_paths
            print(f"[ImageSplitter] Scene {scene_id}: {len(scene_paths)} images")

        return scene_images
