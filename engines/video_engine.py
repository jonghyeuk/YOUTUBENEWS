"""
영상 렌더링 엔진 - MoviePy 기반 (부드러운 줌 효과 + BGM 믹싱)
"""
import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor
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
        # 이미지 전환 크로스페이드 길이 (초)
        self.crossfade = float(VIDEO_CONFIG.get("crossfade_sec", 1.0))
        # 직전 render_scene_clips가 클립 꼬리에 붙인 겹침 길이 (concat_clips가 사용)
        self._clip_overlap = 0.0

    def render_scene_clips(
        self,
        scene_images: Dict[int, List[str]],
        audio_segments: List[AudioSegment],
        output_dir: str,
        use_ken_burns: bool = True,  # 하위 호환용 파라미터명 유지
        key_sentences: Optional[Dict[int, str]] = None,  # 영어Saying전용: 씬별 핵심 문장
        total_audio_duration: Optional[float] = None  # 마지막 씬을 오디오 끝까지 채우기 위함
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

        # ★ 씬 클립 길이 = 오디오 타임라인상의 씬 구간 (말 + 뒤따르는 무음)
        #   TTS는 시작 무음 1.5초 + 씬마다 2초 무음을 넣는데, 예전에는 말 길이(duration)만
        #   클립으로 만들어 영상이 오디오보다 짧았고 → 뒤로 갈수록 그림이 앞서가다
        #   마지막엔 -stream_loop로 영상이 처음부터 반복됐다.
        spans = self._scene_spans(audio_segments, total_audio_duration)

        # ★ 각 클립은 크로스페이드 겹침만큼 꼬리를 더 가진다 (concat_clips에서 겹쳐짐)
        overlap = self.crossfade if use_ken_burns else 0.0
        self._clip_overlap = overlap

        jobs = []
        prev_images = None
        image_counter = 0
        for segment, span in zip(audio_segments, spans):
            scene_id = segment.scene_id
            images = scene_images.get(scene_id, [])

            if not images:
                if not prev_images:
                    print(f"[VideoEngine] Scene {scene_id}: No images, skipping")
                    continue
                # 건너뛰면 이후 씬이 전부 앞당겨지므로, 직전 씬의 마지막 이미지로 구간을 채운다
                print(f"[VideoEngine] Scene {scene_id}: No images → 직전 이미지 유지 (싱크 보존)")
                images = prev_images[-1:]

            clip_path = os.path.join(output_dir, f"scene_{scene_id:02d}.mp4")
            jobs.append((scene_id, images, span, clip_path, image_counter))
            image_counter += len(images)
            prev_images = images

        def _render(job):
            scene_id, images, span, clip_path, effect_offset = job
            if use_ken_burns:
                self._create_scene_clip_smooth_zoom(
                    images=images,
                    scene_duration=span,
                    output_path=clip_path,
                    tail_overlap=overlap,
                    effect_offset=effect_offset
                )
            else:
                self._create_scene_clip_simple(
                    images=images,
                    duration_per_image=span / len(images),
                    output_path=clip_path
                )

            # 영어Saying전용: key_sentence 오버레이 적용
            if key_sentences and scene_id in key_sentences:
                key_text = key_sentences[scene_id]
                if key_text:
                    self._add_key_sentence_overlay(clip_path, key_text)
                    print(f"[VideoEngine] Scene {scene_id} key_sentence: '{key_text}'")

            print(f"[VideoEngine] Scene {scene_id} clip: {clip_path} ({span:.2f}s + {overlap:.1f}s)")
            return clip_path

        # 씬 클립은 서로 독립이므로 병렬 렌더 (PIL 리샘플링·ffmpeg 인코딩 모두 GIL 밖에서 동작)
        workers = max(1, min(len(jobs), VIDEO_CONFIG.get("render_workers", os.cpu_count() or 2)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            clip_paths = list(pool.map(_render, jobs))

        return clip_paths

    def _scene_spans(
        self,
        audio_segments: List[AudioSegment],
        total_audio_duration: Optional[float] = None
    ) -> List[float]:
        """씬별 화면 노출 시간 계산 (오디오 타임라인 기준).

        - 첫 씬: 0초(시작 무음 포함) ~ 다음 씬 시작
        - 중간 씬: 자기 시작 ~ 다음 씬 시작 (씬 사이 무음 포함)
        - 마지막 씬: 자기 시작 ~ 오디오 끝
        start_time이 없는 예전 프로젝트는 기존처럼 duration을 그대로 쓴다.
        """
        n = len(audio_segments)
        if n == 0:
            return []
        if not any(seg.start_time > 0 for seg in audio_segments):
            return [seg.duration for seg in audio_segments]

        spans = []
        for i, seg in enumerate(audio_segments):
            start = 0.0 if i == 0 else seg.start_time
            if i < n - 1:
                end = audio_segments[i + 1].start_time
            elif total_audio_duration and total_audio_duration > seg.end_time:
                end = total_audio_duration
            else:
                end = seg.end_time
            spans.append(max(end - start, 1.0 / self.fps))
        return spans

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
        scene_duration: float,
        output_path: str,
        tail_overlap: float = 0.0,
        effect_offset: int = 0
    ):
        """서브픽셀 줌/팬 + 이미지 간 크로스페이드로 씬 클립 생성.

        예전 방식(ffmpeg zoompan)은 크롭 좌표가 정수 픽셀로 반올림돼 천천히 확대할 때
        화면이 앞뒤로 떨렸다(측정: 300프레임 중 67프레임이 역방향 이동).
        여기서는 PIL resize(box=실수 좌표)로 매 프레임을 원본에서 직접 리샘플링하므로
        이동이 연속적이다.

        클립 길이 = scene_duration + tail_overlap.
        씬 안의 이미지들은 경계마다 self.crossfade 동안 겹쳐서(블렌드) 넘어가고,
        꼬리 tail_overlap 구간은 다음 씬과의 크로스페이드(concat_clips)에 쓰인다.
        """
        fps = self.fps
        n = len(images)
        total_frames = max(1, int(round((scene_duration + tail_overlap) * fps)))
        tail_frames = int(round(tail_overlap * fps))
        xf_frames = max(1, int(round(self.crossfade * fps)))

        # 이미지 k의 시작 프레임 (씬 길이를 균등 분배, 누적 반올림으로 드리프트 없음)
        body_frames = total_frames - tail_frames
        starts = [int(round(body_frames * k / n)) for k in range(n)]
        # 이미지 k의 노출 구간: [starts[k], 다음 이미지 시작 + 겹침) — 마지막은 클립 끝까지
        ends = [min(starts[k + 1] + xf_frames, total_frames) for k in range(n - 1)] + [total_frames]

        sources = [self._load_cover_source(p) for p in images]

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}", "-r", str(fps),
            "-i", "-",
            "-c:v", self.codec, "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            output_path.replace("\\", "/")
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for f in range(total_frames):
                frame = None
                for k in range(n):
                    if not (starts[k] <= f < ends[k]):
                        continue
                    progress = (f - starts[k]) / max(1, ends[k] - starts[k] - 1)
                    effect = self.image_effects[(effect_offset + k) % len(self.image_effects)]
                    img = self._zoom_frame(sources[k], progress, effect, effect_offset + k)
                    if frame is None:
                        frame = img
                    else:
                        # 다음 이미지가 겹치는 구간: 선형 크로스페이드
                        alpha = (f - starts[k] + 1) / (xf_frames + 1)
                        frame = PIL.Image.blend(frame, img, min(1.0, alpha))
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode("utf-8", errors="ignore")
        if proc.wait() != 0:
            print(f"[VideoEngine] FFmpeg encode error: {err}")
            raise RuntimeError(f"FFmpeg encode failed: {err}")

    def _load_cover_source(self, img_path: str):
        """이미지를 RGB로 열고, 출력 비율(16:9)을 꽉 채우는 중앙 영역 박스를 계산한다.

        원본 해상도는 그대로 두고 매 프레임 원본에서 직접 리샘플링한다 (화질 손실 최소화).
        """
        img = PIL.Image.open(img_path).convert("RGB")
        iw, ih = img.size
        target = self.width / self.height
        if iw / ih > target:
            bw, bh = ih * target, float(ih)
        else:
            bw, bh = float(iw), iw / target
        box = ((iw - bw) / 2, (ih - bh) / 2, bw, bh)  # (x0, y0, w, h)
        return img, box

    def _zoom_frame(self, source, progress: float, effect: str, index: int):
        """progress(0→1)에 해당하는 줌/팬 프레임 1장 (서브픽셀 정밀도)."""
        img, (bx, by, bw, bh) = source
        zoom_range = float(VIDEO_CONFIG.get("zoom_range", 0.18))
        p = min(1.0, max(0.0, progress))
        zoom = 1.0 + zoom_range * (p if effect == "zoom_in" else 1.0 - p)

        # 팬: 이미지마다 방향을 바꿔 단조롭지 않게 (확대된 만큼의 여유폭 안에서만 이동)
        directions = [(0.25, 0.10), (-0.25, 0.10), (0.25, -0.10), (-0.25, -0.10)]
        dx, dy = directions[index % len(directions)]
        px = 0.5 + dx * p
        py = 0.5 + dy * p

        cw, ch = bw / zoom, bh / zoom
        x0 = bx + (bw - cw) * px
        y0 = by + (bh - ch) * py
        return img.resize(
            (self.width, self.height),
            PIL.Image.BICUBIC,
            box=(x0, y0, x0 + cw, y0 + ch)
        )

    def _concat_with_crossfade(self, clip_paths: List[str], output_path: str, overlap: float):
        """클립들을 크로스페이드로 합치기 (한 번의 ffmpeg 패스).

        각 클립은 꼬리에 overlap초를 더 가지고 있다고 가정한다.
        k번째 전환 offset = 앞 클립들의 (길이 - overlap) 합 → 다음 클립의 시작이
        정확히 원래 씬 경계에 오고, 전체 길이는 overlap 한 번만큼만 길어진다.
        (예전 구현은 offset=0으로 호출해 앞 클립이 통째로 버려졌다.)
        """
        if len(clip_paths) < 2 or overlap <= 0:
            self._concat_clips_simple(clip_paths, output_path)
            return

        inputs = []
        filters = []
        offset = 0.0
        prev_label = "0:v"
        for i, clip in enumerate(clip_paths):
            inputs += ["-i", clip.replace("\\", "/")]
            if i == 0:
                continue
            offset += get_audio_duration(clip_paths[i - 1]) - overlap
            out_label = f"v{i}" if i < len(clip_paths) - 1 else "vout"
            filters.append(
                f"[{prev_label}][{i}:v]xfade=transition=fade:duration={overlap}:offset={offset:.4f}[{out_label}]"
            )
            prev_label = out_label

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[vout]",
            "-c:v", self.codec, "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            output_path.replace("\\", "/")
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] xfade error: {result.stderr[-2000:]}")
            raise RuntimeError(f"FFmpeg xfade failed: {result.stderr[-2000:]}")

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
        temp_video = output_path.replace(".mp4", "_temp.mp4").replace("\\", "/")

        # 비디오 합치기: 클립에 겹침 꼬리가 있으면 씬 사이를 크로스페이드로, 없으면 단순 이어붙이기
        # (_concat_with_crossfade는 겹침이 없으면 _concat_clips_simple로 위임)
        self._concat_with_crossfade(clip_paths, temp_video, self._clip_overlap)

        # 오디오 추가 (BGM 믹싱 여부에 따라)
        if bgm_path and os.path.exists(bgm_path):
            print(f"[VideoEngine] BGM 믹싱 시작: {os.path.basename(bgm_path)}, 볼륨: {bgm_volume}")
            self._add_audio_with_bgm(temp_video, audio_path, bgm_path, output_path, bgm_volume)
        else:
            print(f"[VideoEngine] BGM 없음 - TTS만 사용 (bgm_path={bgm_path})")
            self._add_audio_simple(temp_video, audio_path, output_path)

        # 임시 파일 삭제
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
            print(f"[VideoEngine] ❌ BGM 믹싱 오류: {result.stderr}")
            # 실패 시 BGM 없이 재시도
            print("[VideoEngine] BGM 없이 재시도...")
            self._add_audio_simple(video_path, tts_path, output_path)
        else:
            print(f"[VideoEngine] ✅ BGM 믹싱 성공!")

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

        # 자막 폰트(NanumMyeongjo 등)는 저장소 fonts/ 에 동봉 → libass가 시스템 설치 없이 찾도록 지정
        # (지정하지 않으면 시스템에 없는 폰트는 다른 폰트로 대체돼 정자체가 나오지 않았다)
        fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")
        fonts_dir_escaped = fonts_dir.replace("\\", "/")
        for char in ["'", ",", ";", "[", "]", ":"]:
            fonts_dir_escaped = fonts_dir_escaped.replace(char, f"\\{char}")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path.replace("\\", "/"),
            "-vf", f"subtitles={subtitle_path_escaped}:fontsdir={fonts_dir_escaped}:force_style='{force_style}'",
            "-c:a", "copy",
            output_path.replace("\\", "/")
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            print(f"[VideoEngine] Subtitle burn error: {result.stderr}")
            raise RuntimeError(f"Subtitle burn failed: {result.stderr}")

        print(f"[VideoEngine] Final video with subtitles: {output_path}")
        return output_path
