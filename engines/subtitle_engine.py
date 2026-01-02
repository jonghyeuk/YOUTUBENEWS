"""
자막 생성 엔진 - 대본 기반 ASS (페이드 효과) + Whisper 옵션
TTS/자막 싱크를 위해 실제 오디오 길이 기반 타임코드 생성
"""
import os
import re
from typing import List, Optional, TYPE_CHECKING

from models.types import Script, AudioSegment
from config import FFMPEG_FILTERS

if TYPE_CHECKING:
    from engines.tts_engine import SubtitleSegment


class SubtitleEngine:
    """자막 생성 (대본 기반 / Whisper 타임스탬프)"""

    def __init__(self, use_whisper: bool = False):
        """
        Args:
            use_whisper: Whisper로 정확한 타임스탬프 추출 (True) 또는 대본 기반 계산 (False)
        """
        self.use_whisper = use_whisper
        # 페이드 효과 설정 (밀리초)
        self.fade_in = 300   # 0.3초 페이드인
        self.fade_out = 300  # 0.3초 페이드아웃

        if use_whisper:
            self._init_whisper()

    def _init_whisper(self):
        """Whisper 모델 초기화"""
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")
            print("[SubtitleEngine] Whisper 모델 로드 완료")
        except ImportError:
            print("[SubtitleEngine] Whisper 미설치, 대본 기반 모드로 전환")
            self.use_whisper = False

    def generate_srt(
        self,
        script: Script,
        audio_segments: List[AudioSegment],
        output_path: str,
        audio_path: Optional[str] = None,
        subtitle_segments: Optional[List["SubtitleSegment"]] = None
    ) -> str:
        """
        ASS 자막 파일 생성 (페이드 효과 포함)

        Args:
            script: Script 객체
            audio_segments: 씬별 오디오 세그먼트
            output_path: 출력 경로 (확장자는 .ass로 변경됨)
            audio_path: 오디오 파일 경로 (Whisper 사용 시 필요)
            subtitle_segments: TTS에서 반환한 자막용 세그먼트 (실제 오디오 길이 기반)

        Returns:
            ASS 파일 경로
        """
        # 확장자를 .ass로 변경
        ass_path = output_path.replace('.srt', '.ass')

        if self.use_whisper and audio_path:
            return self._generate_ass_whisper(audio_path, ass_path)
        elif subtitle_segments:
            # 실제 오디오 길이 기반 자막 생성 (권장)
            return self._generate_ass_from_subtitle_segments(subtitle_segments, ass_path)
        else:
            return self._generate_ass_text_based(script, audio_segments, ass_path)

    def _get_ass_header(self) -> str:
        """ASS 파일 헤더 생성 (스타일 포함)"""
        style = FFMPEG_FILTERS.get("subtitle_style", {})
        fontname = style.get("fontname", "NanumMyeongjo")
        # ASS 폰트 크기: config에서 가져옴
        fontsize = style.get("fontsize", 108)  # 시니어용: 1.5배 크게
        margin_v = style.get("margin_v", 100)  # 조금 위로
        margin_l = style.get("margin_l", 80)  # 좌측 여백
        margin_r = style.get("margin_r", 80)  # 우측 여백
        outline = style.get("outline", 5)  # 외곽선 더 두껍게
        shadow = style.get("shadow", 2)  # 그림자 더 진하게

        return f"""[Script Info]
Title: Auto-generated subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _generate_ass_whisper(self, audio_path: str, output_path: str) -> str:
        """Whisper로 정확한 타임스탬프 추출하여 ASS 생성"""
        import whisper

        print("[SubtitleEngine] Whisper 타임스탬프 추출 중...")

        result = self.whisper_model.transcribe(
            audio_path,
            language="ko",
            task="transcribe"
        )

        ass_content = self._get_ass_header()

        for segment in result["segments"]:
            start_time = segment["start"]
            end_time = segment["end"]
            text = segment["text"].strip()

            if text:
                ass_content += self._format_ass_dialogue(start_time, end_time, text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] Whisper ASS 저장: {output_path}")
        return output_path

    def _generate_ass_from_subtitle_segments(
        self,
        subtitle_segments: List["SubtitleSegment"],
        output_path: str
    ) -> str:
        """
        TTS에서 반환한 SubtitleSegment로 ASS 생성 (실제 오디오 길이 기반)

        이 방식이 권장됩니다:
        - TTS 텍스트와 자막 텍스트 분리 (SSML, 감정태그 제거됨)
        - 실제 오디오 길이 기반으로 정확한 타임코드 생성
        - 감정에 따른 속도 변화도 자동 반영
        """
        ass_content = self._get_ass_header()
        entry_count = 0

        for seg in subtitle_segments:
            if not seg.clean_text.strip():
                continue

            # 씬 텍스트를 문장 단위로 분할
            sentences = self._split_sentences(seg.clean_text)

            if not sentences:
                # 분할 안되면 전체를 하나로
                ass_content += self._format_ass_dialogue(
                    seg.start_time,
                    seg.end_time,
                    seg.clean_text.strip()
                )
                entry_count += 1
                continue

            # 문장별 시간 배분 (실제 오디오 길이 내에서)
            total_chars = sum(len(s) for s in sentences)
            current_time = seg.start_time

            for sentence in sentences:
                if not sentence.strip():
                    continue

                # 문장 길이 비율로 시간 계산 (실제 오디오 길이 기반)
                char_ratio = len(sentence) / total_chars if total_chars > 0 else 1
                duration = seg.duration * char_ratio

                start_time = current_time
                end_time = current_time + duration

                # ASS 다이얼로그 추가
                ass_content += self._format_ass_dialogue(
                    start_time,
                    end_time,
                    sentence.strip()
                )

                current_time = end_time
                entry_count += 1

        # 파일 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] 실제 오디오 길이 기반 ASS 저장: {output_path} ({entry_count} entries)")
        return output_path

    def _generate_ass_text_based(
        self,
        script: Script,
        audio_segments: List[AudioSegment],
        output_path: str
    ) -> str:
        """대본 텍스트 기반으로 ASS 생성 (시간 비례 계산 + 페이드 효과)"""
        ass_content = self._get_ass_header()
        entry_count = 0

        for scene, segment in zip(script.scenes, audio_segments):
            # 씬 텍스트를 문장 단위로 분할
            sentences = self._split_sentences(scene.text)

            if not sentences:
                continue

            # 씬 내에서 문장별 시간 배분
            scene_duration = segment.duration
            total_chars = sum(len(s) for s in sentences)

            current_time = segment.start_time

            for sentence in sentences:
                if not sentence.strip():
                    continue

                # 문장 길이 비율로 시간 계산
                char_ratio = len(sentence) / total_chars if total_chars > 0 else 1
                duration = scene_duration * char_ratio

                start_time = current_time
                end_time = current_time + duration

                # ASS 다이얼로그 추가
                ass_content += self._format_ass_dialogue(
                    start_time,
                    end_time,
                    sentence.strip()
                )

                current_time = end_time
                entry_count += 1

        # 파일 저장
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] 대본 기반 ASS 저장: {output_path} ({entry_count} entries)")
        return output_path

    def _split_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        # 한국어 문장 분리 (마침표, 물음표, 느낌표 기준)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]

    def _wrap_text_for_subtitle(self, text: str, max_chars: int = 20) -> str:
        """긴 텍스트를 자막용으로 줄바꿈 (\\N 사용)"""
        if len(text) <= max_chars:
            return text

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # 현재 줄 + 단어가 max_chars를 초과하면 줄바꿈
            if len(current_line) + len(word) + 1 > max_chars:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word
            else:
                current_line += " " + word if current_line else word

        if current_line:
            lines.append(current_line.strip())

        # 3줄 초과시 2줄로 제한 (화면 가독성)
        if len(lines) > 2:
            mid = len(text) // 2
            # 중간 지점 근처 공백에서 분할
            split_idx = text.rfind(" ", 0, mid + 10)
            if split_idx == -1:
                split_idx = text.find(" ", mid)
            if split_idx != -1:
                lines = [text[:split_idx].strip(), text[split_idx:].strip()]
            else:
                lines = [text[:mid], text[mid:]]

        return "\\N".join(lines)

    def _format_ass_dialogue(self, start: float, end: float, text: str) -> str:
        """ASS 다이얼로그 라인 생성 (페이드 효과 + 자동 줄바꿈 포함)"""
        start_str = self._format_ass_timestamp(start)
        end_str = self._format_ass_timestamp(end)

        # 긴 텍스트 줄바꿈 처리
        wrapped_text = self._wrap_text_for_subtitle(text, max_chars=20)

        # 페이드 효과: \fad(페이드인ms, 페이드아웃ms)
        fade_tag = f"{{\\fad({self.fade_in},{self.fade_out})}}"

        return f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{fade_tag}{wrapped_text}\n"

    def _format_ass_timestamp(self, seconds: float) -> str:
        """초를 ASS 타임스탬프 형식으로 변환 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)

        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    # 하위 호환성을 위한 SRT 메서드 유지
    def _format_srt_entry(self, num: int, start: float, end: float, text: str) -> str:
        """SRT 형식 엔트리 생성 (레거시)"""
        start_str = self._format_timestamp(start)
        end_str = self._format_timestamp(end)
        return f"{num}\n{start_str} --> {end_str}\n{text}\n"

    def _format_timestamp(self, seconds: float) -> str:
        """초를 SRT 타임스탬프 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
