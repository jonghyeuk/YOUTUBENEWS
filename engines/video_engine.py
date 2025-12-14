import os
import subprocess
import tempfile
from typing import List, Dict, Optional
from pathlib import Path
from models.types import ScriptResult


def run_ffmpeg_command(command_list: List[str]) -> subprocess.CompletedProcess:
    """
    FFmpeg 명령어를 실행하고, 실패 시 상세 로그를 출력합니다.

    Args:
        command_list: FFmpeg 명령어 리스트 (예: ["ffmpeg", "-i", "input.mp4", ...])

    Returns:
        subprocess.CompletedProcess 객체

    Raises:
        subprocess.CalledProcessError: FFmpeg 실행 실패 시
    """
    print(f"🎬 [FFmpeg] 명령 실행 중...")

    try:
        result = subprocess.run(
            command_list,
            check=True,
            capture_output=True,  # stdout, stderr 캡처
            text=True,
            encoding='utf-8',  # Windows 한글 인코딩 문제 해결
            errors='replace'   # 디코딩 실패 시 대체 문자 사용
        )
        print("✅ [FFmpeg] 변환 성공!")
        return result

    except subprocess.CalledProcessError as e:
        # FFmpeg가 뱉은 실제 에러 메시지 분석
        error_message = e.stderr if e.stderr else ""
        error_lower = error_message.lower()
        exit_code = e.returncode

        print(f"\n🔴 [FFmpeg] 치명적 오류 발생! (Exit Code: {exit_code})")
        print("=" * 60)
        print(error_message[-1000:])  # 마지막 1000자 출력 (핵심 에러는 보통 끝에 있음)
        print("=" * 60)

        # ★ 에러 유형별 상세 힌트 제공 (확장됨)
        hint_shown = False

        # 1. 해상도 관련
        if "height not divisible by 2" in error_message or "width not divisible by 2" in error_message:
            print("💡 힌트: 영상 해상도(높이/너비)가 홀수입니다. 짝수로 맞춰주세요.")
            hint_shown = True

        # 2. 파일 관련
        elif "No such file" in error_message or "does not exist" in error_lower:
            print("💡 힌트: 입력 파일을 찾을 수 없습니다. 경로를 확인하세요.")
            hint_shown = True

        # 3. 필터 문법 관련
        elif "Invalid argument" in error_message or "filter" in error_lower and "error" in error_lower:
            print("💡 힌트: FFmpeg 필터 문법이 잘못되었습니다.")
            hint_shown = True

        # 4. 스트림 없음
        elif "does not contain any stream" in error_message:
            print("💡 힌트: 입력 파일이 손상되었거나 비디오/오디오 스트림이 없습니다.")
            hint_shown = True

        # 5. 코덱 관련 (VP9, HEVC, AV1 등 Pexels 비디오 호환성)
        elif "codec" in error_lower and ("not found" in error_lower or "unknown" in error_lower):
            print("💡 힌트: 필요한 코덱이 설치되지 않았습니다.")
            print("   - Pexels 비디오가 VP9/HEVC 코덱일 수 있습니다.")
            print("   - 해결: ffmpeg를 최신 버전으로 업데이트하세요.")
            hint_shown = True

        # 6. 디코더/인코더 관련
        elif "decoder" in error_lower or "encoder" in error_lower:
            print("💡 힌트: 비디오 디코더/인코더 문제입니다.")
            print("   - libx264, libvpx 등이 설치되어 있는지 확인하세요.")
            hint_shown = True

        # 7. 메모리 부족
        elif "memory" in error_lower or "cannot allocate" in error_lower:
            print("💡 힌트: 메모리가 부족합니다.")
            print("   - 더 낮은 해상도나 짧은 영상으로 시도해보세요.")
            print("   - 다른 프로그램을 종료하고 다시 시도하세요.")
            hint_shown = True

        # 8. 비디오/오디오 시간 불일치
        elif "discarding" in error_lower or "pts" in error_lower or "dts" in error_lower:
            print("💡 힌트: 비디오/오디오 타임스탬프 문제입니다.")
            print("   - 일부 프레임이 손실될 수 있습니다.")
            hint_shown = True

        # 9. 권한 관련
        elif "permission denied" in error_lower or "access" in error_lower:
            print("💡 힌트: 파일 접근 권한 문제입니다.")
            print("   - 출력 디렉토리에 쓰기 권한이 있는지 확인하세요.")
            hint_shown = True

        # 10. Windows 특수 exit code (4294967274 = -22 EINVAL)
        if exit_code == 4294967274 or exit_code == -22:
            print("💡 힌트: Windows 특수 에러 코드입니다 (EINVAL).")
            print("   - FFmpeg 필터 형식을 확인하세요 (1920x1080 → 1920:1080).")
            hint_shown = True

        # 11. 일반적인 exit code 안내
        if not hint_shown:
            print("💡 일반 힌트:")
            print("   - FFmpeg 로그를 확인하여 정확한 원인을 파악하세요.")
            print("   - 입력 파일이 손상되지 않았는지 확인하세요.")
            print("   - FFmpeg 버전을 최신으로 업데이트해보세요.")

        raise e


