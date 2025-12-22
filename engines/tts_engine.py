"""
TTS 엔진 - Google WaveNet (기본) + ElevenLabs + OpenAI TTS
"""
import os
import io
from typing import List, Tuple
from pydub import AudioSegment as PydubSegment

from models.types import Script, Scene, AudioSegment
from config import TTS_CONFIG


class TTSEngine:
    """TTS 음성 생성 엔진 (WaveNet / ElevenLabs / OpenAI)"""

    ENGINES = ["wavenet", "elevenlabs", "openai"]

    def __init__(self, engine: str = "wavenet"):
        """
        Args:
            engine: "wavenet" (기본), "elevenlabs", 또는 "openai"
        """
        if engine not in self.ENGINES:
            raise ValueError(f"지원하지 않는 엔진: {engine}. 사용 가능: {self.ENGINES}")

        self.engine = engine
        self._init_engine()

    def _init_engine(self):
        """선택된 엔진 초기화"""
        if self.engine == "wavenet":
            self._init_wavenet()
        elif self.engine == "elevenlabs":
            self._init_elevenlabs()
        elif self.engine == "openai":
            self._init_openai()

    def _init_wavenet(self):
        """Google Cloud TTS 초기화"""
        from google.cloud import texttospeech
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=TTS_CONFIG.get("wavenet_voice", "ko-KR-Wavenet-D")
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )
        print("[TTSEngine] Google WaveNet 초기화 완료")

    def _init_elevenlabs(self):
        """ElevenLabs 초기화"""
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        self.voice_id = TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")
        print("[TTSEngine] ElevenLabs 초기화 완료")

    def _init_openai(self):
        """OpenAI TTS 초기화"""
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.voice = TTS_CONFIG.get("openai_voice", "alloy")  # alloy, echo, fable, onyx, nova, shimmer
        print("[TTSEngine] OpenAI TTS 초기화 완료")

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

        print(f"[TTSEngine] {len(script.scenes)}개 씬 TTS 생성 시작...")

        for i, scene in enumerate(script.scenes):
            print(f"[TTSEngine] 씬 {scene.scene_id}/{len(script.scenes)} 처리 중...")

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

        total_duration = sum(s.duration for s in segments)
        print(f"[TTSEngine] TTS 생성 완료: {total_duration:.1f}초")

        return output_path, segments

    def _synthesize(self, text: str) -> bytes:
        """텍스트를 음성으로 변환"""
        if self.engine == "wavenet":
            return self._synthesize_wavenet(text)
        elif self.engine == "elevenlabs":
            return self._synthesize_elevenlabs(text)
        elif self.engine == "openai":
            return self._synthesize_openai(text)

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

    def _synthesize_openai(self, text: str) -> bytes:
        """OpenAI TTS"""
        response = self.client.audio.speech.create(
            model="tts-1",  # 또는 "tts-1-hd" (고품질)
            voice=self.voice,
            input=text
        )

        return response.content
