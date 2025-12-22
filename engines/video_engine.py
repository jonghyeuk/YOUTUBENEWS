"""
영상 렌더링 엔진 - FFmpeg 기반
"""
import os
import subprocess
from typing import List, Dict

from models.types import Script, AudioSegment
from config import DURATION_SPECS, VIDEO_CONFIG


class VideoEngine:
    """FFmpeg를 사용한 영상 생성"""

    def __init__(self):
        self.resolution = VIDEO_CONFIG["resolution"]
        self.fps = VIDEO_CONFIG["fps"]
        self.codec = VIDEO_CONFIG["codec"]

    def render_scene_clips(
        self,
        scene_images: Dict[int, List[str]],
        audio_segments: List[AudioSegment],
        output_dir: str
    ) -> List[str]:
        """
        씬별 영상 클립 생성

        Args:
            scene_images: 씬별 이미지 경로 {scene_id: [img_paths]}
            audio_segments: 씬별 오디오 세그먼트
            output_dir: 출력 디렉토리

        Returns:
            씬 클립 경로 리스트
        """
        os.makedirs(output_dir, exist_ok=True)
        clip_paths = []

        for segment in audio_segments:
            scene_id = segment.scene_id
            images = scene_images.get(scene_id, [])

            if not images:
                print(f"[VideoEngine] Scene {scene_id}: No images, skipping")
                continue

            clip_path = os.path.join(output_dir, f"scene_{scene_id:02d}.mp4")

            # 이미지 2장 → 각각 절반 시간씩
            duration_per_image = segment.duration / len(images)

            # FFmpeg 명령 생성
            self._create_scene_clip(
                images=images,
                duration_per_image=duration_per_image,
                output_path=clip_path
            )

            clip_paths.append(clip_path)
            print(f"[VideoEngine] Scene {scene_id} clip: {clip_path}")

        return clip_paths

    def _create_scene_clip(
        self,
        images: List[str],
        duration_per_image: float,
        output_path: str
    ):
        """씬 클립 생성 (이미지 슬라이드쇼)"""
        # concat 리스트 파일 생성
        list_path = output_path.replace(".mp4", "_list.txt")

        with open(list_path, "w") as f:
            for img_path in images:
                f.write(f"file '{os.path.abspath(img_path)}'\n")
                f.write(f"duration {duration_per_image}\n")
            # 마지막 이미지 반복 (FFmpeg 요구사항)
            f.write(f"file '{os.path.abspath(images[-1])}'\n")

        # FFmpeg 실행
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-vf", f"scale={self.resolution}:force_original_aspect_ratio=decrease,pad={self.resolution}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", self.codec,
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            output_path
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        # 임시 파일 삭제
        os.remove(list_path)

    def concat_clips(
        self,
        clip_paths: List[str],
        audio_path: str,
        output_path: str
    ) -> str:
        """
        씬 클립들을 합치고 오디오 추가

        Args:
            clip_paths: 씬 클립 경로 리스트
            audio_path: 전체 오디오 파일 경로
            output_path: 출력 영상 경로

        Returns:
            최종 영상 경로
        """
        # concat 리스트 파일 생성
        list_path = output_path.replace(".mp4", "_concat.txt")

        with open(list_path, "w") as f:
            for clip_path in clip_paths:
                f.write(f"file '{os.path.abspath(clip_path)}'\n")

        # 비디오 합치기
        temp_video = output_path.replace(".mp4", "_temp.mp4")

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            temp_video
        ]

        subprocess.run(cmd_concat, check=True, capture_output=True)

        # 오디오 추가
        cmd_audio = [
            "ffmpeg", "-y",
            "-i", temp_video,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]

        subprocess.run(cmd_audio, check=True, capture_output=True)

        # 임시 파일 삭제
        os.remove(list_path)
        os.remove(temp_video)

        print(f"[VideoEngine] Video created: {output_path}")
        return output_path

    def burn_subtitles(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str
    ) -> str:
        """
        자막 번인

        Args:
            video_path: 입력 영상 경로
            subtitle_path: SRT 자막 경로
            output_path: 출력 영상 경로

        Returns:
            최종 영상 경로
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles={subtitle_path}:force_style='FontSize=24,FontName=NanumGothic,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'",
            "-c:a", "copy",
            output_path
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        print(f"[VideoEngine] Final video with subtitles: {output_path}")
        return output_path