def get_ffmpeg_scale_filter(target_resolution: str) -> str:
    """
    타깃 해상도에 맞춰 scale + pad 필터 생성

    이 필터는:
    1. 원본 비율을 유지하면서 타깃 해상도에 맞게 축소 (scale)
    2. 남은 공간을 검은색으로 채움 (pad)
    3. 세로/가로 영상 모두 올바르게 처리

    Args:
        target_resolution: "1920x1080" 또는 "1080x1920" 형식

    Returns:
        FFmpeg -vf 옵션에 사용할 필터 문자열

    예시:
        >>> get_ffmpeg_scale_filter("1920x1080")
        "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    """
    w, h = target_resolution.split('x')
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"


# ★ Cinematic Token v0.1 - 카메라 움직임 → FFmpeg 매핑
CAMERA_MOTION_MAP = {
    # 카메라 움직임: (zoom_start, zoom_end, pan_x, pan_y)
    # zoom: 1.0 = 원본, 1.1 = 10% 확대
    # pan: 비율 (-0.02 = 왼쪽 2%)
    "static": {
        "zoom": (1.0, 1.0),
        "pan": (0, 0),
        "desc": "고정 (안정감)"
    },
    "slow_zoom_in": {
        "zoom": (1.0, 1.15),
        "pan": (0, 0),
        "desc": "줌인 (집중, 몰입)"
    },
    "slow_zoom_out": {
        "zoom": (1.15, 1.0),
        "pan": (0, 0),
        "desc": "줌아웃 (해방, 마무리)"
    },
    "slow_pan_left": {
        "zoom": (1.05, 1.05),
        "pan": (-0.02, 0),
        "desc": "왼쪽 패닝 (회상)"
    },
    "slow_pan_right": {
        "zoom": (1.05, 1.05),
        "pan": (0.02, 0),
        "desc": "오른쪽 패닝 (전환)"
    },
    "parallax_subtle": {
        "zoom": (1.0, 1.03),
        "pan": (0.01, 0),
        "desc": "입체 효과 (깊이감)"
    }
}


