"""
YouTube Metadata Engine - 유튜브 업로드용 메타데이터 자동 생성

설명란 구조:
1. 인트로 문장 (맨 앞) - 스토리 소개
2. CTA 문장 (중간) - 좋아요/구독 요청
3. SEO 문장 (맨 뒤) - 검색 최적화용 고정 문구
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class YouTubeDescriptionConfig:
    """YouTube 설명란 템플릿 설정"""

    # ★ 인트로 문장 템플릿 (맨 앞)
    # {story_title}은 영상 제목으로 대체됨
    intro_template: str = "오늘은 {story_title}에 얽힌 옛 야화를 조용히 들려드립니다."

    # ★ CTA 문장 (중간)
    cta_text: str = "편안하게 들으셨다면 좋아요와 구독 부탁드립니다."

    # ★ SEO 문장 (맨 뒤) - 알고리즘용 고정 문구
    seo_text: str = "한국 전통 야화·민담·설화를 바탕으로 재구성한 수면 스토리 채널입니다."

    # 구분선
    separator: str = "\n\n"


class YouTubeMetadataEngine:
    """
    유튜브 업로드용 메타데이터 생성 엔진

    - 설명란 자동 생성 (인트로 + CTA + SEO)
    - 태그 자동 생성
    - 업로드용 메타데이터 파일 생성
    """

    # 카테고리별 기본 설정
    CATEGORY_CONFIGS = {
        "yadam": YouTubeDescriptionConfig(
            intro_template="오늘은 {story_title}에 얽힌 옛 야화를 조용히 들려드립니다.",
            cta_text="편안하게 들으셨다면 좋아요와 구독 부탁드립니다.",
            seo_text="한국 전통 야화·민담·설화를 바탕으로 재구성한 수면 스토리 채널입니다."
        ),
        "history": YouTubeDescriptionConfig(
            intro_template="오늘은 {story_title}에 관한 역사 이야기를 들려드립니다.",
            cta_text="유익하셨다면 좋아요와 구독으로 응원해주세요.",
            seo_text="한국 역사의 숨겨진 이야기를 재조명하는 채널입니다."
        ),
        "radio_drama": YouTubeDescriptionConfig(
            intro_template="오늘의 이야기, {story_title}입니다.",
            cta_text="감동받으셨다면 좋아요와 구독 부탁드립니다.",
            seo_text="감동 실화와 사연을 담은 라디오 드라마 채널입니다."
        ),
        "default": YouTubeDescriptionConfig()
    }

    # 카테고리별 기본 태그
    CATEGORY_TAGS = {
        "yadam": [
            "야담", "야화", "옛날이야기", "전래동화", "한국전통",
            "수면스토리", "잠잘때듣는이야기", "ASMR이야기",
            "민담", "설화", "구전동화", "밤에듣는이야기"
        ],
        "history": [
            "한국역사", "역사이야기", "역사다큐", "조선시대",
            "숨겨진역사", "역사미스터리", "한국사"
        ],
        "radio_drama": [
            "라디오드라마", "감동실화", "사연", "눈물나는이야기",
            "실화", "드라마사연"
        ],
        "default": ["이야기", "스토리", "한국"]
    }

    def __init__(self, category: str = "yadam"):
        """
        Args:
            category: 컨텐츠 카테고리 (yadam, history, radio_drama)
        """
        self.category = category
        self.config = self.CATEGORY_CONFIGS.get(category, self.CATEGORY_CONFIGS["default"])
        self.base_tags = self.CATEGORY_TAGS.get(category, self.CATEGORY_TAGS["default"])

    def generate_description(self,
                            story_title: str,
                            synopsis: str = "",
                            custom_intro: str = None,
                            custom_cta: str = None,
                            custom_seo: str = None) -> str:
        """
        YouTube 설명란 생성

        구조:
        [인트로 문장]

        [시놉시스 (있으면)]

        [CTA 문장]

        ---
        [SEO 문장]

        Args:
            story_title: 스토리 제목
            synopsis: 스토리 요약 (선택)
            custom_intro: 커스텀 인트로 문장 (선택)
            custom_cta: 커스텀 CTA 문장 (선택)
            custom_seo: 커스텀 SEO 문장 (선택)

        Returns:
            완성된 YouTube 설명란 텍스트
        """
        # 1. 인트로 문장 (맨 앞)
        intro = custom_intro or self.config.intro_template.format(story_title=story_title)

        # 2. 시놉시스 (있으면 추가)
        if synopsis:
            content = f"{intro}{self.config.separator}{synopsis}"
        else:
            content = intro

        # 3. CTA 문장 (중간)
        cta = custom_cta or self.config.cta_text
        content = f"{content}{self.config.separator}{cta}"

        # 4. SEO 문장 (맨 뒤) - 구분선으로 분리
        seo = custom_seo or self.config.seo_text
        content = f"{content}\n\n---\n{seo}"

        return content

    def generate_tags(self,
                     story_title: str,
                     keywords: list = None,
                     max_tags: int = 15) -> list:
        """
        YouTube 태그 생성

        Args:
            story_title: 스토리 제목
            keywords: 추가 키워드 리스트
            max_tags: 최대 태그 수

        Returns:
            태그 리스트
        """
        tags = list(self.base_tags)  # 기본 태그 복사

        # 제목에서 키워드 추출
        title_words = story_title.replace(",", "").replace(".", "").split()
        for word in title_words:
            if len(word) >= 2 and word not in tags:
                tags.append(word)

        # 추가 키워드
        if keywords:
            for kw in keywords:
                if kw not in tags:
                    tags.append(kw)

        return tags[:max_tags]

    def generate_metadata(self,
                         video_title: str,
                         story_title: str = None,
                         synopsis: str = "",
                         keywords: list = None,
                         thumbnail_path: str = None,
                         video_path: str = None) -> Dict:
        """
        YouTube 업로드용 전체 메타데이터 생성

        Args:
            video_title: 영상 제목
            story_title: 스토리 제목 (없으면 video_title 사용)
            synopsis: 스토리 요약
            keywords: 키워드 리스트
            thumbnail_path: 썸네일 경로
            video_path: 비디오 경로

        Returns:
            YouTube 업로드용 메타데이터 딕셔너리
        """
        story_title = story_title or video_title

        return {
            "title": video_title,
            "description": self.generate_description(story_title, synopsis),
            "tags": self.generate_tags(story_title, keywords),
            "category": self._get_youtube_category(),
            "privacy_status": "private",  # 기본값: 비공개 (검토 후 공개)
            "thumbnail_path": thumbnail_path,
            "video_path": video_path,
            # 설명란 구성요소 (개별 접근용)
            "description_parts": {
                "intro": self.config.intro_template.format(story_title=story_title),
                "cta": self.config.cta_text,
                "seo": self.config.seo_text
            }
        }

    def _get_youtube_category(self) -> str:
        """YouTube 카테고리 ID 반환"""
        # YouTube 카테고리 ID
        # 22: People & Blogs
        # 24: Entertainment
        # 27: Education
        category_map = {
            "yadam": "24",      # Entertainment
            "history": "27",    # Education
            "radio_drama": "24" # Entertainment
        }
        return category_map.get(self.category, "22")

    def save_description_file(self,
                             description: str,
                             output_path: str) -> str:
        """
        설명란 텍스트를 파일로 저장 (복사용)

        Args:
            description: 설명란 텍스트
            output_path: 출력 파일 경로

        Returns:
            저장된 파일 경로
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(description)
        print(f"[YouTubeMetadataEngine] 설명란 저장: {output_path}")
        return output_path


# 간편 함수
def generate_youtube_description(story_title: str,
                                 category: str = "yadam",
                                 synopsis: str = "") -> str:
    """
    간편 함수: YouTube 설명란 생성

    Args:
        story_title: 스토리 제목
        category: 카테고리 (yadam, history, radio_drama)
        synopsis: 스토리 요약

    Returns:
        완성된 설명란 텍스트
    """
    engine = YouTubeMetadataEngine(category)
    return engine.generate_description(story_title, synopsis)
