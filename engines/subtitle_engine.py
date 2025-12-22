"""
자막 생성 엔진 - 대본 기반 SRT + Whisper 타임스탬프 옵션
"""
import os
import re
from typing import List, Optional

from models.types import Script, AudioSegment


class SubtitleEngine:
    """자막 생성 (대본 기반 / Whisper 타임스탬프)"""

    def __init__(self, use_whisper: bool = False):
        """
        Args:
            use_whisper: Whisper로 정확한 타임스탬프 추출 (True) 또는 대본 기반 계산 (False)
        """
        self.use_whisper = use_whisper

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
        audio_path: Optional[str] = None
    ) -> str:
        """
        SRT 자막 파일 생성

        Args:
            script: Script 객체
            audio_segments: 씬별 오디오 세그먼트
            output_path: SRT 출력 경로
            audio_path: 오디오 파일 경로 (Whisper 사용 시 필요)

        Returns:
            SRT 파일 경로
        """
        if self.use_whisper and audio_path:
            return self._generate_srt_whisper(audio_path, output_path)
        else:
            return self._generate_srt_text_based(script, audio_segments, output_path)

    def _generate_srt_whisper(self, audio_path: str, output_path: str) -> str:
        """Whisper로 정확한 타임스탬프 추출하여 SRT 생성"""
        import whisper

        print("[SubtitleEngine] Whisper 타임스탬프 추출 중...")

        result = self.whisper_model.transcribe(
            audio_path,
            language="ko",
            task="transcribe"
        )

        srt_entries = []

        for i, segment in enumerate(result["segments"], 1):
            start_time = segment["start"]
            end_time = segment["end"]
            text = segment["text"].strip()

            if text:
                srt_entry = self._format_srt_entry(i, start_time, end_time, text)
                srt_entries.append(srt_entry)

        srt_content = "\n".join(srt_entries)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        print(f"[SubtitleEngine] Whisper SRT 저장: {output_path} ({len(srt_entries)} entries)")
        return output_path

    def _generate_srt_text_based(
        self,
        script: Script,
        audio_segments: List[AudioSegment],
        output_path: str
    ) -> str:
        """대본 텍스트 기반으로 SRT 생성 (시간 비례 계산)"""
        srt_entries = []
        entry_num = 1

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

                # SRT 엔트리 생성
                srt_entry = self._format_srt_entry(
                    entry_num,
                    start_time,
                    end_time,
                    sentence.strip()
                )
                srt_entries.append(srt_entry)

                current_time = end_time
                entry_num += 1

        # 파일 저장
        srt_content = "\n".join(srt_entries)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        print(f"[SubtitleEngine] 대본 기반 SRT 저장: {output_path} ({entry_num - 1} entries)")
        return output_path

    def _split_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        # 한국어 문장 분리 (마침표, 물음표, 느낌표 기준)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]

    def _format_srt_entry(
        self,
        num: int,
        start: float,
        end: float,
        text: str
    ) -> str:
        """SRT 형식 엔트리 생성"""
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
