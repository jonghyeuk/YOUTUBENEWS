"""
2.5D / Parallax 모션 엔진

정지 이미지에 깊이감 있는 모션 효과를 적용하여
영상의 몰입감을 높이는 엔진

지원 효과:
1. Ken Burns 효과 (확대/축소 + 패닝)
2. Parallax 스크롤 (전경/배경 분리 움직임)
3. 깊이 기반 모션 (Depth map 활용)

적용 대상:
- 모든 모드에서 이미지 사용 시
- 중요 장면 1-2개에만 선택적 적용 (hook, climax 등)
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MotionType(Enum):
    """모션 효과 유형"""
    NONE = "none"                    # 효과 없음 (정지 이미지)
    KEN_BURNS_ZOOM_IN = "zoom_in"    # 천천히 확대
    KEN_BURNS_ZOOM_OUT = "zoom_out"  # 천천히 축소
    KEN_BURNS_PAN_LEFT = "pan_left"  # 왼쪽으로 패닝
    KEN_BURNS_PAN_RIGHT = "pan_right" # 오른쪽으로 패닝
    PARALLAX_DEPTH = "parallax"      # 깊이감 있는 Parallax


@dataclass
class ParallaxConfig:
    """Parallax 모션 설정"""
    motion_type: MotionType = MotionType.KEN_BURNS_ZOOM_IN
    intensity: float = 0.15  # 0.0 ~ 0.3 (움직임 강도)
    duration_sec: float = 5.0  # 효과 지속 시간
    fps: int = 30


class ParallaxEngine:
    """
    2.5D / Parallax 모션 엔진

    정지 이미지에 Ken Burns 효과 또는 Parallax 모션을 적용하여
    영상 클립으로 변환

    사용법:
    1. 중요 장면 자동 감지 (hook, climax 등)
    2. 해당 이미지에 모션 효과 적용
    3. 비디오 클립으로 출력
    """

    # 중요 장면 ID (모션 효과 적용 대상)
    IMPORTANT_SCENES = {
        # 공통
        "hook": MotionType.KEN_BURNS_ZOOM_IN,      # 시작 장면 - 확대로 관심 유도
        "climax": MotionType.KEN_BURNS_ZOOM_IN,    # 클라이막스 - 극적 확대

        # 역사/드라마 모드
        "revelation": MotionType.KEN_BURNS_ZOOM_IN,  # 반전 장면
        "twist": MotionType.KEN_BURNS_ZOOM_IN,       # 반전

        # 유아 모드
        "try3": MotionType.KEN_BURNS_ZOOM_OUT,      # 성공 장면 - 확대 후 축소로 기쁨 표현
        "ending": MotionType.KEN_BURNS_ZOOM_OUT,   # 해피엔딩 - 넓은 뷰

        # 시니어 감성 모드
        "memories": MotionType.KEN_BURNS_PAN_RIGHT,  # 추억 - 천천히 패닝
        "nostalgia": MotionType.KEN_BURNS_PAN_LEFT,  # 향수 - 패닝
    }

    # 최대 적용 개수 (성능 고려)
    MAX_PARALLAX_SCENES = 2

    def __init__(self, enabled: bool = True):
        """
        Args:
            enabled: Parallax 효과 활성화 여부
        """
        self.enabled = enabled

        # ★ 동적 해상도 설정 (환경변수 기반)
        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        width, height = map(int, resolution.split('x'))
        self.width = width
        self.height = height

        if height > width:  # Shorts (세로)
            print(f"[ParallaxEngine] Mode: YouTube Shorts ({width}x{height})")
        else:  # 일반 영상 (가로)
            print(f"[ParallaxEngine] Mode: 일반 영상 ({width}x{height})")

        # FFmpeg 사용 가능 여부 확인
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """FFmpeg 설치 확인"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0:
                print("[ParallaxEngine] FFmpeg available")
            else:
                print("[ParallaxEngine] Warning: FFmpeg not working properly")
                self.enabled = False
        except FileNotFoundError:
            print("[ParallaxEngine] Warning: FFmpeg not installed. Parallax disabled.")
            self.enabled = False

    def detect_important_scenes(self, scenes: List, max_count: int = None) -> List[Tuple[int, str, MotionType]]:
        """
        중요 장면 자동 감지

        Args:
            scenes: Scene 리스트
            max_count: 최대 적용 개수 (None이면 MAX_PARALLAX_SCENES 사용)

        Returns:
            [(scene_idx, scene_id, motion_type), ...] 리스트
        """
        if max_count is None:
            max_count = self.MAX_PARALLAX_SCENES

        important = []

        for idx, scene in enumerate(scenes):
            scene_id = scene.scene_id.lower()

            # 중요 장면 ID 매칭
            for key, motion_type in self.IMPORTANT_SCENES.items():
                if key in scene_id:
                    important.append((idx, scene.safe_filename_id, motion_type))
                    break

        # 최대 개수 제한 (앞쪽 장면 우선)
        # hook은 항상 포함, 나머지 중 하나 선택
        if len(important) > max_count:
            # hook 우선 선택
            hook_scenes = [s for s in important if 'hook' in s[1].lower()]
            other_scenes = [s for s in important if 'hook' not in s[1].lower()]

            important = hook_scenes[:1] + other_scenes[:max_count - len(hook_scenes[:1])]

        if important:
            print(f"[ParallaxEngine] 중요 장면 감지: {[(s[1], s[2].value) for s in important]}")

        return important

    def apply_ken_burns(self, image_path: str, output_path: str,
                        config: ParallaxConfig) -> str:
        """
        Ken Burns 효과 적용 (확대/축소 + 패닝)

        Args:
            image_path: 입력 이미지 경로
            output_path: 출력 비디오 경로
            config: 모션 설정

        Returns:
            출력 비디오 경로
        """
        if not self.enabled:
            return None

        if not os.path.exists(image_path):
            print(f"[ParallaxEngine] 이미지 없음: {image_path}")
            return None

        # 효과별 FFmpeg zoompan 필터 설정
        # zoompan 필터: z(zoom), x/y(position), d(duration frames), s(output size)
        intensity = config.intensity
        duration_frames = int(config.duration_sec * config.fps)

        # ★ 동적 해상도 사용 (Shorts/일반 영상 자동 대응)
        output_size = f"{self.width}x{self.height}"

        if config.motion_type == MotionType.KEN_BURNS_ZOOM_IN:
            # 확대: 1.0 → 1.0 + intensity
            zoom_filter = f"zoompan=z='min(zoom+{intensity/duration_frames},1+{intensity})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration_frames}:s={output_size}:fps={config.fps}"

        elif config.motion_type == MotionType.KEN_BURNS_ZOOM_OUT:
            # 축소: 1.0 + intensity → 1.0
            zoom_filter = f"zoompan=z='if(lte(zoom,1),1+{intensity},max(1,zoom-{intensity/duration_frames}))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration_frames}:s={output_size}:fps={config.fps}"

        elif config.motion_type == MotionType.KEN_BURNS_PAN_LEFT:
            # 왼쪽 패닝: x가 오른쪽에서 왼쪽으로
            pan_distance = int(self.width * intensity)
            zoom_filter = f"zoompan=z='1.1':x='max(0,{pan_distance}-on*{pan_distance/duration_frames})':y='ih/2-(ih/zoom/2)':d={duration_frames}:s={output_size}:fps={config.fps}"

        elif config.motion_type == MotionType.KEN_BURNS_PAN_RIGHT:
            # 오른쪽 패닝: x가 왼쪽에서 오른쪽으로
            pan_distance = int(self.width * intensity)
            zoom_filter = f"zoompan=z='1.1':x='min({pan_distance},on*{pan_distance/duration_frames})':y='ih/2-(ih/zoom/2)':d={duration_frames}:s={output_size}:fps={config.fps}"

        else:
            # 기본: 약간의 확대
            zoom_filter = f"zoompan=z='min(zoom+0.0005,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={duration_frames}:s={output_size}:fps={config.fps}"

        # FFmpeg 명령 실행
        try:
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', image_path,
                '-vf', zoom_filter,
                '-t', str(config.duration_sec),
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'fast',
                '-crf', '23',
                output_path
            ]

            print(f"[ParallaxEngine] Applying {config.motion_type.value} effect...")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')

            if result.returncode == 0 and os.path.exists(output_path):
                print(f"[ParallaxEngine] ✓ Ken Burns 효과 적용 완료: {output_path}")
                return output_path
            else:
                print(f"[ParallaxEngine] ✗ FFmpeg 에러: {result.stderr[:200]}")
                return None

        except Exception as e:
            print(f"[ParallaxEngine] ✗ 효과 적용 실패: {e}")
            return None

    def process_scene_images(self, scenes: List, image_paths: List[str],
                              audio_durations: List[float],
                              output_dir: str) -> Dict[int, str]:
        """
        장면 이미지에 Parallax 효과 일괄 적용

        중요 장면만 선별하여 효과 적용

        Args:
            scenes: Scene 리스트
            image_paths: 이미지 경로 리스트
            audio_durations: 각 장면의 오디오 길이
            output_dir: 출력 디렉토리

        Returns:
            {scene_idx: video_clip_path} 딕셔너리 (효과 적용된 장면만)
        """
        if not self.enabled:
            return {}

        # 중요 장면 감지
        important_scenes = self.detect_important_scenes(scenes)

        if not important_scenes:
            print("[ParallaxEngine] 적용할 중요 장면 없음")
            return {}

        os.makedirs(output_dir, exist_ok=True)
        parallax_clips = {}

        for scene_idx, scene_id, motion_type in important_scenes:
            if scene_idx >= len(image_paths):
                continue

            image_path = image_paths[scene_idx]
            if not image_path or not os.path.exists(image_path):
                continue

            # 오디오 길이에 맞춰 효과 지속시간 설정
            duration = audio_durations[scene_idx] if scene_idx < len(audio_durations) else 5.0

            config = ParallaxConfig(
                motion_type=motion_type,
                intensity=0.12,  # 12% 움직임
                duration_sec=duration,
                fps=30
            )

            output_path = os.path.join(output_dir, f"parallax_{scene_idx:03d}_{scene_id}.mp4")

            result = self.apply_ken_burns(image_path, output_path, config)

            if result:
                parallax_clips[scene_idx] = result
                print(f"[ParallaxEngine] Scene {scene_idx} ({scene_id}): {motion_type.value} 효과 적용")

        print(f"[ParallaxEngine] 총 {len(parallax_clips)}개 장면에 Parallax 효과 적용")
        return parallax_clips


# 편의 함수
def apply_parallax_to_important_scenes(scenes: List, image_paths: List[str],
                                        audio_durations: List[float],
                                        output_dir: str,
                                        enabled: bool = True) -> Dict[int, str]:
    """
    중요 장면에 Parallax 효과 적용 (편의 함수)

    Args:
        scenes: Scene 리스트
        image_paths: 이미지 경로 리스트
        audio_durations: 오디오 길이 리스트
        output_dir: 출력 디렉토리
        enabled: 활성화 여부

    Returns:
        {scene_idx: video_clip_path} 딕셔너리
    """
    engine = ParallaxEngine(enabled=enabled)
    return engine.process_scene_images(scenes, image_paths, audio_durations, output_dir)
