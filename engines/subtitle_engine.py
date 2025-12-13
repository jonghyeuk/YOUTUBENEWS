"""
시니어 모드 전용: 하이라이트 감성 자막 엔진

시니어 특성:
- 청각 노화로 단어 인지 어려움
- 스마트폰 무음 시청 비율 높음
- 자막이 감정 몰입을 도와줌
- 메시지 기억률 상승

자막 스펙:
- 한 화면 1~3 단어 (감정 키워드 중심)
- 큰 글씨 (폰트 60~90)
- 부드러운 페이드 인/아웃
- 화면 중앙 고정
- 속도 느리게
"""

import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from anthropic import Anthropic


@dataclass
class HighlightSubtitle:
    """감성 하이라이트 자막 단위"""
    text: str           # 핵심 문장/소절 (원문 그대로)
    start_time: float   # 시작 시간 (초)
    end_time: float     # 종료 시간 (초)
    position: str       # "center" or "top"
    font_size: int      # 60~90


# ★ TTS 감정별 자막 타이밍 보정 계수
# TTS는 감정에 따라 속도가 달라짐:
# - 느린 나레이션(calm, sad): 자막이 빨리 나옴 → 늦추기 (계수 > 1.0)
# - 빠른 나레이션(excited): 자막이 늦게 나옴 → 앞당기기 (계수 < 1.0)
# - 보통 나레이션(warm): 기본 보정 유지
EMOTION_SUBTITLE_TIMING = {
    "warm": 1.0,       # 보통 속도 - 기본
    "calm": 1.03,      # 천천히 - 3% 늦추기
    "sad": 1.03,       # 천천히 - 3% 늦추기
    "serious": 1.02,   # 약간 느림 - 2% 늦추기
    "excited": 0.93,   # 빠름 - 7% 앞당기기
    "tense": 0.95,     # 긴박 - 5% 앞당기기
}


class SubtitleEngine:
    """
    시니어 맞춤 하이라이트 감성 자막 생성 엔진

    나레이션에서 핵심 감정 키워드를 추출하여
    큰 글씨의 감성 자막을 생성
    """

    # 자막 크기 프리셋 (px) - 실제 화면에서 잘 보이도록 큰 값 사용
    FONT_SIZE_PRESETS = {
        "small": 60,
        "medium": 80,
        "large": 100,
        "xlarge": 120,
    }

    def __init__(self, api_key: str = None, font_size_preset: str = "auto"):
        """
        자막 엔진 초기화

        Args:
            api_key: Claude API 키
            font_size_preset: 자막 크기 프리셋 (auto, small, medium, large, xlarge)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None

        # 자막 크기 설정
        self.font_size_preset = font_size_preset
        if font_size_preset == "auto":
            # auto: 해상도에 따라 자동 조절 (기본값 사용)
            self.default_font_size = 72
            self.min_font_size = 60
            self.max_font_size = 90
        else:
            # 프리셋 사용
            preset_size = self.FONT_SIZE_PRESETS.get(font_size_preset, 72)
            self.default_font_size = preset_size
            self.min_font_size = max(48, preset_size - 12)
            self.max_font_size = preset_size + 18

        self.fade_duration = 0.5  # 페이드 인/아웃 시간
        self.display_duration = 2.5  # 각 자막 표시 시간
        self.gap_duration = 0.3  # 자막 사이 간격

        # ★ 글자 크기에 따른 줄당 최대 글자수 (화면 너비 기준)
        # 한글 글자 실제 너비 = 폰트 크기 * 0.55 (경험적 수치)
        # 화면 너비의 85% 사용
        char_width = self.default_font_size * 0.55
        self.max_chars_per_line = max(18, int(1920 * 0.85 / char_width))

        print(f"[SubtitleEngine] 자막 크기: {font_size_preset} (기본 {self.default_font_size}px, 줄당 {self.max_chars_per_line}자)")

    def _clean_narrator_tags(self, text: str) -> str:
        """
        나레이션에서 화자 태그 및 대사 태그 제거
        [NARRATOR1], [NARRATOR2], [DIALOGUE], [DIALOGUE:M], [DIALOGUE:F] 등의 태그를 자막에서 제거
        (태그만 제거하고 내용은 유지)
        """
        # [NARRATOR1], [NARRATOR2], [NARRATOR] 등 모든 화자 태그 제거
        cleaned = re.sub(r'\[NARRATOR\d*\]\s*', '', text)
        # 혹시 다른 형태의 태그도 처리 (예: [화자1], [내레이터])
        cleaned = re.sub(r'\[화자\d*\]\s*', '', cleaned)
        cleaned = re.sub(r'\[내레이터\d*\]\s*', '', cleaned)
        # [DIALOGUE], [DIALOGUE:M], [DIALOGUE:F] 태그 제거 (내용은 유지)
        cleaned = re.sub(r'\[DIALOGUE(?::[MF])?\]', '', cleaned)
        cleaned = re.sub(r'\[/DIALOGUE\]', '', cleaned)
        # ★ "야담." 또는 "야담," 시작 제거 (채널명과 혼동 방지)
        if cleaned.startswith("야담.") or cleaned.startswith("야담,"):
            cleaned = cleaned[3:].strip()
        elif cleaned.startswith("야담 "):
            cleaned = cleaned[3:].strip()
        # 연속 공백 정리
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def extract_highlight_keywords(self, narration: str, scene_id: str = "") -> List[str]:
        """
        나레이션에서 감성 하이라이트 문장/소절 추출

        Args:
            narration: 나레이션 텍스트
            scene_id: 장면 ID (문맥 힌트용)

        Returns:
            핵심 문장/소절 리스트 (원문 그대로)
        """
        # 화자 태그 제거
        narration = self._clean_narrator_tags(narration)

        if self.client:
            return self._extract_with_llm(narration, scene_id)
        else:
            return self._extract_with_rules(narration)

    def _extract_with_llm(self, narration: str, scene_id: str) -> List[str]:
        """Claude를 사용하여 나레이션에서 핵심 문장/소절 추출 (원문 그대로)"""

        # ★ 대사가 있으면 대사를 우선적으로 추출
        has_dialogue = "[DIALOGUE]" in narration or "\"" in narration

        prompt = f"""다음 나레이션에서 화면에 크게 보여줄 핵심 문장 또는 소절을 추출하세요.

