"""
영상 렌더링 엔진 - MoviePy 기반 (부드러운 줌 효과 + BGM 믹싱)
"""
import os
import random
import subprocess
from typing import List, Dict, Optional

# Pillow 10+ 호환성 패치 (ANTIALIAS → LANCZOS)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import ImageClip, concatenate_videoclips, CompositeVideoClip
from moviepy.video.fx.resize import resize

from models.types import Script, AudioSegment
from config import DURATION_SPECS, VIDEO_CONFIG, FFMPEG_FILTERS, BGM_CONFIG
from engines.audio_utils import get_audio_duration


class VideoEngine:
    """MoviePy를 사용한 영상 생성 (부드러운 줌 효과 + BGM)"""

    def __init__(self):
        self.resolution = VIDEO_CONFIG["resolution"]
        self.width, self.height = map(int, self.resolution.split("x"))
        self.fps = VIDEO_CONFIG["fps"]
        self.codec = VIDEO_CONFIG["codec"]
        # 부드러운 이미지 효과 옵션
        self.image_effects = ["zoom_in", "zoom_out"]

    def render_scene_clips(
        self,
        scene_images: Dict[int, List[str]],
        audio_segments: List[AudioSegment],
        output_dir: str,
        use_ken_burns: bool = True  # 하위 호환용 파라미터명 유지
    ) -> List[str]:
        """
        씬별 영상 클립 생성 (부드러운 줌 효과 적용)

        Args:
            scene_images: 씬별 이미지 경로 {scene_id: [img_paths]}
            audio_segments: 씬별 오디오 세그먼트
            output_dir: 출력 디렉토리
            use_ken_burns: 이미지 효과 사용 여부

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

            # 이미지별 노출 시간
            duration_per_image = segment.duration / len(images)

            if use_ken_burns:
                self._create_scene_clip_smooth_zoom(
                    images=images,
                    duration_per_image=duration_per_image,
                    output_path=clip_path
                )
            else:
                self._create_scene_clip_simple(
                    images=images,
                    duration_per_image=duration_per_image,
                    output_path=clip_path
                )

            clip_paths.append(clip_path)
            print(f"[VideoEngine] Scene {scene_id} clip: {clip_path}")

        return clip_paths

    def _create_scene_clip_smooth_zoom(
        self,
        images: List[str],
        duration_per_image: float,
        output_path: str
    ):
        """MoviePy를 사용한 부드러운 줌 효과 씬 클립 생성 (떨림 없음)"""
        clips = []

        for i, img_path in enumerate(images):
            # 효과 선택 (줌인/줌아웃 교대)
            effect = self.image_effects[i % len(self.image_effects)]

            # 이미지 클립 생성
            clip = ImageClip(img_path).set_duration(duration_per_image)

            # 부드러운 줌 효과 적용 (부동소수점 계산으로 떨림 방지)
            if effect == "zoom_in":
                # 1.0 → 1.15 (15% 확대)
                zoom_clip = self._apply_smooth_zoom(clip, 1.0, 1.15, duration_per_image)
            else:  # zoom_out
                # 1.15 → 1.0 (축소)
                zoom_clip = self._apply_smooth_zoom(clip, 1.15, 1.0, duration_per_image)

            clips.append(zoom_clip)

        # 클립들 합치기
        final_clip = concatenate_videoclips(clips, method="compose")

        # 파일로 저장 (고품질 설정)
        final_clip.write_videofile(
            output_path,
            fps=self.fps,
            codec=self.codec,
            audio=False,
            preset='medium',
            threads=4,
            logger=None  # 로그 출력 숨김
        )

        # 메모리 해제
        final_clip.close()
        for clip in clips:
            clip.close()

    def _apply_smooth_zoom(self, clip, start_zoom, end_zoom, duration):
        """부드러운 줌 효과 적용 (부동소수점 계산으로 떨림 없음)"""
        from PIL import Image
        import numpy as np

        w, h = clip.size

        def make_frame(gf, t):
            """각 프레임에 줌 효과 적용"""
            frame = gf(t)

            # 줌 비율 계산 (시간에 따라 선형 보간)
            progress = t / duration if duration > 0 else 0
            zoom = start_zoom + (end_zoom - start_zoom) * progress

            # 새 크기 계산
            new_w = int(w * zoom)
            new_h = int(h * zoom)

            # PIL로 고품질 리사이즈 (Lanczos)
            img = Image.fromarray(frame)
            img_resized = img.resize((new_w, new_h), Image.LANCZOS)

            # 중앙 크롭 (원본 크기로)
            left = (new_w - w) // 2
            top = (new_h - h) // 2
            img_cropped = img_resized.crop((left, top, left + w, top + h))

            return np.array(img_cropped)

        # 새 클립 생성
        new_clip = clip.fl(make_frame)

        # 출력 해상도에 맞게 최종 리사이즈
        final_clip = new_clip.resize((self.width, self.height))

        return final_clip

    def _create_scene_clip_simple(
        self,
        images: List[str],
        duration_per_image: float,
        output_path: str
    ):
        """간단한 슬라이드쇼 씬 클립 생성"""
        list_path = output_path.replace(".mp4", "_list.txt")

        with open(list_path, "w", encoding="utf-8") as f:
            for img_path in images:
                # Windows 호환: 경로를 forward slash로 변환
                abs_path = os.path.abspath(img_path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {duration_per_image}\n")
            # 마지막 이미지 참조
            last_abs_path = os.path.abspath(images[-1]).replace("\\", "/")
            f.write(f"file '{last_abs_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path.replace("\\", "/"),
            "-vf", f"scale={self.resolution.replace('x', ':')}:force_original_aspect_ratio=decrease,pad={self.resolution.replace('x', ':')}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", self.codec,
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] FFmpeg stderr: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        os.remove(list_path)

    def _concat_clips_simple(self, clip_paths: List[str], output_path: str):
        """클립들을 단순 합치기"""
        if not clip_paths:
            raise ValueError("No clips to concatenate")

        list_path = output_path.replace(".mp4", "_concat.txt")

        with open(list_path, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                # Windows 호환: 경로를 forward slash로 변환
                abs_path = os.path.abspath(clip_path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path.replace("\\", "/"),
            "-c", "copy",
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")

        os.remove(list_path)

    def concat_clips(
        self,
        clip_paths: List[str],
        audio_path: str,
        output_path: str,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.15
    ) -> str:
        """
        씬 클립들을 합치고 오디오 추가 (BGM 믹싱 옵션)

        Args:
            clip_paths: 씬 클립 경로 리스트
            audio_path: TTS 오디오 파일 경로
            output_path: 출력 영상 경로
            bgm_path: BGM 파일 경로 (없으면 TTS만 사용)
            bgm_volume: BGM 볼륨 (0.0 ~ 0.5, 기본 0.15)

        Returns:
            최종 영상 경로
        """
        # 비디오 합치기
        list_path = output_path.replace(".mp4", "_concat.txt")

        with open(list_path, "w", encoding="utf-8") as f:
            for clip_path in clip_paths:
                # Windows 호환: 경로를 forward slash로 변환
                abs_path = os.path.abspath(clip_path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        temp_video = output_path.replace(".mp4", "_temp.mp4").replace("\\", "/")

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path.replace("\\", "/"),
            "-c", "copy",
            temp_video
        ]

        subprocess.run(cmd_concat, check=True, capture_output=True)

        # 오디오 추가 (BGM 믹싱 여부에 따라)
        if bgm_path and os.path.exists(bgm_path):
            self._add_audio_with_bgm(temp_video, audio_path, bgm_path, output_path, bgm_volume)
        else:
            self._add_audio_simple(temp_video, audio_path, output_path)

        # 임시 파일 삭제
        os.remove(list_path)
        os.remove(temp_video)

        print(f"[VideoEngine] Video created: {output_path}")
        return output_path

    def _add_audio_simple(self, video_path: str, audio_path: str, output_path: str):
        """TTS 오디오만 추가 (오디오 길이 기준 + 페이드아웃)"""
        # 오디오 길이 확인
        audio_duration = get_audio_duration(audio_path)
        fade_out_duration = 3  # 마지막 3초 페이드아웃

        # TTS에 페이드아웃 적용
        filter_audio = f"afade=t=out:st={max(0, audio_duration - fade_out_duration)}:d={fade_out_duration}"

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",  # 비디오 반복 (오디오보다 짧을 경우)
            "-i", video_path.replace("\\", "/"),
            "-i", audio_path.replace("\\", "/"),
            "-af", filter_audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-t", str(audio_duration),  # 오디오 길이로 제한
            output_path.replace("\\", "/")
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def _add_audio_with_bgm(
        self,
        video_path: str,
        tts_path: str,
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.15
    ):
        """TTS + BGM 믹싱하여 추가 (오디오 길이 기준 + 페이드아웃)"""
        # 오디오 길이 확인
        tts_duration = get_audio_duration(tts_path)

        # 페이드 아웃 설정
        fade_out = BGM_CONFIG.get("fade_out", 3)

        # TTS + BGM 모두 페이드아웃 적용
        filter_complex = (
            f"[1:a]afade=t=out:st={max(0, tts_duration - fade_out)}:d={fade_out}[tts];"
            f"[2:a]aloop=loop=-1:size=2e+09,volume={bgm_volume},"
            f"afade=t=out:st={max(0, tts_duration - fade_out)}:d={fade_out}[bgm];"
            f"[tts][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",  # 비디오 반복 (오디오보다 짧을 경우)
            "-i", video_path.replace("\\", "/"),
            "-i", tts_path.replace("\\", "/"),
            "-i", bgm_path.replace("\\", "/"),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-t", str(tts_duration),  # 오디오 길이로 제한
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] BGM 믹싱 오류: {result.stderr}")
            # 실패 시 BGM 없이 재시도
            print("[VideoEngine] BGM 없이 재시도...")
            self._add_audio_simple(video_path, tts_path, output_path)

    def get_random_bgm(self) -> Optional[str]:
        """BGM 폴더에서 무작위 BGM 선택"""
        bgm_folder = BGM_CONFIG.get("folder", "assets/bgm")

        if not os.path.exists(bgm_folder):
            return None

        bgm_files = [
            os.path.join(bgm_folder, f)
            for f in os.listdir(bgm_folder)
            if f.endswith((".mp3", ".wav", ".m4a"))
        ]

        if not bgm_files:
            return None

        return random.choice(bgm_files)

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
        style = FFMPEG_FILTERS["subtitle_style"]

        force_style = (
            f"FontName={style['fontname']},"
            f"FontSize={style['fontsize']},"
            f"PrimaryColour={style['primary_color']},"
            f"OutlineColour={style['outline_color']},"
            f"Outline={style['outline']},"
            f"Shadow={style['shadow']},"
            f"MarginV={style['margin_v']},"
            f"Alignment={style.get('alignment', 2)}"
        )

        # Windows 경로 호환: forward slash + 콜론 이스케이프
        subtitle_path_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path.replace("\\", "/"),
            "-vf", f"subtitles={subtitle_path_escaped}:force_style='{force_style}'",
            "-c:a", "copy",
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] Subtitle burn error: {result.stderr}")
            raise RuntimeError(f"Subtitle burn failed: {result.stderr}")

        print(f"[VideoEngine] Final video with subtitles: {output_path}")
        return output_path
