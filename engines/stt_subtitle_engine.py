"""
Whisper 기반 자막 엔진

TTS로 생성된 음성 파일에서 Whisper로 정확한 타이밍 추출
- OpenAI Whisper (로컬 실행, 무료)
- 단어별 정확한 타임스탬프
- 한국어 인식 정확도 높음
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass

# Whisper
try:
    import whisper
    WHISPER_AVAILABLE = True
    WHISPER_TYPE = "openai"
except ImportError:
    WHISPER_AVAILABLE = False
    WHISPER_TYPE = None

# faster-whisper (더 빠른 대안)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False


@dataclass
class WordTiming:
    """단어별 타이밍 정보"""
    word: str
    start_time: float  # 초
    end_time: float    # 초


@dataclass
class SubtitleSegment:
    """자막 세그먼트"""
    text: str
    start_time: float
    end_time: float


class STTSubtitleEngine:
    """
    Whisper 기반 자막 생성 엔진

    음성 파일에서 실제 발화 타이밍을 추출하여 정확한 자막 생성
    - 무료 (로컬 실행)
    - 오프라인 가능
    - 한국어 인식 우수
    """

    # 자막 크기 프리셋
    FONT_SIZE_PRESETS = {
        "small": 60,
        "medium": 80,
        "large": 100,
        "xlarge": 120,
    }

    def __init__(self, font_size_preset: str = "medium", model_size: str = "medium"):
        """
        Whisper 자막 엔진 초기화

        Args:
            font_size_preset: 자막 크기 (small/medium/large/xlarge)
            model_size: Whisper 모델 크기 (tiny/base/small/medium/large)
                - tiny: 가장 빠름, 정확도 낮음
                - base: 빠름
                - small: 균형
                - medium: 권장 (한국어 좋음)
                - large: 가장 정확, 느림
        """
        self.model = None
        self.model_size = model_size
        self.use_faster_whisper = FASTER_WHISPER_AVAILABLE

        # Whisper 모델 로드
        if FASTER_WHISPER_AVAILABLE:
            print(f"[STTSubtitleEngine] Loading faster-whisper model: {model_size}")
            try:
                # GPU 사용 가능하면 cuda, 아니면 cpu
                self.model = WhisperModel(model_size, device="auto", compute_type="auto")
                print("[STTSubtitleEngine] faster-whisper loaded (GPU accelerated if available)")
            except Exception as e:
                print(f"[STTSubtitleEngine] faster-whisper load error: {e}")
                self.model = None

        elif WHISPER_AVAILABLE:
            print(f"[STTSubtitleEngine] Loading openai-whisper model: {model_size}")
            try:
                self.model = whisper.load_model(model_size)
                print("[STTSubtitleEngine] openai-whisper loaded")
            except Exception as e:
                print(f"[STTSubtitleEngine] whisper load error: {e}")
                self.model = None
        else:
            print("[STTSubtitleEngine] Warning: No whisper library installed!")
            print("  Install with: pip install faster-whisper")
            print("  Or: pip install openai-whisper")

        # 자막 설정
        preset_size = self.FONT_SIZE_PRESETS.get(font_size_preset, 80)
        self.full_sub_size = preset_size
        self.highlight_size = preset_size
        self.highlight_large_size = int(preset_size * 1.25)

        # 자막 분할 설정
        self.max_chars_per_segment = 30  # 한 자막당 최대 글자수
        self.max_segment_duration = 4.0  # 한 자막당 최대 표시 시간 (초)

        print(f"[STTSubtitleEngine] Font size: {font_size_preset} ({preset_size}px)")

    def transcribe_audio(self, audio_path: str) -> List[WordTiming]:
        """
        음성 파일에서 단어별 타이밍 추출 (Whisper)

        Args:
            audio_path: 오디오 파일 경로 (MP3/WAV)

        Returns:
            WordTiming 리스트
        """
        if self.model is None:
            print("[STTSubtitleEngine] No model loaded")
            return []

        if not os.path.exists(audio_path):
            print(f"[STTSubtitleEngine] Audio file not found: {audio_path}")
            return []

        try:
            print(f"[STTSubtitleEngine] Transcribing: {audio_path}")

            word_timings = []

            if self.use_faster_whisper:
                # faster-whisper 사용
                segments, info = self.model.transcribe(
                    audio_path,
                    language="ko",
                    word_timestamps=True,
                    vad_filter=True,  # 음성 활동 감지로 정확도 향상
                )

                for segment in segments:
                    if segment.words:
                        for word in segment.words:
                            word_timings.append(WordTiming(
                                word=word.word.strip(),
                                start_time=word.start,
                                end_time=word.end
                            ))
                    else:
                        # 단어별 타이밍이 없으면 세그먼트 전체 사용
                        word_timings.append(WordTiming(
                            word=segment.text.strip(),
                            start_time=segment.start,
                            end_time=segment.end
                        ))

            else:
                # openai-whisper 사용
                result = self.model.transcribe(
                    audio_path,
                    language="ko",
                    word_timestamps=True,
                )

                for segment in result.get("segments", []):
                    for word_info in segment.get("words", []):
                        word_timings.append(WordTiming(
                            word=word_info["word"].strip(),
                            start_time=word_info["start"],
                            end_time=word_info["end"]
                        ))

            print(f"[STTSubtitleEngine] Extracted {len(word_timings)} words")
            return word_timings

        except Exception as e:
            print(f"[STTSubtitleEngine] Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def words_to_segments(self, word_timings: List[WordTiming]) -> List[SubtitleSegment]:
        """
        단어 타이밍을 자막 세그먼트로 변환

        자연스러운 문장 단위로 묶음
        - 최대 글자수 제한
        - 최대 표시 시간 제한
        - 문장 부호에서 끊기
        """
        if not word_timings:
            return []

        segments = []
        current_words = []
        current_start = word_timings[0].start_time

        for i, wt in enumerate(word_timings):
            current_words.append(wt.word)
            current_text = " ".join(current_words)
            current_duration = wt.end_time - current_start

            # 세그먼트 종료 조건
            should_break = False

            # 1. 문장 부호로 끝나는 경우
            if wt.word.endswith(('.', '?', '!', '。')):
                should_break = True

            # 2. 최대 글자수 초과
            elif len(current_text.replace(" ", "")) >= self.max_chars_per_segment:
                should_break = True

            # 3. 최대 표시 시간 초과
            elif current_duration >= self.max_segment_duration:
                should_break = True

            # 4. 쉼표에서 끊기 (글자가 충분히 많으면)
            elif wt.word.endswith(',') and len(current_text.replace(" ", "")) >= 15:
                should_break = True

            if should_break or i == len(word_timings) - 1:
                # 세그먼트 생성
                segment = SubtitleSegment(
                    text=current_text.strip(),
                    start_time=current_start,
                    end_time=wt.end_time
                )
                segments.append(segment)

                # 초기화
                current_words = []
                if i + 1 < len(word_timings):
                    current_start = word_timings[i + 1].start_time

        return segments

    def generate_subtitles_from_audio(
        self,
        audio_files: List[Dict],
        output_path: str,
        video_width: int = 1920,
        video_height: int = 1080,
        subtitle_mode: str = "full"
    ) -> str:
        """
        오디오 파일들에서 자막 생성

        Args:
            audio_files: 오디오 파일 정보 리스트 [{path, duration}, ...]
            output_path: ASS 자막 출력 경로
            video_width: 영상 너비
            video_height: 영상 높이
            subtitle_mode: 자막 모드 (full/highlight/full_highlight)

        Returns:
            생성된 자막 파일 경로
        """
        all_segments = []
        current_offset = 0.0

        print(f"[STTSubtitleEngine] Processing {len(audio_files)} audio files with Whisper...")

        for idx, audio_info in enumerate(audio_files):
            audio_path = audio_info.get("path")

            if not audio_path or not os.path.exists(audio_path):
                current_offset += audio_info.get("duration", 0)
                continue

            # Whisper로 음성에서 단어 타이밍 추출
            word_timings = self.transcribe_audio(audio_path)

            if word_timings:
                # 단어를 자막 세그먼트로 변환
                segments = self.words_to_segments(word_timings)

                # 오프셋 적용
                for seg in segments:
                    all_segments.append(SubtitleSegment(
                        text=seg.text,
                        start_time=seg.start_time + current_offset,
                        end_time=seg.end_time + current_offset
                    ))

                print(f"  Scene {idx}: {len(segments)} segments extracted")
            else:
                print(f"  Scene {idx}: No words extracted")

            current_offset += audio_info.get("duration", 0)

        # ASS 자막 파일 생성
        return self._generate_ass_file(
            segments=all_segments,
            output_path=output_path,
            video_width=video_width,
            video_height=video_height,
            subtitle_mode=subtitle_mode
        )

    def _generate_ass_file(
        self,
        segments: List[SubtitleSegment],
        output_path: str,
        video_width: int,
        video_height: int,
        subtitle_mode: str
    ) -> str:
        """ASS 자막 파일 생성"""

        ass_content = f"""[Script Info]
