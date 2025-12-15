import os
import re
import subprocess
import tempfile
import requests
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
    TTS 음성 합성 엔진 - Google Cloud TTS + ElevenLabs

    뉴스 영상을 위한 중립적인 나레이터 음성 생성

    ★ Google Cloud TTS (7종)
    - Wavenet: 자연스러운 음성 (4종)
    - Neural2: 최신 고품질 음성 (3종)

    ★ ElevenLabs (다국어 지원, 고품질)
    - 한국어 포함 다국어 지원
    - 자연스럽고 감정 표현 우수
    """

    # Google Cloud TTS 음성 옵션 (한국어 - Wavenet + Neural2만)
    GOOGLE_VOICES = {
        # Wavenet (4종)
        "wavenet_a": {"name": "ko-KR-Wavenet-A", "gender": "FEMALE", "desc": "여성 Wavenet A"},
        "wavenet_b": {"name": "ko-KR-Wavenet-B", "gender": "FEMALE", "desc": "여성 Wavenet B"},
        "wavenet_c": {"name": "ko-KR-Wavenet-C", "gender": "MALE", "desc": "남성 Wavenet C"},
        "wavenet_d": {"name": "ko-KR-Wavenet-D", "gender": "MALE", "desc": "남성 Wavenet D"},
        # Neural2 (3종)
        "neural2_a": {"name": "ko-KR-Neural2-A", "gender": "FEMALE", "desc": "여성 Neural2 A"},
        "neural2_b": {"name": "ko-KR-Neural2-B", "gender": "FEMALE", "desc": "여성 Neural2 B"},
        "neural2_c": {"name": "ko-KR-Neural2-C", "gender": "MALE", "desc": "남성 Neural2 C"},
    }

    # ElevenLabs 음성 옵션
    # voice_id는 ElevenLabs 대시보드에서 확인 가능
    ELEVENLABS_VOICES = {
        # 기본 제공 음성 (한국어 지원)
        "eleven_rachel": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "desc": "Rachel - 차분한 여성"},
        "eleven_drew": {"voice_id": "29vD33N1CtxCmqQRPOHJ", "desc": "Drew - 침착한 남성"},
        "eleven_clyde": {"voice_id": "2EiwWnXFnvU5JabPnv8n", "desc": "Clyde - 깊은 남성"},
        "eleven_paul": {"voice_id": "5Q0t7uMcjvnagumLfvZi", "desc": "Paul - 뉴스 앵커 남성"},
        "eleven_domi": {"voice_id": "AZnzlk1XvdvUeBnXmlld", "desc": "Domi - 밝은 여성"},
        "eleven_bella": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "desc": "Bella - 부드러운 여성"},
        "eleven_antoni": {"voice_id": "ErXwobaYiN019PkySvjV", "desc": "Antoni - 따뜻한 남성"},
        "eleven_elli": {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "desc": "Elli - 젊은 여성"},
        "eleven_josh": {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "desc": "Josh - 젊은 남성"},
        "eleven_arnold": {"voice_id": "VR6AewLTigWG4xSOukaG", "desc": "Arnold - 힘있는 남성"},
        "eleven_adam": {"voice_id": "pNInz6obpgDQGcFmaJgB", "desc": "Adam - 깊고 내레이션용 남성"},
        "eleven_sam": {"voice_id": "yoZ06aMxZJJ28mfd3POQ", "desc": "Sam - 활기찬 남성"},
    }

    # 허용된 음성 목록 (검증용)
    ALLOWED_VOICES = [
        # Google TTS
        "ko-KR-Wavenet-A", "ko-KR-Wavenet-B", "ko-KR-Wavenet-C", "ko-KR-Wavenet-D",
        "ko-KR-Neural2-A", "ko-KR-Neural2-B", "ko-KR-Neural2-C",
        # ElevenLabs
        "eleven_rachel", "eleven_drew", "eleven_clyde", "eleven_paul",
        "eleven_domi", "eleven_bella", "eleven_antoni", "eleven_elli",
        "eleven_josh", "eleven_arnold", "eleven_adam", "eleven_sam",
    ]

    def __init__(self):
        """TTS 클라이언트 초기화"""
        self.google_client = None
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

        # Google Cloud TTS 초기화
        if GOOGLE_TTS_AVAILABLE:
            try:
                self.google_client = texttospeech.TextToSpeechClient()
                print("[TTSEngine] Google Cloud TTS initialized")
            except Exception as e:
                print(f"[TTSEngine] Google Cloud TTS init error: {e}")

        # ElevenLabs 확인
        if self.elevenlabs_api_key:
            print("[TTSEngine] ElevenLabs API key found")
        else:
            print("[TTSEngine] Warning: ELEVENLABS_API_KEY not set")

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

        # 음성 설정 (fallback 없음 - 반드시 설정되어야 함)
        voice_config = profile.extra.get("tts_config")
        if not voice_config:
            raise ValueError("TTS 설정이 없습니다. profile.extra['tts_config'] 필수")

        voice_name = voice_config.get("voice")
        if not voice_name:
            raise ValueError("음성이 설정되지 않았습니다. tts_config['voice'] 필수")

        if voice_name not in self.ALLOWED_VOICES:
            raise ValueError(f"허용되지 않은 음성: {voice_name}. 허용 목록: {self.ALLOWED_VOICES}")

        speech_speed = voice_config.get("speed", 1.0)

        # 엔진 결정 (voice_name 기준)
        is_elevenlabs = voice_name.startswith("eleven_")

        for idx, scene in enumerate(scenes):
            narration = self._clean_narration(scene.narration)

            if not narration.strip():
                print(f"[TTSEngine] Scene {idx}: Empty narration, skipping")
                audio_files.append({"path": None, "duration": 0})
                continue

            output_path = os.path.join(output_dir, f"scene_{idx:03d}.mp3")

            try:
                if is_elevenlabs:
                    duration = self._generate_elevenlabs_tts(
                        text=narration,
                        output_path=output_path,
                        voice_key=voice_name
                    )
                else:
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

                engine_name = "ElevenLabs" if is_elevenlabs else "Google"
                print(f"[TTSEngine] Scene {idx}: {duration:.1f}s ({engine_name}) - {output_path}")

            except Exception as e:
                print(f"[TTSEngine] Scene {idx} Error: {e}")
                raise  # fail fast - 에러 발생시 즉시 중단

        return audio_files

    def _generate_google_tts(
        self,
        text: str,
        output_path: str,
        voice_name: str,
        speaking_rate: float = 1.0
    ) -> float:
        """
        Google Cloud TTS로 음성 생성

        Args:
            text: 나레이션 텍스트
            output_path: 출력 파일 경로
            voice_name: 음성 이름 (필수, ALLOWED_VOICES 중 하나)
            speaking_rate: 말하기 속도 (0.25 ~ 4.0)

        Returns:
            오디오 길이 (초)
        """
        if not self.google_client:
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
        response = self.google_client.synthesize_speech(
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

    def _generate_elevenlabs_tts(
        self,
        text: str,
        output_path: str,
        voice_key: str
    ) -> float:
        """
        ElevenLabs TTS로 음성 생성

        Args:
            text: 나레이션 텍스트
            output_path: 출력 파일 경로
            voice_key: 음성 키 (eleven_rachel, eleven_adam 등)

        Returns:
            오디오 길이 (초)
        """
        if not self.elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")

        voice_info = self.ELEVENLABS_VOICES.get(voice_key)
        if not voice_info:
            raise ValueError(f"Unknown ElevenLabs voice: {voice_key}")

        voice_id = voice_info["voice_id"]

        # ElevenLabs API 호출
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # 다국어 모델 (한국어 지원)
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise RuntimeError(f"ElevenLabs API error: {response.status_code} - {response.text}")

        # 파일 저장
        with open(output_path, "wb") as f:
            f.write(response.content)

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
