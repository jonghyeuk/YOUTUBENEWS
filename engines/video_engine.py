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
        use_ken_burns: bool = True,  # 하위 호환용 파라미터명 유지
        key_sentences: Optional[Dict[int, str]] = None  # 영어Saying전용: 씬별 핵심 문장
    ) -> List[str]:
        """
        씬별 영상 클립 생성 (부드러운 줌 효과 적용)

        Args:
            scene_images: 씬별 이미지 경로 {scene_id: [img_paths]}
            audio_segments: 씬별 오디오 세그먼트
            output_dir: 출력 디렉토리
            use_ken_burns: 이미지 효과 사용 여부
            key_sentences: 씬별 핵심 문장 (영어Saying전용) {scene_id: "text"}

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

            # 영어Saying전용: key_sentence 오버레이 적용
            if key_sentences and scene_id in key_sentences:
                key_text = key_sentences[scene_id]
                if key_text:
                    self._add_key_sentence_overlay(clip_path, key_text)
                    print(f"[VideoEngine] Scene {scene_id} key_sentence: '{key_text}'")

            clip_paths.append(clip_path)
            print(f"[VideoEngine] Scene {scene_id} clip: {clip_path}")

        return clip_paths

    def _add_key_sentence_overlay(self, video_path: str, text: str):
        """
        영상에 핵심 문장 오버레이 (영어Saying전용)
        - 화면 중앙에 큰 글씨 (더 크고 굵게)
        - 흰색 텍스트 + 검정 외곽선 (썸네일 스타일)
        - 천천히 부드럽게 나타났다 사라짐 (1회만, 반복 없음)
        """
        temp_output = video_path.replace(".mp4", "_keysent.mp4")

        # FFmpeg drawtext 필터로 텍스트 오버레이
        # 폰트 설정 (ExtraBold/Black 우선)
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-ExtraBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        ]
        font_path = next((f for f in font_candidates if os.path.exists(f)), font_candidates[0])

        # 텍스트 이스케이프 (FFmpeg용)
        escaped_text = text.replace("'", "'\\''").replace(":", "\\:")

        # 천천히 나타났다 사라지는 효과 (1회만, 반복 없음)
        # 1.0-3.0초: fade in (2초간 천천히 나타남)
        # 3.0-7.0초: 유지 (4초간 완전히 보임)
        # 7.0-9.0초: fade out (2초간 천천히 사라짐)
        fade_expr = (
            "if(lt(t,1),0,"                           # 0-1초: 안 보임
            "if(lt(t,3),(t-1)/2,"                     # 1-3초: fade in (0→1, 2초간)
            "if(lt(t,7),1,"                           # 3-7초: 유지 (4초간)
            "if(lt(t,9),(9-t)/2,"                     # 7-9초: fade out (1→0, 2초간)
            "0))))"                                    # 9초 이후: 안 보임
        )

        # drawtext 필터: 중앙 배치, 더 크고 굵게, 천천히 fade
        drawtext_filter = (
            f"drawtext=text='{escaped_text}'"
            f":fontfile={font_path}"
            f":fontsize=100"
            f":fontcolor=white"
            f":borderw=8"
            f":bordercolor=black"
            f":shadowcolor=black@0.5"
            f":shadowx=3:shadowy=3"
            f":x=(w-text_w)/2"
            f":y=(h-text_h)/2"
            f":alpha='{fade_expr}'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path.replace("\\", "/"),
            "-vf", drawtext_filter,
            "-c:a", "copy",
            temp_output.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            # 원본 교체
            os.replace(temp_output, video_path)
            print(f"[VideoEngine] Key sentence overlay applied (slow fade, once)")
        else:
            print(f"[VideoEngine] Key sentence overlay failed: {result.stderr[:200]}")
            # 실패해도 원본 유지 (오류 무시)

    def _create_scene_clip_smooth_zoom(
        self,
        images: List[str],
        duration_per_image: float,
        output_path: str
    ):
        """FFmpeg zoompan을 사용한 빠른 줌 효과 씬 클립 생성"""
        temp_clips = []

        for i, img_path in enumerate(images):
            # 효과 선택 (줌인/줌아웃 교대)
            effect = self.image_effects[i % len(self.image_effects)]
            temp_clip = output_path.replace(".mp4", f"_temp_{i:02d}.mp4")

            # FFmpeg zoompan 필터로 줌 효과 생성
            self._create_zoom_clip_ffmpeg(
                img_path=img_path,
                duration=duration_per_image,
                effect=effect,
                output_path=temp_clip
            )
            temp_clips.append(temp_clip)

        # 클립들 합치기 (크로스페이드)
        if len(temp_clips) == 1:
            # Windows 호환: 대상 파일이 이미 있으면 삭제 후 rename
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_clips[0], output_path)
        else:
            self._concat_with_crossfade(temp_clips, output_path)
            # 임시 파일 삭제
            for tc in temp_clips:
                if os.path.exists(tc):
                    os.remove(tc)

    def _create_zoom_clip_ffmpeg(
        self,
        img_path: str,
        duration: float,
        effect: str,
        output_path: str
    ):
        """
        FFmpeg zoompan 필터로 단일 이미지 줌 클립 생성
        - Cinematic Arc Path: 곡선 경로로 이동하며 입체적인 카메라 워킹
        - 시작=끝 위치 일치로 씬 전환 시 끊김 없음
        """
        # 총 프레임 수
        total_frames = int(duration * self.fps)

        # ========================================
        # Cinematic Arc Path 로직
        # - 카메라가 곡선(Arc)을 그리며 이동
        # - sin 함수로 시작/끝에서 가감속 내장
        # - 영상 시작=끝 위치 일치로 루프 최적화
        # ========================================

        # 줌: 1.05 ~ 1.12 (부드러운 확대/축소)
        # sin(PI*on/total) = 0→1→0 이므로 1.05에서 시작해 1.12까지 갔다가 1.05로 복귀
        zoom_expr = f"1.05+0.07*sin(PI*on/{total_frames})"

        # 기본 중앙 위치
        center_x = f"(iw/2-(iw/zoom/2))"
        center_y = f"(ih/2-(ih/zoom/2))"

        # ========================================
        # X축 (Pan): 좌우 이동 (0 → Max → 0)
        # - sin(PI*on/total): 왼쪽→오른쪽→왼쪽 왕복
        # - 계수 0.08 = 전체 여유폭의 8% 이동
        # ========================================
        pan_x = f"(iw-ow)*sin(PI*on/{total_frames})*0.08"

        # ========================================
        # Y축 (Tilt): 상하 곡선 (높낮이 변화로 곡선미 추가)
        # - sin(2*PI*on/total): X의 2배 주기로 위아래 굴곡
        # - 계수 0.04 = 전체 여유높이의 4%
        # ========================================
        tilt_y = f"(ih-oh)*sin(2*PI*on/{total_frames})*0.04"

        # 최종 좌표 = 중앙 + Pan(좌우) + Tilt(상하)
        x_expr = f"{center_x}+{pan_x}"
        y_expr = f"{center_y}+{tilt_y}"

        # zoompan 필터 (bicubic 보간, 부드러운 줌)
        filter_complex = (
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
            f"d={total_frames}:s={self.width}x{self.height}:fps={self.fps},"
            f"fade=t=in:st=0:d=0.3,fade=t=out:st={duration-0.3}:d=0.3"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img_path.replace("\\", "/"),
            "-vf", filter_complex,
            "-c:v", self.codec,
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-preset", "fast",  # 빠른 인코딩
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] FFmpeg zoompan error: {result.stderr}")
            raise RuntimeError(f"FFmpeg zoompan failed: {result.stderr}")

    def _concat_with_crossfade(self, clip_paths: List[str], output_path: str):
        """클립들을 크로스페이드로 합치기"""
        if len(clip_paths) < 2:
            return

        # 첫 번째 클립부터 시작
        current = clip_paths[0]
        crossfade_duration = 0.3  # 0.3초 크로스페이드

        for i, next_clip in enumerate(clip_paths[1:], 1):
            temp_output = output_path.replace(".mp4", f"_xfade_{i}.mp4")

            # xfade 필터로 크로스페이드
            cmd = [
                "ffmpeg", "-y",
                "-i", current.replace("\\", "/"),
                "-i", next_clip.replace("\\", "/"),
                "-filter_complex", f"xfade=transition=fade:duration={crossfade_duration}:offset=0",
                "-c:v", self.codec,
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                temp_output.replace("\\", "/")
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                # 크로스페이드 실패 시 단순 concat
                print(f"[VideoEngine] xfade failed, using simple concat")
                self._concat_clips_simple(clip_paths, output_path)
                return

            # 이전 임시 파일 삭제
            if i > 1 and os.path.exists(current):
                os.remove(current)

            current = temp_output

        # 최종 파일 이동 (Windows 호환: 대상 파일이 이미 있으면 삭제)
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(current, output_path)

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
            f"MarginL={style.get('margin_l', 80)},"
            f"MarginR={style.get('margin_r', 80)},"
            f"Alignment={style.get('alignment', 2)}"
        )

        # Windows 경로 호환: FFmpeg subtitles 필터용 이스케이프
        # 콤마, 콜론, 대괄호, 세미콜론, 작은따옴표 등 이스케이프 필요
        subtitle_path_escaped = subtitle_path.replace("\\", "/")
        # FFmpeg 필터 특수문자 이스케이프 (순서 중요: 백슬래시 먼저)
        for char in ["'", ",", ";", "[", "]", ":"]:
            subtitle_path_escaped = subtitle_path_escaped.replace(char, f"\\{char}")

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