나레이션:
"{narration}"

장면 유형: {scene_id}

★★★ 핵심 규칙: 나레이션 원문을 그대로 추출 ★★★

{"★★★ 대사 우선 규칙 ★★★" if has_dialogue else ""}
{"이 나레이션에 대사(큰따옴표 안의 말)가 있다면 대사를 우선적으로 추출하세요!" if has_dialogue else ""}
{"대사는 이야기에서 가장 중요한 부분이므로 반드시 포함해야 합니다." if has_dialogue else ""}

1. 나레이션에서 감동적이거나 중요한 부분을 **원문 그대로** 추출
2. 대사(큰따옴표 안의 말)가 있으면 대사를 우선 추출
3. 한 소절, 한 문장, 또는 두 문장까지 가능
4. 절대로 단어만 추출하지 말 것 - 문장/소절 단위로 추출
5. 1~2개만 추출
6. 각 추출 문장은 10~50자 사이
7. ★ 나레이션에 나오는 순서대로 추출 (앞에 나오는 문장 먼저)

좋은 예시 (문장/소절 그대로):
- "또 왔구나, 작은 친구야."  (대사 예시)
- "그 시절이 정말 그립습니다"
- "아이가 처음으로 걸음마를 뗐습니다"

나쁜 예시 (피할 것):
- 단어만 추출: "그리움", "감동", "첫 걸음"
- 나레이션에 없는 내용 생성
- 너무 짧은 구문 (5자 미만)
- 나레이션 뒷부분 문장을 앞부분보다 먼저 추출

