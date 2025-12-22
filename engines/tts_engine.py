"""
TTS 엔진 - Google WaveNet + ElevenLabs
"""
import os
import io
from typing import List, Tuple
from pydub import AudioSegment as PydubSegment

from models.types import Script, Scene, AudioSegment
from config import TTS_CONFIG


class TTSEngine:
    """TTS 음성 생성 엔진"""

    def __init__(self, engine: str = "wavenet"):
        """
        Args:
            engine: "wavenet" 또는 "elevenlabs"
        """
        self.engine = engine

        if engine == "wavenet":
            self._init_wavenet()
        elif engine == "elevenlabs":
            self._init_elevenlabs()

    def _init_wavenet(self):
        """Google Cloud TTS 초기화"""
        from google.cloud import texttospeech
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=TTS_CONFIG["wavenet_voice"]
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )

    def _init_elevenlabs(self):
        """ElevenLabs 초기화"""
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.voice_id = TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")  # Adam

    def generate_full_audio(
        self,
        script: Script,
        output_path: str
    ) -> Tuple[str, List[AudioSegment]]:
        """
        전체 대본으로 단일 오디오 파일 생성

        Args:
            script: Script 객체
            output_path: 출력 파일 경로

        Returns:
            (오디오 파일 경로, 씬별 AudioSegment 리스트)
        """
        segments = []
        combined = PydubSegment.empty()
        current_time = 0.0

        for scene in script.scenes:
            # 씬별 TTS 생성
            audio_data = self._synthesize(scene.text)
            scene_audio = PydubSegment.from_mp3(io.BytesIO(audio_data))

            duration = len(scene_audio) / 1000.0  # ms → sec

            segment = AudioSegment(
                scene_id=scene.scene_id,
                start_time=current_time,
                end_time=current_time + duration,
                duration=duration
            )
            segments.append(segment)

            # 씬 사이 짧은 무음 추가
            silence = PydubSegment.silent(duration=500)  # 0.5초
            combined += scene_audio + silence

            current_time += duration + 0.5

        # 파일 저장
        combined.export(output_path, format="mp3")

        return output_path, segments

    def _synthesize(self, text: str) -> bytes:
        """텍스트를 음성으로 변환"""
        if self.engine == "wavenet":
            return self._synthesize_wavenet(text)
        else:
            return self._synthesize_elevenlabs(text)

    def _synthesize_wavenet(self, text: str) -> bytes:
        """Google WaveNet TTS"""
        from google.cloud import texttospeech

        input_text = texttospeech.SynthesisInput(text=text)

        response = self.client.synthesize_speech(
            input=input_text,
            voice=self.voice,
            audio_config=self.audio_config
        )

        return response.audio_content

    def _synthesize_elevenlabs(self, text: str) -> bytes:
        """ElevenLabs TTS"""
        audio = self.client.generate(
            text=text,
            voice=self.voice_id,
            model="eleven_multilingual_v2"
        )

        # generator를 bytes로 변환
        audio_bytes = b"".join(audio)
        return audio_bytes
