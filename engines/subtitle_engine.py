"""
자막 생성 엔진 - 대본 기반 SRT 생성
"""
import re
from typing import List

from models.types import Script, AudioSegment


class SubtitleEngine:
    """대본 텍스트 기반 SRT 자막 생성"""

    def __init__(self, chars_per_second: float = 5.0):
        """
        Args:
            chars_per_second: 초당 글자 수 (읽기 속도 기반)
        """
        self.chars_per_second = chars_per_second

    def generate_srt(
        self,
        script: Script,
        audio_segments: List[AudioSegment],
        output_path: str
    ) -> str:
        """
        대본과 오디오 세그먼트를 기반으로 SRT 생성

        Args:
            script: Script 객체
            audio_segments: 씬별 오디오 세그먼트
            output_path: SRT 출력 경로

        Returns:
            SRT 파일 경로
        """
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

        print(f"[SubtitleEngine] SRT saved: {output_path} ({entry_num - 1} entries)")
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