class VideoRenderEngine:
    """
    영상 렌더링 엔진 (FFmpeg 기반)
    - 이미지 + 오디오를 결합해서 최종 mp4 생성
    - Cinematic Token 기반 카메라 움직임 적용
    - 간단한 페이드 효과와 Ken Burns 적용
    """

    def __init__(self):
        self.ffmpeg_path = "ffmpeg"

    def render_video(self,
                    image_paths: List[str],
                    audio_files: List[Dict[str, any]],
                    script: ScriptResult,
                    output_path: str,
                    resolution: str = "1920x1080",
                    fps: int = 30,
                    video_paths: Dict[int, str] = None,
                    subtitle_path: Optional[str] = None,
                    subtitle_engine=None,
                    per_scene_subtitle: bool = False,
                    subtitle_mode: str = "full_highlight") -> str:
        """
        최종 영상 렌더링

        Args:
            image_paths: 이미지 파일 경로 리스트
            audio_files: 오디오 파일 정보 리스트
            script: 스크립트 정보
            output_path: 출력 비디오 경로
            resolution: 해상도
            fps: FPS
            video_paths: B-roll 비디오 경로 딕셔너리 {scene_idx: video_path}
            subtitle_path: 하이라이트 자막 파일 경로 (ASS 형식) - 전체 자막용
            subtitle_engine: SubtitleEngine 인스턴스 (씬별 자막용)
            per_scene_subtitle: True면 씬별로 자막 번인 후 합치기 (싱크 정확도 향상)
            subtitle_mode: 자막 모드 ("full", "highlight", "full_highlight")

        Returns:
            생성된 비디오 경로
        """
        if video_paths is None:
            video_paths = {}
        if not image_paths or not audio_files:
            print("[VideoEngine] No images or audio files to render")
            return output_path

        print(f"[VideoEngine] Starting video rendering...")
        print(f"  Images: {len(image_paths)} files")
        print(f"  Audio: {len(audio_files)} files")
        print(f"  Scenes: {len(script.scenes)} scenes")
        print(f"  Output: {output_path}")

        # 임시 디렉토리에서 작업
        temp_dir = tempfile.mkdtemp(prefix="senior_video_")
        clip_paths = []

        try:
            # 1. Scene별 클립 생성
            for idx, scene in enumerate(script.scenes):
                if idx >= len(image_paths) or idx >= len(audio_files):
                    print(f"[VideoEngine] Warning: Missing image or audio for scene {idx}")
                    continue

                # B-roll 비디오가 있는지 확인
                video_path = video_paths.get(idx)
                image_path = image_paths[idx]

                # 소스 경로 결정 (비디오 우선)
                source_path = video_path if video_path and os.path.exists(video_path) else image_path
                is_video = (source_path == video_path)

                # 소스 파일이 존재하지 않으면 스킵
                if not os.path.exists(source_path):
                    print(f"[VideoEngine] Warning: Source not found: {source_path}")
                    continue

                # 오디오 파일이 있는 경우만 처리
                audio_info = audio_files[idx]
                audio_path = audio_info.get("path")
                if not audio_path or not os.path.exists(audio_path):
                    print(f"[VideoEngine] Warning: Audio not found for scene {idx}")
                    # 오디오 없이 소스만으로 클립 생성
                    audio_path = None

                duration = audio_info.get("duration", scene.duration_sec)
                # ★ 디버그: 실제 사용되는 duration 출력
                if abs(duration - scene.duration_sec) > 1:
                    print(f"[VideoEngine] ★ Scene {idx}: using audio duration {duration:.1f}s (script: {scene.duration_sec:.0f}s)")
                clip_path = os.path.join(temp_dir, f"clip_{idx:03d}.mp4")

                source_type = "video" if is_video else "image"
                # ★ Scene에서 camera_motion 가져오기 (Shot Planner 메타데이터)
                camera_motion = getattr(scene, 'camera_motion', 'slow_zoom_in')
                print(f"[VideoEngine] Creating clip {idx+1}/{len(script.scenes)}: {scene.scene_id} ({source_type}, {camera_motion})")

                self._create_clip(
                    image_path=source_path,
                    audio_path=audio_path,
                    duration=duration,
                    output_path=clip_path,
                    resolution=resolution,
                    fps=fps,
                    is_video=is_video,
                    camera_motion=camera_motion
                )

                # ★ 씬별 자막 번인 모드
                if per_scene_subtitle and subtitle_engine and os.path.exists(clip_path):
                    # 씬별 자막 생성
                    scene_sub_path = os.path.join(temp_dir, f"sub_{idx:03d}.ass")
                    width, height = map(int, resolution.split('x'))
                    subtitle_engine.generate_single_scene_subtitle(
                        scene=scene,
                        scene_duration=duration,
                        output_path=scene_sub_path,
                        video_width=width,
                        video_height=height,
                        subtitle_mode=subtitle_mode
                    )

                    if os.path.exists(scene_sub_path):
                        # 자막 번인된 클립 생성
                        clip_with_sub = os.path.join(temp_dir, f"clip_sub_{idx:03d}.mp4")
                        self._burn_subtitles(clip_path, scene_sub_path, clip_with_sub)
                        if os.path.exists(clip_with_sub):
                            clip_paths.append(clip_with_sub)
                        else:
                            clip_paths.append(clip_path)
                    else:
                        clip_paths.append(clip_path)
                elif os.path.exists(clip_path):
                    clip_paths.append(clip_path)

            if not clip_paths:
                print("[VideoEngine] Error: No clips were created")
                return output_path

            # 2. 모든 클립을 하나로 합치기
            print(f"[VideoEngine] Concatenating {len(clip_paths)} clips...")

            # ★ 씬별 자막 모드면 이미 자막이 번인되어 있으므로 바로 concat
            if per_scene_subtitle and subtitle_engine:
                print(f"[VideoEngine] ★ 씬별 자막 모드: 자막 번인된 클립들 합치기")
                self._concat_clips(clip_paths, output_path)
            # 전체 자막이 있으면 concat 후 자막 burn-in
            elif subtitle_path and os.path.exists(subtitle_path):
                temp_concat = os.path.join(temp_dir, "concat_temp.mp4")
                self._concat_clips(clip_paths, temp_concat)

                # 3. 하이라이트 자막 burn-in
                print(f"[VideoEngine] Burning in highlight subtitles...")
                self._burn_subtitles(temp_concat, subtitle_path, output_path)
            else:
                self._concat_clips(clip_paths, output_path)

            print(f"[VideoEngine] ✓ Video rendering complete: {output_path}")

        except Exception as e:
            print(f"[VideoEngine] Error during rendering: {e}")
            raise

        finally:
            # 임시 파일 정리 (선택적)
            # shutil.rmtree(temp_dir)
            print(f"[VideoEngine] Temporary files kept in: {temp_dir}")

        return output_path

    def _create_clip(self, image_path: str, audio_path: str, duration: float,
                    output_path: str, resolution: str = "1920x1080",
                    fps: int = 30, ken_burns: bool = True, is_video: bool = False,
                    camera_motion: str = "slow_zoom_in") -> str:
        """
        단일 클립 생성 (이미지/비디오 + 오디오)

        Args:
            image_path: 이미지 또는 비디오 경로
            audio_path: 오디오 경로 (None이면 무음)
            duration: 길이 (초)
            output_path: 출력 경로
            resolution: 해상도
            fps: FPS
            ken_burns: Ken Burns 효과 (줌인/줌아웃) - 이미지용
            is_video: True면 비디오 소스, False면 이미지 소스
            camera_motion: 카메라 움직임 (Cinematic Token)
        """
        try:
            if is_video:
                # 비디오 클립 처리
                return self._create_video_clip(
                    video_path=image_path,
                    audio_path=audio_path,
                    duration=duration,
                    output_path=output_path,
                    resolution=resolution,
                    fps=fps
                )
            else:
                # 이미지 클립 처리 (Cinematic Token 적용)
                return self._create_image_clip(
                    image_path=image_path,
                    audio_path=audio_path,
                    duration=duration,
                    output_path=output_path,
                    resolution=resolution,
                    fps=fps,
                    camera_motion=camera_motion
                )

        except Exception as e:
            print(f"[VideoEngine] Error creating clip: {e}")
            raise

    def _create_image_clip(self, image_path: str, audio_path: str, duration: float,
                          output_path: str, resolution: str = "1920x1080",
                          fps: int = 30, camera_motion: str = "slow_zoom_in") -> str:
        """
        이미지 기반 클립 생성 (Cinematic Token 카메라 움직임 적용)

        Args:
            image_path: 이미지 경로
            audio_path: 오디오 경로
            duration: 길이 (초)
            output_path: 출력 경로
            resolution: 해상도
            fps: FPS
            camera_motion: 카메라 움직임 토큰 (Cinematic Token)
        """
        try:
            # FFmpeg 명령어 구성
            cmd = [
                self.ffmpeg_path,
                '-y',  # 덮어쓰기
                '-loop', '1',
                '-i', image_path,
                '-t', str(duration),
            ]

            # 오디오 추가 (있는 경우)
            if audio_path and os.path.exists(audio_path):
                cmd.extend(['-i', audio_path])

            # ★ Cinematic Token에서 카메라 설정 가져오기
            motion_config = CAMERA_MOTION_MAP.get(camera_motion, CAMERA_MOTION_MAP["slow_zoom_in"])
            zoom_start, zoom_end = motion_config["zoom"]
            pan_x, pan_y = motion_config["pan"]

            # 개선된 scale + pad 필터 사용
            base_filter = get_ffmpeg_scale_filter(resolution)

            # ★ 페이드 효과 제거 - 씬 간 연속 재생 (검은 화면 없음)
            # fade out 제거: 씬 끝에서 검은 화면으로 전환되지 않음
            total_frames = int(fps * duration)

            if camera_motion == "static":
                # 고정 샷 - 움직임 없음, 페이드 없음
                vf = f"{base_filter}"
            elif pan_x != 0 or pan_y != 0:
                # 패닝 효과 (줌 + 이동)
                # zoompan으로 줌과 패닝 동시 적용
                zoom_expr = f"'if(eq(on,1),{zoom_start},{zoom_start})'"  # 고정 줌
                # 패닝: 시작점에서 끝점으로 이동
                x_expr = f"'(iw-iw/zoom)/2 + (on/{total_frames})*iw*{pan_x}'"
                y_expr = f"'(ih-ih/zoom)/2 + (on/{total_frames})*ih*{pan_y}'"
                vf = (
                    f"{base_filter},"
                    f"zoompan=z={zoom_expr}:x={x_expr}:y={y_expr}:d={total_frames}:s={resolution}:fps={fps}"
                )
            else:
                # 줌 효과 (줌인 또는 줌아웃)
                # 줌 속도 계산: (zoom_end - zoom_start) / total_frames
                zoom_speed = (zoom_end - zoom_start) / total_frames
                zoom_expr = f"'min(zoom+{zoom_speed:.6f},{zoom_end})'" if zoom_end > zoom_start else f"'max(zoom-{abs(zoom_speed):.6f},{zoom_end})'"
                vf = (
                    f"{base_filter},"
                    f"zoompan=z={zoom_expr}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={resolution}:fps={fps}"
                )

            cmd.extend([
                '-vf', vf,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
            ])

            # 오디오 설정
            if audio_path and os.path.exists(audio_path):
                # ★ 오디오 지연 제거 (TTS 짤림 방지)
                # 페이드만 짧게 유지, adelay 사용 안 함
                audio_fade_in = 0.1
                audio_fade_out = 0.1
                fade_out_start = max(0, duration - audio_fade_out)
                cmd.extend([
                    '-af', f'afade=t=in:st=0:d={audio_fade_in},afade=t=out:st={fade_out_start}:d={audio_fade_out}',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest'  # 오디오와 비디오 중 짧은 것에 맞춤
                ])
            else:
                cmd.extend(['-an'])  # 오디오 없음

            cmd.append(output_path)

            # FFmpeg 실행 (개선된 에러 처리)
            run_ffmpeg_command(cmd)

            return output_path

        except subprocess.CalledProcessError as e:
            print(f"[VideoEngine] Image clip creation failed")
            raise
        except Exception as e:
            print(f"[VideoEngine] Error creating image clip: {e}")
            raise

    def _create_video_clip(self, video_path: str, audio_path: str, duration: float,
                          output_path: str, resolution: str = "1920x1080",
                          fps: int = 30) -> str:
        """
        비디오 클립 처리 (B-roll 비디오)

        Args:
            video_path: 비디오 경로
            audio_path: 오디오 경로
            duration: 목표 길이 (초)
            output_path: 출력 경로
            resolution: 해상도
            fps: FPS
        """
        try:
            # FFmpeg 명령어 구성
            cmd = [
                self.ffmpeg_path,
                '-y',  # 덮어쓰기
                '-i', video_path,
                '-t', str(duration),  # 비디오를 duration 길이로 자름
            ]

            # 오디오 추가 (있는 경우) - 오디오를 비디오 오디오로 교체
            if audio_path and os.path.exists(audio_path):
                cmd.extend(['-i', audio_path])

            # 비디오 필터 (리사이즈만, 페이드 없음)
            # 개선된 scale + pad 필터 사용
            base_filter = get_ffmpeg_scale_filter(resolution)

            # ★ 페이드 효과 제거 - 씬 간 연속 재생 (검은 화면 없음)
            vf = (
                f"{base_filter},"
                f"setsar=1"  # 픽셀 종횡비 설정
            )

            cmd.extend([
                '-vf', vf,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-r', str(fps),  # FPS 설정
            ])

            # 오디오 설정
            if audio_path and os.path.exists(audio_path):
                # ★ 오디오 지연 제거 (TTS 짤림 방지)
                # 페이드만 짧게 유지, adelay 사용 안 함
                audio_fade_in = 0.1
                audio_fade_out = 0.1
                audio_fade_out_start = max(0, duration - audio_fade_out)
                cmd.extend([
                    '-map', '0:v:0',  # 첫 번째 입력의 비디오
                    '-map', '1:a:0',  # 두 번째 입력의 오디오 (TTS)
                    '-af', f'afade=t=in:st=0:d={audio_fade_in},afade=t=out:st={audio_fade_out_start}:d={audio_fade_out}',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest'  # 짧은 쪽에 맞춤
                ])
            else:
                # 오디오가 없으면 비디오 오디오 사용 (또는 무음)
                cmd.extend([
                    '-c:a', 'aac',
                    '-b:a', '192k'
                ])

            cmd.append(output_path)

            # FFmpeg 실행 (개선된 에러 처리)
            run_ffmpeg_command(cmd)

            return output_path

        except subprocess.CalledProcessError as e:
            print(f"[VideoEngine] Video clip creation failed")
            raise
        except Exception as e:
            print(f"[VideoEngine] Error creating video clip: {e}")
            raise

    def _concat_clips(self, clip_paths: List[str], output_path: str) -> str:
        """
        여러 클립을 하나로 합치기 (FFmpeg concat demuxer)

        Args:
            clip_paths: 클립 경로 리스트
            output_path: 출력 경로
        """
        try:
            # concat용 텍스트 파일 생성
            concat_file = output_path + ".concat.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                for clip_path in clip_paths:
                    # FFmpeg concat 형식
                    f.write(f"file '{os.path.abspath(clip_path)}'\n")

            # FFmpeg concat 실행
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',  # re-encoding 없이 복사
                output_path
            ]

            # FFmpeg 실행 (개선된 에러 처리)
            run_ffmpeg_command(cmd)

            # concat 파일 삭제
            if os.path.exists(concat_file):
                os.remove(concat_file)

            return output_path

        except subprocess.CalledProcessError as e:
            print(f"[VideoEngine] Concat failed")
            raise
        except Exception as e:
            print(f"[VideoEngine] Error concatenating clips: {e}")
            raise

    def add_subtitles(self, video_path: str, subtitle_path: str, output_path: str) -> str:
        """
        비디오에 자막 추가 (SRT burn-in)

        Args:
            video_path: 원본 비디오 경로
            subtitle_path: 자막 파일 경로 (SRT)
            output_path: 출력 경로
        """
        try:
            cmd = [
                self.ffmpeg_path,
                '-y',
                '-i', video_path,
                '-vf', f"subtitles={subtitle_path}:force_style='FontSize=24,PrimaryColour=&HFFFFFF&'",
                '-c:a', 'copy',
                output_path
            ]

            run_ffmpeg_command(cmd)
            return output_path

        except subprocess.CalledProcessError as e:
            print(f"[VideoEngine] Error adding subtitles: {e}")
            raise

    def _burn_subtitles(self, video_path: str, subtitle_path: str, output_path: str) -> str:
        """
        시니어 모드: 하이라이트 감성 자막 burn-in (ASS 형식)

        ASS 자막은 스타일 정보(폰트 크기, 페이드, 위치 등)를 포함하므로
        force_style 없이 그대로 적용

        Args:
            video_path: 원본 비디오 경로
            subtitle_path: ASS 자막 파일 경로
            output_path: 출력 경로
        """
        try:
            # ASS 파일 경로에서 특수 문자 이스케이프 (FFmpeg 필터용)
            # Windows 경로의 백슬래시와 콜론 처리
            # 작은따옴표로 감싸서 경로 전체를 하나의 값으로 인식하게 함
            escaped_path = subtitle_path.replace('\\', '/').replace(':', '\\:')
            escaped_path = f"'{escaped_path}'"

            # ★ 프로젝트 fonts 폴더 경로 (손글씨 폰트 자동 인식)
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
            escaped_fonts_dir = fonts_dir.replace('\\', '/').replace(':', '\\:')

            cmd = [
                self.ffmpeg_path,
                '-y',
                '-i', video_path,
                '-vf', f"ass={escaped_path}:fontsdir='{escaped_fonts_dir}'",
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',
                output_path
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='ignore',
                check=True
            )

            print(f"[VideoEngine] ✓ Highlight subtitles burned in: {output_path}")
            return output_path

        except subprocess.CalledProcessError as e:
            print(f"[VideoEngine] Error burning subtitles: {e.stderr}")
            # 자막 실패 시 원본 복사
            print("[VideoEngine] Falling back to video without subtitles")
            import shutil
            shutil.copy(video_path, output_path)
            return output_path
