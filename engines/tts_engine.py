"""
TTS 엔진 - Google WaveNet (기본) + ElevenLabs v3 + ElevenLabs Turbo v2.5 + OpenAI TTS
스타일별 음성 + 감정 태그 지원
"""
import os
import io
import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from pydub import AudioSegment as PydubSegment

from models.types import Script, Scene, AudioSegment
from config import TTS_CONFIG, ELEVENLABS_STYLE_VOICES, EMOTION_TAGS, LANGUAGE_CONFIG


# ========== ElevenLabs Turbo v2.5 감정 흉내 시스템 ==========

# Turbo v2.5에서 해석할 "사용자 태그" (ElevenLabs로 그대로 보내지 않음)
EMO_TAGS_V25 = {
    "neutral", "calm", "sad", "angry", "happy", "fear",
    "suspense", "tender", "shout", "whisper", "thoughtful"
}
PAUSE_TAGS_V25 = {"short pause", "pause", "long pause"}

TAG_RE_V25 = re.compile(
    r"\[((?:short pause|long pause|pause)|"
    r"(?:neutral|calm|sad|angry|happy|fear|suspense|tender|shout|whisper|thoughtful))\]",
    re.IGNORECASE
)


@dataclass
class TurboSegment:
    """Turbo v2.5 감정 세그먼트"""
    emotion: str
    text: str


@dataclass
class SubtitleSegment:
    """자막 싱크용 세그먼트 (TTS 텍스트와 분리)"""
    clean_text: str      # 자막용 클린 텍스트 (SSML 제거)
    start_time: float    # 시작 시간 (초)
    end_time: float      # 종료 시간 (초)
    duration: float      # 길이 (초)


def convert_lifespan_to_speech(text: str) -> str:
    """
    TTS가 읽기 어려운 특수 표기 정리

    처리 대상:
    - 생몰년 괄호 (501-531) → 제거
    - 꺾쇠 괄호 《금강경》 → 금강경 (내용만 유지)
    - 홑꺾쇠 〈법화경〉 → 법화경
    """
    # 1. 생몰년 괄호 완전 제거: (501-531), (기원전 563-483) 등
    text = re.sub(r'\(기원전\s*\d+\s*[-~]\s*기원전\s*\d+\)', '', text)
    text = re.sub(r'\(기원전\s*\d+\s*[-~]\s*\d+\)', '', text)
    text = re.sub(r'\(\d{2,4}\s*[-~]\s*\d{2,4}\)', '', text)
    text = re.sub(r'\(\d{2,4}년\)', '', text)

    # 2. 꺾쇠 괄호 제거 (내용은 유지): 《금강경》 → 금강경
    text = re.sub(r'《([^》]+)》', r'\1', text)
    text = re.sub(r'〈([^〉]+)〉', r'\1', text)

    # 3. 연속 공백 정리
    text = re.sub(r'\s{2,}', ' ', text)

    return text.strip()


def clean_text_for_subtitle(text: str) -> str:
    """
    TTS용 텍스트에서 자막용 클린 텍스트 생성
    - SSML 태그 제거 (<break>, <prosody> 등)
    - 감정 태그 제거 ([angry], [calm] 등)
    - 과도한 의성어/말줄임 정리
    """
    clean = text

    # 1. SSML 태그 제거
    clean = re.sub(r'<[^>]+>', '', clean)

    # 2. 감정/pause 태그 제거
    clean = re.sub(r'\[(short pause|long pause|pause|neutral|calm|sad|angry|happy|fear|suspense|tender|shout|whisper|thoughtful)\]', '', clean, flags=re.IGNORECASE)

    # 3. 기타 대괄호 태그 제거
    clean = re.sub(r'\[[^\]]+\]', '', clean)

    # 4. 과도한 느낌표/물음표 정리 (3개 이상 → 1개)
    clean = re.sub(r'!{2,}', '!', clean)
    clean = re.sub(r'\?{2,}', '?', clean)

    # 5. 연속된 말줄임표 정리
    clean = re.sub(r'…{2,}', '…', clean)
    clean = re.sub(r'\.{4,}', '...', clean)

    # 6. 공백 정리
    clean = re.sub(r'\s+', ' ', clean).strip()

    return clean