JSON 배열만 응답 (나레이션 순서대로):
["첫번째문장", "두번째문장"]"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            # JSON 파싱
            import json
            # 마크다운 코드블록 제거
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)

            sentences = json.loads(content)

            # ★ 유효한 자막 텍스트만 필터링
            sentences = [s for s in sentences if self._is_valid_subtitle(s)]

            print(f"[SubtitleEngine] Extracted highlight sentences: {sentences}")
            return sentences[:2]  # 최대 2개

        except Exception as e:
            print(f"[SubtitleEngine] LLM extraction failed: {e}")
            return self._extract_with_rules(narration)

    def _is_valid_subtitle(self, text: str) -> bool:
        """
        자막 텍스트가 유효한지 검증
        - "...", "....", 빈 문자열, 구두점만 있는 텍스트 제외
        """
        if not text or not isinstance(text, str):
            return False

        # 공백 제거 후 검사
        cleaned = text.strip()

        # 빈 문자열 제외
        if not cleaned:
            return False

        # 길이 검사 (10~60자)
        if not (10 <= len(cleaned) <= 60):
            return False

        # 구두점/특수문자만 있는 텍스트 제외
        # 한글, 영문, 숫자가 최소 5자 이상 있어야 함
        meaningful_chars = re.sub(r'[^\w가-힣a-zA-Z0-9]', '', cleaned)
        if len(meaningful_chars) < 5:
            return False

        # "..." 패턴 제외
        if re.match(r'^[\.\s]+$', cleaned):
            return False

        return True

    def _extract_with_rules(self, narration: str) -> List[str]:
        """규칙 기반 문장/소절 추출 (fallback)"""

        sentences = []

        # 마침표, 느낌표, 물음표로 문장 분리
        split_sentences = re.split(r'[.!?]', narration)

        for sent in split_sentences:
            sent = sent.strip()
            # ★ 유효한 자막인지 검증
            if self._is_valid_subtitle(sent):
                sentences.append(sent)

        # 문장이 부족하면 쉼표로 소절 분리
        if len(sentences) < 1:
            clauses = re.split(r'[,，]', narration)
            for clause in clauses:
                clause = clause.strip()
                if self._is_valid_subtitle(clause):
                    sentences.append(clause)

        # 여전히 부족하면 전체 나레이션에서 앞부분 추출
        if len(sentences) < 1 and len(narration) >= 10:
            # 나레이션 앞부분 40자까지
            first_part = narration[:40].strip()
            if self._is_valid_subtitle(first_part):
                sentences.append(first_part)

        return sentences[:2]  # 최대 2개

    def generate_scene_subtitles(self,
                                  narration: str,
                                  scene_id: str,
                                  scene_duration: float,
                                  start_offset: float = 0,
                                  emotion_tag: str = "warm") -> List[HighlightSubtitle]:
        """
        한 장면에 대한 하이라이트 자막 생성
        나레이션 내 위치 기반으로 타이밍 계산 (TTS 싱크 개선)

        ★ 30초 청킹: 긴 씬은 30초 단위로 나눠서 타이밍 드리프트 방지

        Args:
            narration: 나레이션 텍스트
            scene_id: 장면 ID
            scene_duration: 장면 길이 (초)
            start_offset: 전체 영상에서의 시작 위치
            emotion_tag: 감정 태그 (타이밍 보정용)

        Returns:
            HighlightSubtitle 리스트
        """
        keywords = self.extract_highlight_keywords(narration, scene_id)

        if not keywords:
            return []

        subtitles = []
        clean_narration = self._clean_narrator_tags(narration)
        total_chars = len(clean_narration)

        if total_chars == 0:
            return []

        # ★ 15초 청킹: 긴 씬은 15초 단위로 분할하여 타이밍 드리프트 방지
        CHUNK_DURATION = 15.0  # 청크 단위 (초)
        margin = 0.3

        # 씬이 15초 이하면 기존 방식
        if scene_duration <= CHUNK_DURATION:
            return self._generate_subtitles_for_chunk(
                keywords, clean_narration, total_chars,
                scene_duration, start_offset, margin, emotion_tag
            )

        # ★ 15초 초과 씬: 청크 단위로 분할
        num_chunks = int((scene_duration + CHUNK_DURATION - 1) // CHUNK_DURATION)
        chars_per_chunk = total_chars // num_chunks

        # ★ 키워드를 나레이션 내 위치 기반으로 청크에 할당
        # 먼저 각 키워드의 위치를 찾고, 해당 위치가 속한 청크에 할당
        keyword_positions = []
        for keyword in keywords:
            pos = clean_narration.find(keyword)
            if pos == -1:
                pos = total_chars // 2  # 못 찾으면 중간으로
            keyword_positions.append((keyword, pos))

        # 위치순으로 정렬
        keyword_positions.sort(key=lambda x: x[1])

        all_subtitles = []

        for chunk_idx in range(num_chunks):
            chunk_start = start_offset + (chunk_idx * CHUNK_DURATION)
            chunk_end = min(chunk_start + CHUNK_DURATION, start_offset + scene_duration)
            chunk_duration = chunk_end - chunk_start

            # 해당 청크의 나레이션 범위 (글자 인덱스)
            char_start = chunk_idx * chars_per_chunk
            char_end = min((chunk_idx + 1) * chars_per_chunk, total_chars) if chunk_idx < num_chunks - 1 else total_chars
            chunk_narration = clean_narration[char_start:char_end]
            chunk_chars = len(chunk_narration)

            # ★ 해당 청크 범위 내에 위치한 키워드만 선택
            chunk_keywords = [kw for kw, pos in keyword_positions if char_start <= pos < char_end]

            if not chunk_keywords or chunk_chars == 0:
                continue

            # 청크 내에서 자막 생성 (각 청크 내에서 타이밍 재계산)
            chunk_subtitles = self._generate_subtitles_for_chunk(
                chunk_keywords, chunk_narration, chunk_chars,
                chunk_duration, chunk_start, margin, emotion_tag,
                char_offset=char_start
            )

            # 이전 청크 마지막 자막과 겹침 방지
            if all_subtitles and chunk_subtitles:
                last_end = all_subtitles[-1].end_time
                first_start = chunk_subtitles[0].start_time
                if first_start < last_end + self.gap_duration:
                    # 첫 자막 시작 시간 조정
                    time_shift = (last_end + self.gap_duration) - first_start
                    chunk_subtitles[0] = HighlightSubtitle(
                        text=chunk_subtitles[0].text,
                        start_time=chunk_subtitles[0].start_time + time_shift,
                        end_time=min(chunk_subtitles[0].end_time + time_shift, chunk_end - margin),
                        position=chunk_subtitles[0].position,
                        font_size=chunk_subtitles[0].font_size
                    )

            all_subtitles.extend(chunk_subtitles)

        return all_subtitles

    def _generate_subtitles_for_chunk(self,
                                      keywords: List[str],
                                      chunk_narration: str,
                                      chunk_chars: int,
                                      chunk_duration: float,
                                      chunk_start: float,
                                      margin: float,
                                      emotion_tag: str,
                                      char_offset: int = 0) -> List[HighlightSubtitle]:
        """
        청크 내에서 자막 생성 (내부 헬퍼)

        Args:
            keywords: 이 청크에 할당된 키워드
            chunk_narration: 청크 내 나레이션 텍스트
            chunk_chars: 청크 나레이션 글자수
            chunk_duration: 청크 길이 (초)
            chunk_start: 청크 시작 시간 (전체 영상 기준)
            margin: 앞뒤 여백
            emotion_tag: 감정 태그
            char_offset: 원본 나레이션에서의 시작 위치 (키워드 검색용)

        Returns:
            HighlightSubtitle 리스트
        """
        subtitles = []
        usable_duration = chunk_duration - (margin * 2)

        for idx, keyword in enumerate(keywords):
            # 청크 나레이션에서 키워드 위치 찾기
            keyword_pos = chunk_narration.find(keyword)
            if keyword_pos == -1:
                # 키워드를 찾지 못하면 균등 분배
                if len(keywords) == 1:
                    position_ratio = 0.3
                else:
                    position_ratio = idx / (len(keywords) - 1) * 0.6 + 0.2
            else:
                # 청크 내 위치를 시간 비율로 변환
                position_ratio = keyword_pos / chunk_chars

            # ★ 감정 기반 TTS 속도 보정
            emotion_factor = EMOTION_SUBTITLE_TIMING.get(emotion_tag, 1.0)
            position_ratio = max(0, min(1.0, position_ratio * emotion_factor))

            # 글자수 기반 display duration 계산
            # ★ 최소 3초로 늘림 (너무 빨리 사라지는 문제 해결)
            keyword_len = len(keyword)
            calculated_duration = max(3.0, min(5.0, keyword_len * 0.15))

            # ★ 인트로(첫 청크)는 자막을 더 오래 보여줌 (4초 이상)
            # chunk_start가 0이거나 1초 미만이면 인트로로 판단
            if chunk_start < 1.0:
                calculated_duration = max(4.0, min(6.0, keyword_len * 0.18))
                print(f"    [자막] ★ 인트로 자막 - 표시 시간 늘림: {calculated_duration:.1f}초")

            # 청크 길이가 짧아도 최소 2.5초는 보장
            if chunk_duration < 15:
                calculated_duration = max(2.5, min(calculated_duration, chunk_duration * 0.4))

            # 시작 시간 계산 (청크 내 기준)
            start_time = chunk_start + margin + (position_ratio * usable_duration)

            # 끝 시간이 청크를 넘지 않도록 조정
            end_time = min(start_time + calculated_duration, chunk_start + chunk_duration - margin)

            # 이전 자막과 겹치지 않도록 조정
            if subtitles:
                last_end = subtitles[-1].end_time
                if start_time < last_end + self.gap_duration:
                    start_time = last_end + self.gap_duration
                    end_time = min(start_time + calculated_duration, chunk_start + chunk_duration - margin)

            # 유효한 시간 범위인지 확인
            if end_time <= start_time or start_time >= chunk_start + chunk_duration:
                continue

            # 폰트 크기 결정 (첫 번째와 마지막은 더 크게)
            if idx == 0 or idx == len(keywords) - 1:
                font_size = self.max_font_size
            else:
                font_size = self.default_font_size

            # 위치 결정 (항상 가운데)
            position = "center"

            subtitle = HighlightSubtitle(
                text=keyword,
                start_time=start_time,
                end_time=end_time,
                position=position,
                font_size=font_size
            )
            subtitles.append(subtitle)

            # ★ 디버그: 자막 타이밍 로그
            print(f"    [자막] \"{keyword[:20]}{'...' if len(keyword) > 20 else ''}\" → {start_time:.1f}s ~ {end_time:.1f}s")

        return subtitles

    def generate_ass_subtitle(self,
                               subtitles: List[HighlightSubtitle],
                               video_width: int = 1920,
                               video_height: int = 1080) -> str:
        """
        ASS 자막 파일 내용 생성

        ASS 형식은 FFmpeg에서 스타일링(폰트 크기, 페이드 등) 지원

        Args:
            subtitles: HighlightSubtitle 리스트
            video_width: 영상 너비
            video_height: 영상 높이

        Returns:
            ASS 자막 파일 내용
        """
        # ASS 헤더
        ass_content = f"""[Script Info]
Title: Senior Highlight Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Center,Nanum Pen Script,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1
Style: Top,Nanum Pen Script,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,8,50,50,50,1
Style: CenterLarge,Nanum Pen Script,90,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,100,1
Style: TopLarge,Nanum Pen Script,90,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,8,50,50,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # 자막 이벤트 추가
        for sub in subtitles:
            # 시간 포맷 변환 (H:MM:SS.cc)
            start_str = self._format_ass_time(sub.start_time)
            end_str = self._format_ass_time(sub.end_time)

            # 스타일 선택
            if sub.font_size >= 85:
                style = "CenterLarge" if sub.position == "center" else "TopLarge"
            else:
                style = "Center" if sub.position == "center" else "Top"

            # 페이드 효과 (밀리초 단위)
            fade_ms = int(self.fade_duration * 1000)
            fade_effect = f"{{\\fad({fade_ms},{fade_ms})}}"

            # 텍스트 이스케이프
            text = sub.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

            ass_content += f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{fade_effect}{text}\n"

        return ass_content

    def _format_ass_time(self, seconds: float) -> str:
        """초를 ASS 시간 포맷으로 변환 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def save_ass_file(self, subtitles: List[HighlightSubtitle],
                      output_path: str,
                      video_width: int = 1920,
                      video_height: int = 1080) -> str:
        """
        ASS 자막 파일 저장

        Args:
            subtitles: HighlightSubtitle 리스트
            output_path: 출력 파일 경로
            video_width: 영상 너비
            video_height: 영상 높이

        Returns:
            저장된 파일 경로
        """
        ass_content = self.generate_ass_subtitle(subtitles, video_width, video_height)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] Saved ASS subtitle: {output_path}")
        return output_path

    def generate_full_subtitles(self,
                                 scenes: List,
                                 audio_files: List[Dict],
                                 output_path: str,
                                 video_width: int = 1920,
                                 video_height: int = 1080) -> str:
        """
        전체 자막 생성 (나레이션 전문)

        시니어를 위해 큰 글씨와 적절한 줄바꿈 적용

        Args:
            scenes: Scene 리스트
            audio_files: 오디오 파일 정보 리스트
            output_path: 출력 파일 경로
            video_width: 영상 너비
            video_height: 영상 높이

        Returns:
            저장된 파일 경로
        """
        # ASS 헤더 - 전체 자막용 스타일 (프리셋 크기 적용)
        # 전체 자막은 하이라이트보다 약간 작게 (80%)
        full_sub_size = max(48, int(self.default_font_size * 0.9))
        ass_content = f"""[Script Info]
Title: Senior Full Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,NanumGothic,{full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,50,50,30,1
Style: FullSub,NanumGothic,{full_sub_size + 4},&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,3,3,3,2,60,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        current_time = 0.0

        for idx, scene in enumerate(scenes):
            # 장면 시간 계산
            if idx < len(audio_files):
                scene_duration = audio_files[idx].get("duration", scene.duration_sec)
            else:
                scene_duration = scene.duration_sec

            narration = scene.narration.strip()

            if not narration:
                current_time += scene_duration
                continue

            # 화자 태그 제거 ([NARRATOR1], [NARRATOR2] 등)
            narration = self._clean_narrator_tags(narration)

            # 나레이션을 문장 단위로 분할
            sentences = self._split_narration_to_sentences(narration)

            if not sentences:
                current_time += scene_duration
                continue

            # ★ TTS 싱크 개선: 문장 길이(글자수)에 비례하여 시간 배분
            # 글자수가 많을수록 말하는 시간이 길어짐
            char_counts = [len(s) for s in sentences]
            total_chars = sum(char_counts)

            if total_chars == 0:
                current_time += scene_duration
                continue

            # 각 문장의 시간 비율 계산
            sentence_durations = [(c / total_chars) * scene_duration for c in char_counts]

            # 누적 시작 시간 계산
            accumulated_time = 0.0
            for sent_idx, sentence in enumerate(sentences):
                start_time = current_time + accumulated_time
                end_time = start_time + sentence_durations[sent_idx]
                accumulated_time += sentence_durations[sent_idx]

                # 시간 포맷 변환
                start_str = self._format_ass_time(start_time)
                end_str = self._format_ass_time(end_time)

                # 페이드 효과
                fade_ms = 300
                fade_effect = f"{{\\fad({fade_ms},{fade_ms})}}"

                # 텍스트 이스케이프
                text = sentence.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                # 긴 문장은 줄바꿈 (글자 크기에 따라 동적 조정)
                if len(text) > self.max_chars_per_line:
                    text = self._add_line_breaks(text, max_chars=self.max_chars_per_line)

                ass_content += f"Dialogue: 0,{start_str},{end_str},FullSub,,0,0,0,,{fade_effect}{text}\n"

            current_time += scene_duration

        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] Saved full subtitle: {output_path}")
        return output_path

    def _split_narration_to_sentences(self, narration: str) -> List[str]:
        """나레이션을 문장 단위로 분할"""
        # 문장 분리 (마침표, 물음표, 느낌표 기준)
        sentences = re.split(r'([.!?])\s*', narration)

        # 분리된 구두점을 문장에 다시 붙이기
        result = []
        i = 0
        while i < len(sentences):
            sent = sentences[i].strip()
            if sent:
                # 다음 요소가 구두점이면 붙이기
                if i + 1 < len(sentences) and sentences[i + 1] in '.!?':
                    sent += sentences[i + 1]
                    i += 1
                result.append(sent)
            i += 1

        return result

    def _add_line_breaks(self, text: str, max_chars: int = 25, max_lines: int = 2) -> str:
        """긴 텍스트에 줄바꿈 추가 (ASS 형식: \\N), 최대 2줄 제한"""
        # 전체 텍스트가 max_chars 이하면 그대로 반환
        if len(text) <= max_chars:
            return text

        # 2줄에 맞게 분할
        total_allowed = max_chars * max_lines
        if len(text) > total_allowed:
            text = text[:total_allowed - 3] + "..."

        # 중간 지점에서 공백을 찾아 분할
        mid = len(text) // 2
        # 중간 근처에서 공백 찾기
        split_pos = -1
        for offset in range(min(15, mid)):
            if mid + offset < len(text) and text[mid + offset] == ' ':
                split_pos = mid + offset
                break
            if mid - offset >= 0 and text[mid - offset] == ' ':
                split_pos = mid - offset
                break

        if split_pos > 0:
            line1 = text[:split_pos].strip()
            line2 = text[split_pos:].strip()
            return f"{line1}\\N{line2}"
        else:
            # 공백이 없으면 그냥 중간에서 자르기
            return f"{text[:mid]}\\N{text[mid:]}"

    def generate_full_highlight_subtitles(self,
                                          scenes: List,
                                          audio_files: List[Dict],
                                          output_path: str,
                                          video_width: int = 1920,
                                          video_height: int = 1080) -> str:
        """
        전체 자막 + 하이라이트 감성 자막 동시 생성

        - 하단: 전체 나레이션 자막 (작은 글씨)
        - 중앙: 하이라이트 감성 키워드 (큰 글씨, 페이드)

        Args:
            scenes: Scene 리스트
            audio_files: 오디오 파일 정보 리스트
            output_path: 출력 파일 경로
            video_width: 영상 너비
            video_height: 영상 높이

        Returns:
            저장된 파일 경로
        """
        # ASS 헤더 - 전체 자막용 + 하이라이트용 스타일 모두 포함
        # 프리셋 크기 적용
        full_sub_size = max(48, int(self.default_font_size * 0.85))
        highlight_size = self.default_font_size
        highlight_large_size = self.max_font_size
        ass_content = f"""[Script Info]
