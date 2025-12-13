import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict

from models.types import Scene, ContentProfile

# Google Cloud TTS
try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False
    print("[TTSEngine] Warning: google-cloud-texttospeech not installed")


class TTSEngine:
    """
    TTS 음성 합성 엔진 - Google Cloud TTS 전용

    뉴스 영상을 위한 중립적인 나레이터 음성 생성
    - 한국어 여성 아나운서 톤
    - 객관적이고 신뢰감 있는 음성
    """

    # Google Cloud TTS 음성 옵션 (한국어)
    GOOGLE_VOICES = {
        "female_a": {"name": "ko-KR-Wavenet-A", "gender": "FEMALE", "desc": "여성 아나운서 A"},
        "female_b": {"name": "ko-KR-Wavenet-B", "gender": "FEMALE", "desc": "여성 아나운서 B"},
        "male_c": {"name": "ko-KR-Wavenet-C", "gender": "MALE", "desc": "남성 아나운서 C"},
        "male_d": {"name": "ko-KR-Wavenet-D", "gender": "MALE", "desc": "남성 아나운서 D"},
    }

    def __init__(self):
        """Google Cloud TTS 클라이언트 초기화"""
        self.client = None

        if GOOGLE_TTS_AVAILABLE:
            try:
                self.client = texttospeech.TextToSpeechClient()
                print("[TTSEngine] Google Cloud TTS initialized")
            except Exception as e:
                print(f"[TTSEngine] Google Cloud TTS init error: {e}")

    def generate_audio(
        self,
        scenes: List[Scene],
        profile: ContentProfile,
        output_dir: str
    ) -> List[Dict]:
        """
        씬별 TTS 음성 생성

        Args:
            scenes: Scene 객체 리스트
            profile: 콘텐츠 프로필
            output_dir: 출력 디렉토리

        Returns:
            오디오 파일 정보 리스트 [{path, duration}, ...]
        """
        os.makedirs(output_dir, exist_ok=True)
        audio_files = []

        # 음성 설정
        voice_config = profile.extra.get("tts_config", {})
        voice_name = voice_config.get("voice", "ko-KR-Wavenet-A")
        speech_speed = voice_config.get("speed", 1.0)

        for idx, scene in enumerate(scenes):
            narration = self._clean_narration(scene.narration)

            if not narration.strip():
                print(f"[TTSEngine] Scene {idx}: Empty narration, skipping")
                audio_files.append({"path": None, "duration": 0})
                continue

            output_path = os.path.join(output_dir, f"scene_{idx:03d}.mp3")

            try:
                duration = self._generate_google_tts(
                    text=narration,
                    output_path=output_path,
                    voice_name=voice_name,
                    speaking_rate=speech_speed
                )

                audio_files.append({
                    "path": output_path,
                    "duration": duration
                })

                print(f"[TTSEngine] Scene {idx}: {duration:.1f}s - {output_path}")

            except Exception as e:
                print(f"[TTSEngine] Scene {idx} Error: {e}")
                audio_files.append({"path": None, "duration": scene.duration_sec})

        return audio_files

    def _generate_google_tts(
        self,
        text: str,
        output_path: str,
        voice_name: str = "ko-KR-Wavenet-A",
        speaking_rate: float = 1.0
    ) -> float:
        """
        Google Cloud TTS로 음성 생성

        Args:
            text: 나레이션 텍스트
            output_path: 출력 파일 경로
            voice_name: 음성 이름
            speaking_rate: 말하기 속도 (0.25 ~ 4.0)

        Returns:
            오디오 길이 (초)
        """
        if not self.client:
            raise RuntimeError("Google Cloud TTS client not initialized")

        # 입력 텍스트 설정
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # 음성 설정
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice_name
        )

        # 오디오 설정
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=0.0  # 기본 피치
        )

        # TTS 요청
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # 파일 저장
        with open(output_path, "wb") as f:
            f.write(response.audio_content)

        # 오디오 길이 측정
        duration = self._get_audio_duration(output_path)

        return duration

    def _clean_narration(self, text: str) -> str:
        """
        나레이션 텍스트 정리

        - [DIALOGUE] 태그 제거 (있다면)
        - 특수문자 정리
        - 빈 줄 제거
        """
        if not text:
            return ""

        # [DIALOGUE]...[/DIALOGUE] 태그 제거
        text = re.sub(r'\[DIALOGUE[^\]]*\].*?\[/DIALOGUE\]', '', text, flags=re.DOTALL)

        # 특수 태그 제거
        text = re.sub(r'\[.*?\]', '', text)

        # 이모지 제거
        text = re.sub(r'[\U00010000-\U0010FFFF]', '', text)

        # 연속 공백/줄바꿈 정리
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _get_audio_duration(self, audio_path: str) -> float:
        """FFprobe로 오디오 길이 측정"""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ],
                capture_output=True,
                text=True
            )
            return float(result.stdout.strip())
        except Exception as e:
            print(f"[TTSEngine] Duration check error: {e}")
            return 0.0

    def concatenate_audio(self, audio_files: List[Dict], output_path: str) -> str:
        """
        여러 오디오 파일을 하나로 합치기

        Args:
            audio_files: [{path, duration}, ...] 리스트
            output_path: 출력 파일 경로

        Returns:
            합쳐진 오디오 파일 경로
        """
        valid_files = [f["path"] for f in audio_files if f.get("path") and os.path.exists(f["path"])]

        if not valid_files:
            print("[TTSEngine] No valid audio files to concatenate")
            return None

        if len(valid_files) == 1:
            # 파일이 하나면 복사
            import shutil
            shutil.copy(valid_files[0], output_path)
            return output_path

        # FFmpeg concat 사용
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for audio_path in valid_files:
                f.write(f"file '{audio_path}'\n")
            list_file = f.name

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", list_file, "-c", "copy", output_path
                ],
                capture_output=True,
                check=True
            )
            print(f"[TTSEngine] Concatenated {len(valid_files)} files -> {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"[TTSEngine] Concatenate error: {e}")
            return None
        finally:
            os.unlink(list_file)

        return output_path