Title: Whisper-based Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; 하단 전체 자막 스타일
Style: FullSub,NanumGothic,{self.full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,3,3,3,2,60,60,40,1
; 중앙 하이라이트 스타일
Style: Highlight,Nanum Pen Script,{self.highlight_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1
Style: HighlightLarge,Nanum Pen Script,{self.highlight_large_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        for seg in segments:
            start_str = self._format_ass_time(seg.start_time)
            end_str = self._format_ass_time(seg.end_time)

            # 텍스트 정리
            text = seg.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

            # 페이드 효과
            fade_effect = "{\\fad(200,200)}"

            # 전체 자막 (Layer 0, 하단)
            if subtitle_mode in ["full", "full_highlight"]:
                ass_content += f"Dialogue: 0,{start_str},{end_str},FullSub,,0,0,0,,{fade_effect}{text}\n"

        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        print(f"[STTSubtitleEngine] Saved: {output_path} ({len(segments)} segments)")
        return output_path

    def _format_ass_time(self, seconds: float) -> str:
        """초를 ASS 시간 포맷으로 변환 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


# 편의 함수
def create_stt_subtitle_engine(font_size_preset: str = "medium", model_size: str = "medium") -> STTSubtitleEngine:
    """STT 자막 엔진 생성"""
    return STTSubtitleEngine(font_size_preset=font_size_preset, model_size=model_size)