def extract_break_duration(text: str) -> float:
    """텍스트에서 <break> 태그들의 총 시간 추출 (초)"""
    total = 0.0
    for match in re.finditer(r'<break\s+time="([0-9.]+)s"\s*/>', text):
        total += float(match.group(1))
    return total


def parse_emotion_tags_for_turbo(text: str, default_emotion: str = "neutral") -> List[TurboSegment]:
    """
    입력 텍스트에서 [angry], [sad], [pause] 같은 태그를 파싱하되,
    Turbo로 보낼 최종 텍스트에는 태그를 남기지 않는다.
    """
    emotion = default_emotion
    buf: List[str] = []
    out: List[TurboSegment] = []

    def flush():
        nonlocal buf, emotion
        t = "".join(buf).strip()
        if t:
            out.append(TurboSegment(emotion=emotion, text=t))
        buf = []

    last = 0
    for m in TAG_RE_V25.finditer(text):
        # 태그 이전 텍스트 추가
        buf.append(text[last:m.start()])
        tag = m.group(1).lower().strip()

        # 태그 처리
        if tag in PAUSE_TAGS_V25:
            # Turbo는 SSML <break>를 지원하므로 pause 태그를 break로 치환
            if tag == "short pause":
                buf.append('<break time="0.25s" />')
            elif tag == "pause":
                buf.append('<break time="0.6s" />')
            else:  # long pause
                buf.append('<break time="1.2s" />')
        elif tag in EMO_TAGS_V25:
            # 감정 태그는 구간 분리를 위해 flush 후 감정 상태 변경
            flush()
            emotion = tag
        # 다음 위치
        last = m.end()

    buf.append(text[last:])
    flush()
    return out


