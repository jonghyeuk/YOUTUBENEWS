"""
대본 추출 엔진 - YouTube 자막/트랜스크립트 추출 및 번역
"""
import os
import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    """자막 세그먼트"""
    text: str
    start: float
    duration: float


@dataclass
class ExtractedScript:
    """추출된 대본"""
    video_id: str
    original_language: str
    original_text: str
    translated_text: str = None
    segments: List[TranscriptSegment] = None


class TranscriptEngine:
    """YouTube 대본 추출 및 번역 엔진"""

    def __init__(self):
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            self.transcript_api = YouTubeTranscriptApi
            print("[TranscriptEngine] YouTube Transcript API 초기화 완료")
        except ImportError:
            self.transcript_api = None
            print("[TranscriptEngine] Warning: youtube_transcript_api 미설치")

        # 번역용 OpenAI 클라이언트
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def extract_transcript(
        self,
        video_id: str,
        languages: List[str] = None
    ) -> ExtractedScript:
        """
        YouTube 영상에서 자막/트랜스크립트 추출

        Args:
            video_id: YouTube 영상 ID (URL에서 추출)
            languages: 선호 언어 리스트 (예: ["ko", "en", "ja"])

        Returns:
            ExtractedScript 객체
        """
        if not self.transcript_api:
            raise RuntimeError("youtube_transcript_api가 설치되지 않았습니다")

        # URL에서 video_id 추출
        video_id = self._extract_video_id(video_id)

        if languages is None:
            languages = ["ko", "en", "ja", "zh"]

        try:
            # 자막 리스트 조회
            transcript_list = self.transcript_api.list_transcripts(video_id)

            # 수동 자막 우선, 없으면 자동 생성 자막
            transcript = None
            detected_lang = None

            # 수동 자막 시도
            for lang in languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    detected_lang = lang
                    break
                except:
                    continue

            # 자동 생성 자막 시도
            if not transcript:
                for lang in languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        detected_lang = lang
                        break
                    except:
                        continue

            if not transcript:
                raise RuntimeError(f"사용 가능한 자막이 없습니다: {video_id}")

            # 자막 데이터 가져오기
            transcript_data = transcript.fetch()

            # 세그먼트 변환
            segments = [
                TranscriptSegment(
                    text=seg["text"],
                    start=seg["start"],
                    duration=seg["duration"]
                )
                for seg in transcript_data
            ]

            # 전체 텍스트
            full_text = " ".join([seg.text for seg in segments])
            full_text = self._clean_text(full_text)

            print(f"[TranscriptEngine] 추출 완료: {len(segments)}개 세그먼트, 언어: {detected_lang}")

            return ExtractedScript(
                video_id=video_id,
                original_language=detected_lang,
                original_text=full_text,
                segments=segments
            )

        except Exception as e:
            print(f"[TranscriptEngine] 추출 실패: {e}")
            raise

    def translate_script(
        self,
        script: ExtractedScript,
        target_language: str = "ko"
    ) -> ExtractedScript:
        """
        추출된 대본 번역

        Args:
            script: ExtractedScript 객체
            target_language: 목표 언어 (기본: 한국어)

        Returns:
            번역된 ExtractedScript
        """
        if script.original_language == target_language:
            script.translated_text = script.original_text
            return script

        if not self.openai_key:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)

        language_names = {
            "ko": "한국어",
            "en": "영어",
            "ja": "일본어",
            "zh": "중국어"
        }
        target_name = language_names.get(target_language, target_language)

        # 긴 텍스트는 청크로 분할
        chunks = self._split_into_chunks(script.original_text, max_chars=3000)
        translated_chunks = []

        for i, chunk in enumerate(chunks):
            print(f"[TranscriptEngine] 번역 중... {i+1}/{len(chunks)}")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"당신은 전문 번역가입니다. 다음 텍스트를 {target_name}로 자연스럽게 번역해주세요. 원문의 뉘앙스와 감정을 살려주세요."
                    },
                    {
                        "role": "user",
                        "content": chunk
                    }
                ],
                temperature=0.3
            )

            translated_chunks.append(response.choices[0].message.content)

        script.translated_text = " ".join(translated_chunks)
        print(f"[TranscriptEngine] 번역 완료: {len(script.translated_text)}자")

        return script

    def analyze_structure(self, script: ExtractedScript) -> Dict:
        """
        대본 구조 분석 (GPT 활용)
        - 훅(Hook) 포인트
        - 전개 방식
        - 감정 고조 지점
        - 클라이맥스

        Returns:
            구조 분석 결과
        """
        if not self.openai_key:
            return {"error": "OPENAI_API_KEY 없음"}

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)

        text = script.translated_text or script.original_text

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """당신은 콘텐츠 분석 전문가입니다. 주어진 대본을 분석하여 다음 요소를 JSON으로 추출해주세요:

1. hook: 시청자를 사로잡는 첫 문장/장면 (어떤 기법 사용?)
2. emotional_points: 감정이 고조되는 핵심 장면들 (리스트)
3. plot_structure: 이야기 구조 (도입-전개-위기-클라이맥스-결말)
4. key_message: 핵심 메시지/교훈
5. viral_elements: 바이럴 요소 (공감, 분노, 감동 등)
6. recommended_scenes: 영상화할 때 필요한 주요 장면 (5-8개)"""
                },
                {
                    "role": "user",
                    "content": f"다음 대본을 분석해주세요:\n\n{text[:4000]}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        import json
        analysis = json.loads(response.choices[0].message.content)

        print("[TranscriptEngine] 구조 분석 완료")
        return analysis

    def _extract_video_id(self, url_or_id: str) -> str:
        """URL에서 video_id 추출"""
        if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
            patterns = [
                r'(?:v=|/)([a-zA-Z0-9_-]{11})',
                r'(?:embed/)([a-zA-Z0-9_-]{11})',
                r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})'
            ]
            for pattern in patterns:
                match = re.search(pattern, url_or_id)
                if match:
                    return match.group(1)
        return url_or_id

    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        # 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        # [음악] 같은 태그 제거
        text = re.sub(r'\[.*?\]', '', text)
        return text.strip()

    def _split_into_chunks(self, text: str, max_chars: int = 3000) -> List[str]:
        """긴 텍스트를 청크로 분할"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)

        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chars:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
