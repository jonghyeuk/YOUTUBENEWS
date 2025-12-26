"""
TTS 엔진 - Google WaveNet (기본) + ElevenLabs + OpenAI TTS
스타일별 음성 + 감정 태그 지원
"""
import os
import io
from typing import List, Tuple, Optional
from pydub import AudioSegment as PydubSegment

from models.types import Script, Scene, AudioSegment
from config import TTS_CONFIG, ELEVENLABS_STYLE_VOICES, EMOTION_TAGS


class TTSEngine:
    """TTS 음성 생성 엔진 (WaveNet / ElevenLabs / OpenAI)"""

    ENGINES = ["wavenet", "elevenlabs", "openai"]

    def __init__(self, engine: str = "wavenet", style: str = None, speed: float = None):
        """
        Args:
            engine: "wavenet" (기본), "elevenlabs", 또는 "openai"
            style: 콘텐츠 스타일 (뉴스/정보/믿거나말거나/불교종교)
            speed: 음성 속도 (None이면 config/스타일 설정 사용)
        """
        if engine not in self.ENGINES:
            raise ValueError(f"지원하지 않는 엔진: {engine}. 사용 가능: {self.ENGINES}")

        self.engine = engine
        self.style = style
        self._speed_override = speed  # UI에서 지정한 속도 (우선순위 높음)
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
        # 속도 설정: UI 지정값 > config 값 (0.25 ~ 4.0)
        self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=self.speed,
            pitch=0.0
        )
        print(f"[TTSEngine] Google WaveNet 초기화 완료 (속도: {self.speed})")

    def _init_elevenlabs(self):
        """ElevenLabs 초기화 (스타일별 음성 설정)"""
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

        # 스타일별 음성 설정 가져오기
        if self.style and self.style in ELEVENLABS_STYLE_VOICES:
            voice_config = ELEVENLABS_STYLE_VOICES[self.style]
            self.voice_id = voice_config["voice_id"]
            self.stability = voice_config.get("stability", 0.5)
            self.similarity_boost = voice_config.get("similarity_boost", 0.75)
            # 속도: UI 지정값 > 스타일 값 > 전역 설정
            style_speed = voice_config.get("speed", TTS_CONFIG.get("speed", 1.0))
            self.speed = self._speed_override if self._speed_override else style_speed
            print(f"[TTSEngine] ElevenLabs 초기화 완료 (스타일: {self.style}, 속도: {self.speed})")
        else:
            self.voice_id = TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")
            self.stability = 0.5
            self.similarity_boost = 0.75
            self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
            print(f"[TTSEngine] ElevenLabs 초기화 완료 (기본 음성, 속도: {self.speed})")

    def _init_openai(self):
        """OpenAI TTS 초기화"""
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.voice = TTS_CONFIG.get("openai_voice", "alloy")  # alloy, echo, fable, onyx, nova, shimmer
        # 속도: UI 지정값 > config 값 (0.25 ~ 4.0)
        self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
        print(f"[TTSEngine] OpenAI TTS 초기화 완료 (속도: {self.speed})")

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
        total_scenes = len(script.scenes)

        print(f"[TTSEngine] {total_scenes}개 씬 TTS 생성 시작...")

        for i, scene in enumerate(script.scenes):
            print(f"[TTSEngine] 씬 {scene.scene_id}/{total_scenes} 처리 중...")

            # 감정 태그 추가 (ElevenLabs + 스타일 설정 시)
            text_with_emotion = self._add_emotion_tag(scene.text, i, total_scenes)

            # 씬별 TTS 생성
            audio_data = self._synthesize(text_with_emotion)
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

    def _add_emotion_tag(self, text: str, scene_idx: int, total_scenes: int) -> str:
        """씬 위치에 따라 감정 태그 추가 (ElevenLabs용)"""
        if self.engine != "elevenlabs" or not self.style:
            return text

        if self.style not in EMOTION_TAGS:
            return text

        tags = EMOTION_TAGS[self.style]

        # 씬 위치에 따른 태그 선택
        position = scene_idx / total_scenes

        if position < 0.15:  # 도입부 (0-15%)
            tag = tags.get("intro", "")
        elif position < 0.5:  # 전개부 (15-50%)
            tag = tags.get("body_sad", tags.get("body", ""))
        elif position < 0.75:  # 전환/클라이맥스 (50-75%)
            tag = tags.get("body_hope", tags.get("climax", ""))
        elif position < 0.9:  # 클라이맥스 (75-90%)
            tag = tags.get("climax", "")
        else:  # 엔딩 (90-100%)
            tag = tags.get("ending", "")

        if tag:
            print(f"[TTSEngine] 감정 태그: {tag}")
            return f"{tag} {text}"

        return text

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
        """ElevenLabs TTS (스타일별 음성 설정 적용)"""
        # Eleven v3 모델 사용 (Audio Tags 지원)
        # 참고: https://elevenlabs.io/blog/eleven-v3-alpha-now-available-in-the-api
        audio_generator = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            model_id="eleven_v3",  # v3: Audio Tags 지원 ([calm], [excited] 등)
            voice_settings={
                "stability": getattr(self, 'stability', 0.5),
                "similarity_boost": getattr(self, 'similarity_boost', 0.75),
                "style": 0.5,
                "use_speaker_boost": True,
                "speed": getattr(self, 'speed', 1.0)  # 속도 설정 (0.5 ~ 2.0)
            }
        )

        # generator를 bytes로 변환
        audio_bytes = b"".join(audio_generator)
        return audio_bytes

    def _synthesize_openai(self, text: str) -> bytes:
        """OpenAI TTS"""
        response = self.client.audio.speech.create(
            model="tts-1",  # 또는 "tts-1-hd" (고품질)
            voice=self.voice,
            input=text,
            speed=getattr(self, 'speed', 1.0)  # 속도 설정 (0.25 ~ 4.0)
        )

        return response.content

    def get_elevenlabs_usage(self) -> dict:
        """ElevenLabs 사용량 조회"""
        if self.engine != "elevenlabs":
            return None

        try:
            # 최신 SDK API: user.subscription.get()
            subscription = self.client.user.subscription.get()

            # 사용량 정보 추출
            character_count = subscription.character_count
            character_limit = subscription.character_limit
            usage_percent = (character_count / character_limit * 100) if character_limit > 0 else 0

            # 리셋 날짜
            next_reset = subscription.next_character_count_reset_unix
            if next_reset:
                from datetime import datetime
                reset_date = datetime.fromtimestamp(next_reset)
                reset_str = reset_date.strftime("%Y-%m-%d")
            else:
                reset_str = "알 수 없음"

            return {
                "used": character_count,
                "limit": character_limit,
                "percent": round(usage_percent, 1),
                "reset_date": reset_str,
                "tier": subscription.tier
            }
        except Exception as e:
            print(f"[TTSEngine] ElevenLabs 사용량 조회 실패: {e}")
            return None