def shape_text_for_turbo(text: str, emotion: str) -> str:
    """
    감정 흉내를 강화하는 텍스트 변형 (구두점/호흡/SSML break)
    Turbo v2.5는 태그 대신 문장 형태에 반응
    """
    t = text.strip()

    # 꺾쇠 괄호 제거 (내용은 유지): 《금강경》 → 금강경, 〈법화경〉 → 법화경
    t = re.sub(r'《([^》]+)》', r'\1', t)
    t = re.sub(r'〈([^〉]+)〉', r'\1', t)

    # 한국어 특수 따옴표 제거 (내용은 유지): '반야바라밀' → 반야바라밀
    # TTS가 특수 따옴표를 잘못 해석해서 무음/볼륨 변화를 일으킬 수 있음
    t = re.sub(r''([^']+)'', r'\1', t)
    t = re.sub(r'"([^"]+)"', r'\1', t)

    # (필수) 남아있는 모든 [ ... ] 제거 — Turbo가 읽어버리는 사고 방지
    t = re.sub(r"\[[^\]]+\]", "", t)

    # 과도한 느낌표/물음표는 2개까지만 허용
    def cap_marks(s: str) -> str:
        s = re.sub(r"!{3,}", "!!", s)
        s = re.sub(r"\?{3,}", "??", s)
        s = re.sub(r"\?!{2,}|\!\?{2,}", "?!", s)
        return s

    t = cap_marks(t)

    # 감정별 미세 튜닝
    if emotion in ("angry", "shout"):
        # 짧게 끊고, 강한 끝맺음
        t = t.replace("...", "…")
        if not t.endswith(("!", "!!", "?", "??", "…")):
            t += "!"
        # 질문형이면 ?!로 살짝 올리기
        if t.endswith("?"):
            t = t[:-1] + "?!"

    elif emotion in ("sad", "tender"):
        # 호흡 늘리고, 말줄임/쉼표로 속도 떨어뜨림
        t = t.replace("!", ".")
        t = t.replace("??", "?")
        # 문장 중간에 너무 길면 약한 break 삽입
        if len(t) > 80 and "<break" not in t:
            t = t.replace(",", ', <break time="0.25s" />', 1)

    elif emotion in ("fear", "suspense"):
        # 짧은 호흡과 멈칫
        if "<break" not in t:
            # 핵심 단어 앞에 짧은 멈춤
            t = re.sub(r"(그때|순간|문득|갑자기)", r'<break time="0.25s" /> \1', t, count=1)
        t = t.replace("!", "!!")  # 공포는 가끔 강세가 필요

    elif emotion in ("happy",):
        # 밝게, 다만 과한 느낌표 금지
        t = re.sub(r"!{2,}", "!", t)
        if not t.endswith(("!", "?", "…")):
            t += "!"

    elif emotion in ("whisper", "thoughtful", "calm"):
        # 차분하게
        t = re.sub(r"!+", ".", t)
        t = t.replace("!!", ".")
        if len(t) > 90 and "<break" not in t:
            t = t + ' <break time="0.35s" />'

    return t.strip()


def voice_settings_for_emotion(emotion: str) -> Dict:
    """감정별 voice_settings 프리셋 (Turbo v2.5용)"""
    # 기본값(중립)
    base = dict(
        stability=0.60,
        similarity_boost=0.82,
        style=0.20,
        use_speaker_boost=True,
    )

    presets = {
        "neutral":    dict(stability=0.60, similarity_boost=0.82, style=0.20),
        "calm":       dict(stability=0.75, similarity_boost=0.84, style=0.10),
        "thoughtful": dict(stability=0.70, similarity_boost=0.84, style=0.15),

        "sad":        dict(stability=0.78, similarity_boost=0.80, style=0.15),
        "tender":     dict(stability=0.72, similarity_boost=0.83, style=0.20),

        "happy":      dict(stability=0.45, similarity_boost=0.83, style=0.35),
        "angry":      dict(stability=0.30, similarity_boost=0.86, style=0.55),
        "shout":      dict(stability=0.25, similarity_boost=0.86, style=0.60),

        "fear":       dict(stability=0.38, similarity_boost=0.84, style=0.45),
        "suspense":   dict(stability=0.50, similarity_boost=0.84, style=0.40),

        "whisper":    dict(stability=0.65, similarity_boost=0.82, style=0.12),
    }

    cfg = presets.get(emotion, base)
    result = base.copy()
    result.update(cfg)
    return result


# 스타일별 기본 감정 매핑 (Turbo v2.5용)
STYLE_DEFAULT_EMOTIONS_V25 = {
    "불교종교": {
        "intro": "calm",
        "body_early": "sad",
        "body_late": "tender",
        "climax": "thoughtful",
        "ending": "calm",
    },
    "믿거나말거나": {
        "intro": "neutral",
        "body_early": "suspense",
        "body_late": "fear",
        "climax": "angry",
        "ending": "thoughtful",
    },
    "뉴스": {
        "intro": "neutral",
        "body_early": "neutral",
        "body_late": "neutral",
        "climax": "neutral",
        "ending": "calm",
    },
    "정보": {
        "intro": "happy",
        "body_early": "neutral",
        "body_late": "neutral",
        "climax": "happy",
        "ending": "calm",
    },
}


class TTSEngine:
    """TTS 음성 생성 엔진 (WaveNet / ElevenLabs v3 / ElevenLabs Turbo v2.5 / OpenAI)"""

    ENGINES = ["wavenet", "elevenlabs", "elevenlabs2.5", "elevenlabs2.5_limkony", "openai"]

    # 언어별 WaveNet 음성 설정
    WAVENET_VOICES = {
        "ko": {"language_code": "ko-KR", "name": "ko-KR-Wavenet-D"},
        "ja": {"language_code": "ja-JP", "name": "ja-JP-Wavenet-D"},
        "en": {"language_code": "en-US", "name": "en-US-Wavenet-D"},
    }

    def __init__(self, engine: str = "wavenet", style: str = None, speed: float = None, language: str = "ko"):
        """
        Args:
            engine: "wavenet" (기본), "elevenlabs", 또는 "openai"
            style: 콘텐츠 스타일 (뉴스/정보/믿거나말거나/불교종교)
            speed: 음성 속도 (None이면 config/스타일 설정 사용)
            language: 출력 언어 (ko/ja/en)
        """
        if engine not in self.ENGINES:
            raise ValueError(f"지원하지 않는 엔진: {engine}. 사용 가능: {self.ENGINES}")

        self.engine = engine
        self.style = style
        self.language = language
        self._speed_override = speed  # UI에서 지정한 속도 (우선순위 높음)
        self._init_engine()

    def _init_engine(self):
        """선택된 엔진 초기화"""
        if self.engine == "wavenet":
            self._init_wavenet()
        elif self.engine == "elevenlabs":
            self._init_elevenlabs()
        elif self.engine == "elevenlabs2.5":
            self._init_elevenlabs_v25()
        elif self.engine == "elevenlabs2.5_limkony":
            self._init_elevenlabs_v25_limkony()
        elif self.engine == "openai":
            self._init_openai()

    def _init_wavenet(self):
        """Google Cloud TTS 초기화 (언어별 음성 지원)"""
        from google.cloud import texttospeech
        self.client = texttospeech.TextToSpeechClient()

        # 언어별 WaveNet 음성 설정
        voice_config = self.WAVENET_VOICES.get(self.language, self.WAVENET_VOICES["ko"])
        lang_name = LANGUAGE_CONFIG.get(self.language, {}).get("name", "🇰🇷 한국어")

        self.voice = texttospeech.VoiceSelectionParams(
            language_code=voice_config["language_code"],
            name=voice_config["name"]
        )
        # 속도 설정: UI 지정값 > config 값 (0.25 ~ 4.0)
        self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=self.speed,
            pitch=0.0
        )
        print(f"[TTSEngine] Google WaveNet 초기화 완료 ({lang_name}, 속도: {self.speed})")

    def _init_elevenlabs(self):
        """ElevenLabs 초기화 (언어별 + 스타일별 음성 설정)"""
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

        # 언어별 voice_id 우선 적용
        lang_config = LANGUAGE_CONFIG.get(self.language, {})
        lang_voice_id = lang_config.get("tts_voice_id")
        lang_name = lang_config.get("name", "🇰🇷 한국어")

        # 스타일별 음성 설정 가져오기
        if self.style and self.style in ELEVENLABS_STYLE_VOICES:
            voice_config = ELEVENLABS_STYLE_VOICES[self.style]
            # 불교종교/불교강의/영어Saying전용: 스타일 voice_id 우선 사용 (전용 음성)
            if self.style in ("영어Saying전용", "불교종교", "불교강의"):
                self.voice_id = voice_config["voice_id"]
            else:
                # 다른 스타일: 언어별 voice_id 우선
                self.voice_id = lang_voice_id if lang_voice_id else voice_config["voice_id"]
            self.stability = voice_config.get("stability", 0.5)
            self.similarity_boost = voice_config.get("similarity_boost", 0.75)
            # 속도: UI 지정값 > 스타일 값 > 전역 설정
            style_speed = voice_config.get("speed", TTS_CONFIG.get("speed", 1.0))
            self.speed = self._speed_override if self._speed_override else style_speed
            print(f"[TTSEngine] ElevenLabs 초기화 완료 ({lang_name}, 스타일: {self.style}, voice: {self.voice_id[:8]}..., 속도: {self.speed})")
        else:
            self.voice_id = lang_voice_id if lang_voice_id else TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")
            self.stability = 0.5
            self.similarity_boost = 0.75
            self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
            print(f"[TTSEngine] ElevenLabs 초기화 완료 ({lang_name}, 기본 음성, 속도: {self.speed})")

    def _init_elevenlabs_v25(self):
        """ElevenLabs Turbo v2.5 초기화 (언어별 + SSML + voice_settings 기반 감정 흉내)"""
        from elevenlabs.client import ElevenLabs
        self.client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

        # 언어별 voice_id 우선 적용
        lang_config = LANGUAGE_CONFIG.get(self.language, {})
        lang_voice_id = lang_config.get("tts_voice_id")
        lang_name = lang_config.get("name", "🇰🇷 한국어")

        # 스타일별 음성 설정 가져오기
        if self.style and self.style in ELEVENLABS_STYLE_VOICES:
            voice_config = ELEVENLABS_STYLE_VOICES[self.style]
            # 불교종교/불교강의/영어Saying전용: 스타일 voice_id 우선 사용 (전용 음성)
            if self.style in ("영어Saying전용", "불교종교", "불교강의"):
                self.voice_id = voice_config["voice_id"]
            else:
                # 다른 스타일: 언어별 voice_id 우선
                self.voice_id = lang_voice_id if lang_voice_id else voice_config["voice_id"]
            # 속도: UI 지정값 > 스타일 값 > 전역 설정
            style_speed = voice_config.get("speed", TTS_CONFIG.get("speed", 1.0))
            self.speed = self._speed_override if self._speed_override else style_speed
            print(f"[TTSEngine] ElevenLabs Turbo v2.5 초기화 완료 ({lang_name}, 스타일: {self.style}, voice: {self.voice_id[:8]}..., 속도: {self.speed})")
        else:
            self.voice_id = lang_voice_id if lang_voice_id else TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")
            self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
            print(f"[TTSEngine] ElevenLabs Turbo v2.5 초기화 완료 ({lang_name}, 기본 음성, 속도: {self.speed})")

    def _init_elevenlabs_v25_limkony(self):
        """ElevenLabs Turbo v2.5 (limkony 계정) 초기화 - 별도 API 키 사용, elevenlabs2.5와 동일 로직"""
        from elevenlabs.client import ElevenLabs
        # limkony 전용 API 키 사용
        api_key = os.getenv("ELEVENLABS_API_KEY_LIMKONY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY_LIMKONY 환경변수가 설정되지 않았습니다")
        self.client = ElevenLabs(api_key=api_key)

        # 언어별 voice_id 우선 적용 (elevenlabs2.5와 동일)
        lang_config = LANGUAGE_CONFIG.get(self.language, {})
        lang_voice_id = lang_config.get("tts_voice_id")
        lang_name = lang_config.get("name", "🇰🇷 한국어")

        # 스타일별 음성 설정 가져오기
        if self.style and self.style in ELEVENLABS_STYLE_VOICES:
            voice_config = ELEVENLABS_STYLE_VOICES[self.style]
            # 불교종교/불교강의/영어Saying전용: 스타일 voice_id 우선 사용 (전용 음성)
            if self.style in ("영어Saying전용", "불교종교", "불교강의"):
                self.voice_id = voice_config["voice_id"]
            else:
                # 다른 스타일: 언어별 voice_id 우선
                self.voice_id = lang_voice_id if lang_voice_id else voice_config["voice_id"]
            # 속도: UI 지정값 > 스타일 값 > 전역 설정
            style_speed = voice_config.get("speed", TTS_CONFIG.get("speed", 1.0))
            self.speed = self._speed_override if self._speed_override else style_speed
            print(f"[TTSEngine] ElevenLabs v2.5 (limkony) 초기화 완료 ({lang_name}, 스타일: {self.style}, voice: {self.voice_id[:8]}..., 속도: {self.speed})")
        else:
            self.voice_id = lang_voice_id if lang_voice_id else TTS_CONFIG.get("elevenlabs_voice_id", "pNInz6obpgDQGcFmaJgB")
            self.speed = self._speed_override if self._speed_override else TTS_CONFIG.get("speed", 1.0)
            print(f"[TTSEngine] ElevenLabs v2.5 (limkony) 초기화 완료 ({lang_name}, 기본 음성, 속도: {self.speed})")

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
    ) -> Tuple[str, List[AudioSegment], List[SubtitleSegment]]:
        """
        전체 대본으로 단일 오디오 파일 생성

        Args:
            script: Script 객체
            output_path: 출력 파일 경로

        Returns:
            (오디오 파일 경로, 씬별 AudioSegment 리스트, 자막용 SubtitleSegment 리스트)
        """
        segments = []
        subtitle_segments = []  # 자막 싱크용 세그먼트
        combined = PydubSegment.empty()

        # 시작 무음 추가 (영상 시작 시 급작스럽지 않게)
        start_silence = PydubSegment.silent(duration=1500)  # 1.5초
        combined += start_silence
        current_time = 1.5  # 시작 무음 반영

        print(f"[TTSEngine] ⏱️ 시작 무음 1.5초 추가됨 (combined 길이: {len(combined)}ms)")

        total_scenes = len(script.scenes)

        print(f"[TTSEngine] {total_scenes}개 씬 TTS 생성 시작...")

        for i, scene in enumerate(script.scenes):
            # 원본 텍스트 저장 (자막용)
            original_text = scene.text
            text_len = len(original_text)

            print(f"[TTSEngine] 씬 {scene.scene_id}/{total_scenes} 처리 중... (텍스트: {text_len}자)")

            # 감정 태그 추가 (ElevenLabs v3 + 스타일 설정 시)
            text_with_emotion = self._add_emotion_tag(scene.text, i, total_scenes)

            # 씬별 TTS 생성 (elevenlabs2.5는 scene 정보 필요)
            audio_data = self._synthesize(text_with_emotion, scene_idx=i, total_scenes=total_scenes)
            scene_audio = PydubSegment.from_mp3(io.BytesIO(audio_data))

            duration = len(scene_audio) / 1000.0  # ms → sec

            # 디버그: 텍스트 길이 대비 오디오 길이 체크
            chars_per_sec = text_len / duration if duration > 0 else 0
            if chars_per_sec > 10:  # 초당 10자 이상이면 너무 빠름 (의심)
                print(f"[TTSEngine] ⚠️ 씬 {scene.scene_id}: {text_len}자 → {duration:.1f}초 (초당 {chars_per_sec:.1f}자, 너무 빠름?)")
            else:
                print(f"[TTSEngine] ✓ 씬 {scene.scene_id}: {text_len}자 → {duration:.1f}초")

            segment = AudioSegment(
                scene_id=scene.scene_id,
                start_time=current_time,
                end_time=current_time + duration,
                duration=duration
            )
            segments.append(segment)

            # 자막용 클린 텍스트 생성 (SSML, 감정 태그 제거)
            clean_text = clean_text_for_subtitle(original_text)
            subtitle_seg = SubtitleSegment(
                clean_text=clean_text,
                start_time=current_time,
                end_time=current_time + duration,
                duration=duration
            )
            subtitle_segments.append(subtitle_seg)

            # 씬 사이 무음 추가 (호흡 시간)
            silence = PydubSegment.silent(duration=2000)  # 2초
            combined += scene_audio + silence

            current_time += duration + 2.0

        # 파일 저장
        combined.export(output_path, format="mp3")

        total_duration = sum(s.duration for s in segments)
        print(f"[TTSEngine] TTS 생성 완료: {total_duration:.1f}초")
        print(f"[TTSEngine] 자막 세그먼트: {len(subtitle_segments)}개 생성")

        return output_path, segments, subtitle_segments

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

    def _synthesize(self, text: str, scene_idx: int = 0, total_scenes: int = 1) -> bytes:
        """텍스트를 음성으로 변환"""
        if self.engine == "wavenet":
            return self._synthesize_wavenet(text)
        elif self.engine == "elevenlabs":
            return self._synthesize_elevenlabs(text)
        elif self.engine == "elevenlabs2.5":
            return self._synthesize_elevenlabs_v25(text, scene_idx, total_scenes)
        elif self.engine == "elevenlabs2.5_limkony":
            # limkony 계정도 동일한 v2.5 합성 로직 사용 (API 키만 다름)
            return self._synthesize_elevenlabs_v25(text, scene_idx, total_scenes)
        elif self.engine == "openai":
            return self._synthesize_openai(text)

    def _synthesize_wavenet(self, text: str) -> bytes:
        """Google WaveNet TTS (영어Saying전용: SSML prosody 적용)"""
        from google.cloud import texttospeech

        # 영어Saying전용 스타일: SSML prosody로 따뜻한 목회자 톤 적용
        if self.style == "영어Saying전용" and self.language == "en":
            # rate=0.85 (느리게), pitch=-5% (낮게) → 따뜻한 목회자 톤
            ssml_text = f'<speak><prosody rate="0.85" pitch="-5%">{text}</prosody></speak>'
            input_text = texttospeech.SynthesisInput(ssml=ssml_text)
            print(f"[TTSEngine] WaveNet 영어Saying전용: SSML prosody 적용 (rate=0.85, pitch=-5%)")
        else:
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
            },
            apply_text_normalization="on"  # 숫자/기호 자동 변환
        )

        # generator를 bytes로 변환
        audio_bytes = b"".join(audio_generator)
        return audio_bytes

    def _synthesize_elevenlabs_v25(self, text: str, scene_idx: int, total_scenes: int) -> bytes:
        """
        ElevenLabs Turbo v2.5 TTS (SSML + voice_settings 기반 감정 흉내)
        - 태그를 읽지 않게 제거하고 내부 감정 상태로만 사용
        - 텍스트 변형 + <break> + 구간별 voice_settings 적용
        """
        # 씬 위치에 따른 기본 감정 결정
        default_emotion = self._get_default_emotion_v25(scene_idx, total_scenes)

        # 텍스트에서 감정 태그 파싱 (태그는 제거됨)
        segments = parse_emotion_tags_for_turbo(text, default_emotion)

        if not segments:
            segments = [TurboSegment(emotion=default_emotion, text=text)]

        audio_chunks: List[bytes] = []

        for seg in segments:
            # 감정에 맞게 텍스트 변형 (구두점, SSML break 등)
            shaped_text = shape_text_for_turbo(seg.text, seg.emotion)

            # 디버그: 원본 vs 변형 텍스트 비교
            if len(seg.text) != len(shaped_text):
                print(f"[TTSEngine] ⚠️ 텍스트 변형: {len(seg.text)}자 → {len(shaped_text)}자")
                if len(shaped_text) < 10:
                    print(f"[TTSEngine] ⚠️ 변형 후 텍스트가 너무 짧음: '{shaped_text}'")

            if not shaped_text.strip():
                print(f"[TTSEngine] ⚠️ 빈 텍스트 건너뜀 (원본: {len(seg.text)}자)")
                continue

            # 감정별 voice_settings 적용
            vs = voice_settings_for_emotion(seg.emotion)
            vs["speed"] = getattr(self, 'speed', 1.0)

            print(f"[TTSEngine] Turbo v2.5 감정: {seg.emotion}, settings: stability={vs['stability']:.2f}, style={vs['style']:.2f}")

            # Turbo v2.5 API 호출
            # apply_text_normalization: 숫자/날짜를 자동으로 자연스럽게 발음
            audio_generator = self.client.text_to_speech.convert(
                text=shaped_text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2_5",  # Turbo v2.5: SSML 지원, 빠름
                voice_settings=vs,
                apply_text_normalization="on"  # 숫자/기호 자동 변환
            )

            audio_bytes = b"".join(audio_generator)
            audio_chunks.append(audio_bytes)

        # 모든 세그먼트 오디오 병합
        if len(audio_chunks) == 1:
            return audio_chunks[0]

        # 여러 세그먼트면 pydub으로 병합
        combined = PydubSegment.empty()
        for chunk in audio_chunks:
            seg_audio = PydubSegment.from_mp3(io.BytesIO(chunk))
            combined += seg_audio

        # bytes로 반환
        output_buffer = io.BytesIO()
        combined.export(output_buffer, format="mp3")
        return output_buffer.getvalue()

    def _get_default_emotion_v25(self, scene_idx: int, total_scenes: int) -> str:
        """씬 위치에 따른 기본 감정 반환 (Turbo v2.5용)"""
        if not self.style or self.style not in STYLE_DEFAULT_EMOTIONS_V25:
            return "neutral"

        emotions = STYLE_DEFAULT_EMOTIONS_V25[self.style]
        position = scene_idx / total_scenes if total_scenes > 0 else 0

        if position < 0.15:  # 도입부 (0-15%)
            return emotions.get("intro", "neutral")
        elif position < 0.4:  # 전개부 초반 (15-40%)
            return emotions.get("body_early", "neutral")
        elif position < 0.7:  # 전개부 후반 (40-70%)
            return emotions.get("body_late", "neutral")
        elif position < 0.9:  # 클라이맥스 (70-90%)
            return emotions.get("climax", "neutral")
        else:  # 엔딩 (90-100%)
            return emotions.get("ending", "calm")

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
        if self.engine not in ("elevenlabs", "elevenlabs2.5", "elevenlabs2.5_limkony"):
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