Title: Senior Full + Highlight Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
; 하단 전체 자막 스타일 (Layer 0) - 고딕
Style: FullSub,NanumGothic,{full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,3,3,3,2,60,60,40,1
; 중앙 하이라이트 스타일 (Layer 1 - 더 위에 표시) - 손글씨
Style: Highlight,Nanum Pen Script,{highlight_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1
Style: HighlightLarge,Nanum Pen Script,{highlight_large_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        current_time = 0.0

        # ★ 디버그: audio_files duration 합계 출력
        total_audio_duration = sum(af.get("duration", 0) for af in audio_files)
        print(f"[SubtitleEngine] ★ 오디오 총 길이: {total_audio_duration:.1f}초 ({total_audio_duration/60:.1f}분)")

        for idx, scene in enumerate(scenes):
            # 장면 시간 계산
            if idx < len(audio_files):
                scene_duration = audio_files[idx].get("duration", scene.duration_sec)
                audio_dur = audio_files[idx].get("duration", 0)
                # ★ 디버그: scene.duration_sec vs audio duration 비교
                if abs(scene.duration_sec - audio_dur) > 1:
                    print(f"[SubtitleEngine] ⚠️ Scene {idx}: script={scene.duration_sec:.0f}s vs audio={audio_dur:.1f}s")
            else:
                scene_duration = scene.duration_sec

            narration = scene.narration.strip()

            if not narration:
                current_time += scene_duration
                continue

            # 화자 태그 제거 ([NARRATOR1], [NARRATOR2] 등)
            narration = self._clean_narrator_tags(narration)

            # ★ 감정 기반 타이밍 보정 계수
            emotion_tag = getattr(scene, 'emotion_tag', 'warm')
            emotion_timing_factor = EMOTION_SUBTITLE_TIMING.get(emotion_tag, 1.0)

            # ===== 1. 전체 자막 생성 (Layer 0, 하단) =====
            sentences = self._split_narration_to_sentences(narration)

            if sentences:
                # ★ TTS 싱크 개선: 글자수 비례 시간 배분 + TTS 속도 보정
                char_counts = [len(s) for s in sentences]
                total_chars = sum(char_counts)

                if total_chars > 0:
                    # 기본 배분
                    sentence_durations = [(c / total_chars) * scene_duration for c in char_counts]

                    # ★ TTS 속도 보정: 앞 문장은 짧게, 뒷 문장은 길게 (TTS가 앞을 빠르게 읽는 경향 보정)
                    # 첫 문장 -5%, 마지막 문장 +5%, 중간은 선형 보간
                    if len(sentences) > 1:
                        for i in range(len(sentence_durations)):
                            ratio = i / (len(sentences) - 1)  # 0.0 ~ 1.0
                            adjustment = 0.95 + (ratio * 0.1)  # 0.95 ~ 1.05
                            sentence_durations[i] *= adjustment
                        # 총 합이 scene_duration이 되도록 정규화
                        total_duration = sum(sentence_durations)
                        if total_duration > 0:
                            sentence_durations = [d * scene_duration / total_duration for d in sentence_durations]
                else:
                    sentence_durations = [scene_duration / len(sentences)] * len(sentences)

                accumulated_time = 0.0
                for sent_idx, sentence in enumerate(sentences):
                    # ★ 감정 기반 타이밍 보정 적용
                    adjusted_offset = accumulated_time * emotion_timing_factor
                    start_time = current_time + max(0, min(adjusted_offset, scene_duration - 0.5))
                    end_time = start_time + sentence_durations[sent_idx]
                    accumulated_time += sentence_durations[sent_idx]

                    start_str = self._format_ass_time(start_time)
                    end_str = self._format_ass_time(min(end_time, current_time + scene_duration))

                    fade_effect = "{\\fad(300,300)}"
                    text = sentence.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                    # ★ 글자 크기에 따른 동적 줄바꿈 (하드코딩 제거)
                    if len(text) > self.max_chars_per_line:
                        text = self._add_line_breaks(text, max_chars=self.max_chars_per_line)

                    # Layer 0: 전체 자막
                    ass_content += f"Dialogue: 0,{start_str},{end_str},FullSub,,0,0,0,,{fade_effect}{text}\n"

            # ===== 2. 하이라이트 감성 자막 생성 (Layer 1, 중앙) =====
            highlight_subs = self.generate_scene_subtitles(
                narration=narration,
                scene_id=scene.scene_id,
                scene_duration=scene_duration,
                start_offset=current_time,
                emotion_tag=emotion_tag  # ★ 감정 기반 타이밍 보정
            )

            for sub in highlight_subs:
                start_str = self._format_ass_time(sub.start_time)
                end_str = self._format_ass_time(sub.end_time)

                # 스타일 선택 (큰 글씨는 노란색 하이라이트)
                style = "HighlightLarge" if sub.font_size >= 85 else "Highlight"

                fade_ms = int(self.fade_duration * 1000)
                fade_effect = f"{{\\fad({fade_ms},{fade_ms})}}"

                text = sub.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                # Layer 1: 하이라이트 자막 (위에 표시)
                ass_content += f"Dialogue: 1,{start_str},{end_str},{style},,0,0,0,,{fade_effect}{text}\n"

            current_time += scene_duration

        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        print(f"[SubtitleEngine] Saved full+highlight subtitle: {output_path}")
        return output_path

    def generate_single_scene_subtitle(self,
                                        scene,
                                        scene_duration: float,
                                        output_path: str,
                                        video_width: int = 1920,
                                        video_height: int = 1080,
                                        subtitle_mode: str = "full_highlight") -> str:
        """
        ★ 단일 씬용 자막 생성 (싱크 오차 방지)

        각 씬에 대해 개별적으로 자막을 생성하여
        타이밍이 0부터 scene_duration까지로 설정됨.
        클립별로 자막을 번인한 후 합치면 싱크 오차가 누적되지 않음.

        Args:
            scene: Scene 객체
            scene_duration: 씬 길이 (초, 실제 오디오 길이 사용)
            output_path: 출력 파일 경로
            video_width: 영상 너비
            video_height: 영상 높이
            subtitle_mode: 자막 모드 ("full", "highlight", "full_highlight")

        Returns:
            저장된 파일 경로
        """
        narration = scene.narration.strip()
        if not narration:
            return None

        # 화자 태그 제거
        narration = self._clean_narrator_tags(narration)

        # ★ 감정 기반 자막 타이밍 보정 계수 가져오기
        emotion_tag = getattr(scene, 'emotion_tag', 'warm')
        emotion_timing_factor = EMOTION_SUBTITLE_TIMING.get(emotion_tag, 1.0)
        if emotion_timing_factor != 1.0:
            print(f"  [자막 타이밍] 감정={emotion_tag} → 보정계수={emotion_timing_factor}")

        # ASS 헤더
        full_sub_size = max(48, int(self.default_font_size * 0.85))
        highlight_size = self.default_font_size
        highlight_large_size = self.max_font_size

        ass_content = f"""[Script Info]
Title: Scene Subtitle
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: FullSub,NanumGothic,{full_sub_size},&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,3,3,3,2,60,60,40,1
Style: Highlight,Nanum Pen Script,{highlight_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1
Style: HighlightLarge,Nanum Pen Script,{highlight_large_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,5,50,50,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # ===== 1. 전체 자막 (하단) - full 또는 full_highlight 모드에서만 =====
        if subtitle_mode in ["full", "full_highlight"]:
            sentences = self._split_narration_to_sentences(narration)

            if sentences:
                char_counts = [len(s) for s in sentences]
                total_chars = sum(char_counts)

                if total_chars > 0:
                    # 기본 배분
                    sentence_durations = [(c / total_chars) * scene_duration for c in char_counts]

                    # ★ TTS 속도 보정: 앞 문장은 짧게, 뒷 문장은 길게
                    if len(sentences) > 1:
                        for i in range(len(sentence_durations)):
                            ratio = i / (len(sentences) - 1)
                            adjustment = 0.95 + (ratio * 0.1)  # 0.95 ~ 1.05
                            sentence_durations[i] *= adjustment
                        total_duration = sum(sentence_durations)
                        if total_duration > 0:
                            sentence_durations = [d * scene_duration / total_duration for d in sentence_durations]
                else:
                    sentence_durations = [scene_duration / len(sentences)] * len(sentences)

                accumulated_time = 0.0
                for sent_idx, sentence in enumerate(sentences):
                    # ★ 감정 기반 타이밍 보정 적용
                    # 느린 나레이션: 자막 시작 늦추기 (factor > 1.0)
                    # 빠른 나레이션: 자막 시작 앞당기기 (factor < 1.0)
                    adjusted_start = accumulated_time * emotion_timing_factor
                    start_time = max(0, min(adjusted_start, scene_duration - 0.5))
                    end_time = start_time + sentence_durations[sent_idx]
                    accumulated_time += sentence_durations[sent_idx]

                    start_str = self._format_ass_time(start_time)
                    end_str = self._format_ass_time(min(end_time, scene_duration))

                    fade_effect = "{\\fad(300,300)}"
                    text = sentence.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                    if len(text) > self.max_chars_per_line:
                        text = self._add_line_breaks(text, max_chars=self.max_chars_per_line)

                    ass_content += f"Dialogue: 0,{start_str},{end_str},FullSub,,0,0,0,,{fade_effect}{text}\n"

        # ===== 2. 하이라이트 자막 (중앙) - highlight 또는 full_highlight 모드에서만 =====
        if subtitle_mode in ["highlight", "full_highlight"]:
            highlight_subs = self.generate_scene_subtitles(
                narration=narration,
                scene_id=scene.scene_id,
                scene_duration=scene_duration,
                start_offset=0,  # ★ 항상 0부터 시작
                emotion_tag=emotion_tag  # ★ 감정 기반 타이밍 보정
            )

            for sub in highlight_subs:
                start_str = self._format_ass_time(sub.start_time)
                end_str = self._format_ass_time(sub.end_time)

                style = "HighlightLarge" if sub.font_size >= 85 else "Highlight"

                fade_ms = int(self.fade_duration * 1000)
                fade_effect = f"{{\\fad({fade_ms},{fade_ms})}}"

                text = sub.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                ass_content += f"Dialogue: 1,{start_str},{end_str},{style},,0,0,0,,{fade_effect}{text}\n"

        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        return output_path
