"""
Whisper 기반 자막 엔진

TTS로 생성된 음성 파일에서 Whisper로 정확한 타이밍 추출
- Whisper: 타이밍만 추출 (언제 말했는지)
- 원본 나레이션: 자막 텍스트 (정확한 텍스트)
- 한국어 인식 정확도 높음
"""

import os
import re
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
class TimingInfo:
    """세그먼트별 타이밍 정보"""
    start_time: float  # 초
    end_time: float    # 초
    text: str          # Whisper 인식 텍스트 (참조용)


@dataclass
class SubtitleSegment:
    """자막 세그먼트"""
    text: str          # 원본 나레이션 텍스트
    start_time: float
    end_time: float


class STTSubtitleEngine:
    """
    Whisper 기반 자막 생성 엔진

    ★ 핵심 전략:
    - Whisper: 타이밍만 추출 (언제 말했는지)
    - 원본 나레이션: 자막 텍스트 (맞춤법 정확)
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
        """
        self.model = None
        self.model_size = model_size
        self.use_faster_whisper = FASTER_WHISPER_AVAILABLE

        # Whisper 모델 로드
        if FASTER_WHISPER_AVAILABLE:
            print(f"[STTSubtitleEngine] Loading faster-whisper model: {model_size}")
            try:
                self.model = WhisperModel(model_size, device="auto", compute_type="auto")
                print("[STTSubtitleEngine] faster-whisper loaded")
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

        # 자막 설정
        preset_size = self.FONT_SIZE_PRESETS.get(font_size_preset, 80)
        self.full_sub_size = preset_size
        self.highlight_size = preset_size
        self.highlight_large_size = int(preset_size * 1.25)

        # 자막 분할 설정
        self.max_chars_per_segment = 30
        self.max_segment_duration = 4.0

        print(f"[STTSubtitleEngine] Font size: {font_size_preset} ({preset_size}px)")

    def extract_timing(self, audio_path: str) -> List[TimingInfo]:
        """
        음성 파일에서 세그먼트별 타이밍 추출 (Whisper)

        Args:
            audio_path: 오디오 파일 경로

        Returns:
            TimingInfo 리스트 (시작/끝 시간)
        """
        if self.model is None:
            print("[STTSubtitleEngine] No model loaded")
            return []

        if not os.path.exists(audio_path):
            print(f"[STTSubtitleEngine] Audio file not found: {audio_path}")
            return []

        try:
            print(f"[STTSubtitleEngine] Extracting timing: {audio_path}")

            timings = []

            if self.use_faster_whisper:
                segments, info = self.model.transcribe(
                    audio_path,
                    language="ko",
                    word_timestamps=True,
                    vad_filter=True,
                )

                for segment in segments:
                    timings.append(TimingInfo(
                        start_time=segment.start,
                        end_time=segment.end,
                        text=segment.text.strip()
                    ))
            else:
                result = self.model.transcribe(
                    audio_path,
                    language="ko",
                    word_timestamps=True,
                )

                for segment in result.get("segments", []):
                    timings.append(TimingInfo(
                        start_time=segment["start"],
                        end_time=segment["end"],
                        text=segment["text"].strip()
                    ))

            print(f"[STTSubtitleEngine] Extracted {len(timings)} timing segments")
            return timings

        except Exception as e:
            print(f"[STTSubtitleEngine] Timing extraction error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def align_text_to_timing(
        self,
        original_text: str,
        timings: List[TimingInfo],
        audio_duration: float
    ) -> List[SubtitleSegment]:
        """
        원본 텍스트를 Whisper 타이밍에 맞춰 정렬

        ★ 핵심: Whisper 타이밍 + 원본 텍스트

        Args:
            original_text: 원본 나레이션 텍스트
            timings: Whisper에서 추출한 타이밍
            audio_duration: 오디오 총 길이

        Returns:
            SubtitleSegment 리스트
        """
        if not timings or not original_text:
            # 타이밍이 없으면 균등 분할
            return self._fallback_split(original_text, audio_duration)

        # 원본 텍스트를 문장으로 분할
        sentences = self._split_to_sentences(original_text)

        if not sentences:
            return []

        segments = []

        # 타이밍 개수와 문장 개수가 비슷하면 1:1 매핑
        if len(timings) >= len(sentences):
            # 각 문장에 타이밍 할당
            for i, sentence in enumerate(sentences):
                if i < len(timings):
                    timing = timings[i]
                else:
                    # 남은 문장은 마지막 타이밍 이후로
                    timing = timings[-1]

                segments.append(SubtitleSegment(
                    text=sentence,
                    start_time=timing.start_time,
                    end_time=timing.end_time
                ))
        else:
            # 타이밍이 적으면 문장을 타이밍에 맞춰 그룹화
            sentences_per_timing = len(sentences) / len(timings)

            for i, timing in enumerate(timings):
                start_idx = int(i * sentences_per_timing)
                end_idx = int((i + 1) * sentences_per_timing)

                grouped_text = " ".join(sentences[start_idx:end_idx])

                if grouped_text:
                    segments.append(SubtitleSegment(
                        text=grouped_text,
                        start_time=timing.start_time,
                        end_time=timing.end_time
                    ))

        # 긴 세그먼트 분할
        final_segments = []
        for seg in segments:
            if len(seg.text) > self.max_chars_per_segment:
                # 긴 세그먼트를 여러 개로 분할
                split_segs = self._split_long_segment(seg)
                final_segments.extend(split_segs)
            else:
                final_segments.append(seg)

        return final_segments

    def _split_to_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        # 화자 태그 제거
        text = re.sub(r'\[NARRATOR\d*\]\s*', '', text)
        text = re.sub(r'\[화자\d*\]\s*', '', text)

        # 문장 분리
        sentences = re.split(r'([.!?])\s*', text)

        result = []
        i = 0
        while i < len(sentences):
            sent = sentences[i].strip()
            if sent:
                # 다음 요소가 구두점이면 붙이기
                if i + 1 < len(sentences) and sentences[i + 1] in '.!?':
                    sent += sentences[i + 1]
                    i += 1
                if len(sent) >= 5:  # 너무 짧은 문장 제외
                    result.append(sent)
            i += 1

        return result

    def _split_long_segment(self, segment: SubtitleSegment) -> List[SubtitleSegment]:
        """긴 세그먼트를 여러 개로 분할"""
        text = segment.text
        duration = segment.end_time - segment.start_time

        # 쉼표나 공백에서 분할
        parts = re.split(r'[,，]\s*|\s+', text)

        # 적절한 크기로 그룹화
        groups = []
        current_group = []
        current_len = 0

        for part in parts:
            if current_len + len(part) > self.max_chars_per_segment and current_group:
                groups.append(" ".join(current_group))
                current_group = [part]
                current_len = len(part)
            else:
                current_group.append(part)
                current_len += len(part) + 1

        if current_group:
            groups.append(" ".join(current_group))

        # 시간 분배
        if not groups:
            return [segment]

        time_per_group = duration / len(groups)
        result = []

        for i, group_text in enumerate(groups):
            result.append(SubtitleSegment(
                text=group_text,
                start_time=segment.start_time + (i * time_per_group),
                end_time=segment.start_time + ((i + 1) * time_per_group)
            ))

        return result

    def _fallback_split(self, text: str, duration: float) -> List[SubtitleSegment]:
        """타이밍이 없을 때 균등 분할 (fallback)"""
        sentences = self._split_to_sentences(text)

        if not sentences:
            return []

        time_per_sentence = duration / len(sentences)
        segments = []

        for i, sentence in enumerate(sentences):
            segments.append(SubtitleSegment(
                text=sentence,
                start_time=i * time_per_sentence,
                end_time=(i + 1) * time_per_sentence
            ))

        return segments

    def generate_subtitles_from_audio(
        self,
        audio_files: List[Dict],
        output_path: str,
        video_width: int = 1920,
        video_height: int = 1080,
        subtitle_mode: str = "full",
        scenes: List = None  # ★ 원본 나레이션을 위한 Scene 리스트
    ) -> str:
        """
        오디오 파일들에서 자막 생성

        ★ Whisper 타이밍 + 원본 나레이션 텍스트

        Args:
            audio_files: 오디오 파일 정보 리스트 [{path, duration}, ...]
            output_path: ASS 자막 출력 경로
            video_width: 영상 너비
            video_height: 영상 높이
            subtitle_mode: 자막 모드 (full/highlight/full_highlight)
            scenes: Scene 리스트 (원본 나레이션 텍스트용)

        Returns:
            생성된 자막 파일 경로
        """
        all_segments = []
        current_offset = 0.0

        # ★ 유효성 검사
        num_audio = len(audio_files)
        num_scenes = len(scenes) if scenes else 0

        print(f"[STTSubtitleEngine] Processing {num_audio} audio files...")
        print(f"[STTSubtitleEngine] Scenes provided: {num_scenes}")
        print("[STTSubtitleEngine] Strategy: Whisper timing + Original narration text")

        if num_scenes > 0 and num_audio != num_scenes:
            print(f"[STTSubtitleEngine] ⚠️ Warning: audio({num_audio}) != scenes({num_scenes})")

        for idx, audio_info in enumerate(audio_files):
            audio_path = audio_info.get("path")
            audio_duration = audio_info.get("duration", 0)

            # ★ duration 유효성 검사
            if audio_duration <= 0:
                print(f"  Scene {idx}: ⚠️ Invalid duration ({audio_duration}), skipping")
                continue

            # 원본 나레이션 텍스트 가져오기
            original_text = ""
            if scenes and idx < len(scenes):
                original_text = getattr(scenes[idx], 'narration', '')

            # 오디오 파일이 없거나 없으면 fallback 처리
            if not audio_path or not os.path.exists(audio_path):
                # ★ 오디오가 없어도 원본 텍스트가 있으면 균등 분할로 자막 생성
                if original_text:
                    print(f"  Scene {idx}: No audio, using fallback timing for original text")
                    segments = self._fallback_split(original_text, audio_duration)
                    for seg in segments:
                        all_segments.append(SubtitleSegment(
                            text=seg.text,
                            start_time=seg.start_time + current_offset,
                            end_time=seg.end_time + current_offset
                        ))
                current_offset += audio_duration
                continue

            # 1) Whisper로 타이밍만 추출
            timings = self.extract_timing(audio_path)

            # 2) 원본 텍스트를 타이밍에 맞춰 정렬
            if original_text:
                segments = self.align_text_to_timing(original_text, timings, audio_duration)
                print(f"  Scene {idx}: {len(segments)} segments (original text + Whisper timing)")
            elif timings:
                # 원본이 없으면 Whisper 텍스트 사용 (fallback)
                segments = [
                    SubtitleSegment(
                        text=t.text,
                        start_time=t.start_time,
                        end_time=t.end_time
                    ) for t in timings
                ]
                print(f"  Scene {idx}: {len(segments)} segments (Whisper text - no original)")
            else:
                segments = []
                print(f"  Scene {idx}: ⚠️ No segments extracted (no timing, no original)")

            # 오프셋 적용
            for seg in segments:
                all_segments.append(SubtitleSegment(
                    text=seg.text,
                    start_time=seg.start_time + current_offset,
                    end_time=seg.end_time + current_offset
                ))

            current_offset += audio_duration

        print(f"[STTSubtitleEngine] Total segments: {len(all_segments)}, Total duration: {current_offset:.1f}s")

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
        """
        ASS 자막 파일 생성

        ★ 뉴스 스타일 자막:
        - 하단 중앙: 흰색 텍스트 + 검정 외곽선 + 반투명 배경
        - 깔끔하고 가독성 좋은 스타일
        """

        # 자막 마진 (하단 여백)
        margin_v = 50

        ass_content = f"""[Script Info]
Title: News Style Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; ★ 뉴스 스타일 - 하단 중앙, 반투명 박스 배경
Style: FullSub,NanumGothic,{self.full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,3,2.5,0,2,80,80,{margin_v},1
; ★ 깔끔한 외곽선 스타일 (배경 없음)
Style: CleanSub,NanumGothic,{self.full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,1,0,1,3,1.5,2,80,80,{margin_v},1
; ★ 강조 키워드 스타일 (노란색)
Style: Keyword,NanumGothic,{self.highlight_size},&H00FFFF00,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,1.5,2,80,80,{margin_v},1
; ★ 상단 제목 스타일
Style: Title,NanumGothic,{self.highlight_large_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,4,2,8,80,80,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        for seg in segments:
            start_str = self._format_ass_time(seg.start_time)
            end_str = self._format_ass_time(seg.end_time)

            # 텍스트 정리
            text = seg.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

            # ★ 부드러운 페이드 인/아웃 (150ms)
            fade_effect = "{\\fad(150,150)}"

            # 전체 자막 (Layer 0, 하단)
            if subtitle_mode in ["full", "full_highlight"]:
                ass_content += f"Dialogue: 0,{start_str},{end_str},FullSub,,0,0,0,,{fade_effect}{text}\n"

            # 깔끔한 스타일 (배경 없이 외곽선만)
            elif subtitle_mode == "clean":
                ass_content += f"Dialogue: 0,{start_str},{end_str},CleanSub,,0,0,0,,{fade_effect}{text}\n"

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
