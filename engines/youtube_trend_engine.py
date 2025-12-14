"""
YouTube Trend Engine - YouTube Data API v3 연동 모듈
유튜브 인기 영상 데이터를 가져와 전광판에 표시
"""

import os
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class YouTubeTrendEngine:
    """YouTube Data API v3를 사용하여 트렌드 데이터 수집"""

    # 카테고리별 검색 키워드
    SEARCH_QUERIES = {
        "radio_drama": [
            "라디오드라마 사연",
            "감동 실화 사연",
            "가족 사연 눈물",
            "첫사랑 이야기",
            "실화 드라마",
            "인생 사연",
        ],
        "history": [
            "한국사 미스터리",
            "역사 숨겨진 진실",
            "조선시대 비밀",
            "한국 전쟁 실화",
            "역사 인물 진실",
            "일제강점기 실화",
        ]
    }

    # 카테고리별 제외 키워드 (관련 없는 영상 필터링)
    EXCLUDE_KEYWORDS = {
        "radio_drama": ["ASMR", "브이로그", "먹방", "게임", "shorts"],
        "history": ["게임", "드라마 리뷰", "예능", "shorts"]
    }

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self._youtube = None

    @property
    def youtube(self):
        """YouTube API 클라이언트 lazy loading"""
        if self._youtube is None:
            if not self.api_key:
                raise ValueError("YOUTUBE_API_KEY가 .env에 설정되지 않았습니다.")

            try:
                from googleapiclient.discovery import build
                self._youtube = build('youtube', 'v3', developerKey=self.api_key)
            except ImportError:
                raise ImportError("google-api-python-client 패키지가 필요합니다. pip install google-api-python-client")

        return self._youtube

    def is_available(self) -> bool:
        """API 사용 가능 여부 확인"""
        return bool(self.api_key)

    def search_trending_videos(
        self,
        category: str,
        max_results: int = 10,
        published_after_days: int = 30
    ) -> List[Dict]:
        """
        카테고리별 인기 영상 검색

        Args:
            category: "radio_drama" 또는 "history"
            max_results: 반환할 최대 결과 수
            published_after_days: 최근 N일 이내 영상만 검색

        Returns:
            인기 영상 목록 (정렬됨)
        """
        if not self.is_available():
            return []

        queries = self.SEARCH_QUERIES.get(category, [])
        if not queries:
            return []

        # 검색 기간 설정
        published_after = (datetime.utcnow() - timedelta(days=published_after_days)).isoformat() + "Z"

        all_videos = []
        seen_ids = set()

        for query in queries:
            try:
                # 검색 실행
                search_response = self.youtube.search().list(
                    q=query,
                    part="id,snippet",
                    type="video",
                    order="viewCount",  # 조회수 순
                    publishedAfter=published_after,
                    regionCode="KR",
                    relevanceLanguage="ko",
                    maxResults=10
                ).execute()

                video_ids = []
                for item in search_response.get("items", []):
                    video_id = item["id"]["videoId"]
                    if video_id not in seen_ids:
                        video_ids.append(video_id)
                        seen_ids.add(video_id)

                if video_ids:
                    # 상세 정보 가져오기
                    videos_response = self.youtube.videos().list(
                        part="snippet,statistics,contentDetails",
                        id=",".join(video_ids)
                    ).execute()

                    for video in videos_response.get("items", []):
                        video_data = self._parse_video_data(video, category)
                        if video_data:
                            all_videos.append(video_data)

            except Exception as e:
                print(f"[YouTubeTrendEngine] 검색 오류 ({query}): {e}")
                continue

        # 점수 계산 및 정렬
        scored_videos = self._calculate_scores(all_videos)

        # 상위 N개 반환
        return scored_videos[:max_results]

    def _parse_video_data(self, video: Dict, category: str) -> Optional[Dict]:
        """YouTube API 응답을 파싱하여 필요한 데이터 추출"""
        try:
            snippet = video["snippet"]
            statistics = video.get("statistics", {})
            content_details = video.get("contentDetails", {})

            title = snippet["title"]

            # 제외 키워드 필터링
            exclude_keywords = self.EXCLUDE_KEYWORDS.get(category, [])
            if any(kw.lower() in title.lower() for kw in exclude_keywords):
                return None

            # 조회수 파싱
            view_count = int(statistics.get("viewCount", 0))
            like_count = int(statistics.get("likeCount", 0))
            comment_count = int(statistics.get("commentCount", 0))

            # 영상 길이 파싱 (ISO 8601 duration)
            duration_str = content_details.get("duration", "PT0S")
            duration_minutes = self._parse_duration(duration_str)

            # 너무 짧거나 긴 영상 제외 (1분 미만, 60분 초과)
            if duration_minutes < 1 or duration_minutes > 60:
                return None

            # 게시일
            published_at = snippet["publishedAt"]
            published_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            days_since_published = (datetime.now(published_date.tzinfo) - published_date).days

            return {
                "video_id": video["id"],
                "title": title,
                "channel_title": snippet["channelTitle"],
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "duration_minutes": duration_minutes,
                "published_at": published_at,
                "days_since_published": max(days_since_published, 1),
                "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                "description": snippet.get("description", "")[:200]
            }

        except Exception as e:
            print(f"[YouTubeTrendEngine] 파싱 오류: {e}")
            return None

    def _parse_duration(self, duration_str: str) -> float:
        """ISO 8601 duration을 분 단위로 변환"""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 60 + minutes + seconds / 60

    def _calculate_scores(self, videos: List[Dict]) -> List[Dict]:
        """각 영상의 떡상 점수 계산"""
        if not videos:
            return []

        # 정규화를 위한 최대값 계산
        max_views = max(v["view_count"] for v in videos) or 1
        max_likes = max(v["like_count"] for v in videos) or 1

        scored_videos = []

        for video in videos:
            # 일 평균 조회수 (30%)
            daily_views = video["view_count"] / video["days_since_published"]
            view_score = min((daily_views / 10000) * 30, 30)  # 하루 1만뷰 = 30점

            # 참여도 (좋아요 + 댓글) / 조회수 (25%)
            if video["view_count"] > 0:
                engagement_rate = (video["like_count"] + video["comment_count"]) / video["view_count"]
                engagement_score = min(engagement_rate * 500, 25)  # 5% 참여율 = 25점
            else:
                engagement_score = 0

            # 영상 길이 점수 (20%) - 5~15분이 최적
            duration = video["duration_minutes"]
            if 5 <= duration <= 15:
                duration_score = 20
            elif 3 <= duration < 5 or 15 < duration <= 20:
                duration_score = 15
            elif 1 <= duration < 3 or 20 < duration <= 30:
                duration_score = 10
            else:
                duration_score = 5

            # 신선도 (15%) - 최근 영상 가산점
            days = video["days_since_published"]
            if days <= 7:
                freshness_score = 15
            elif days <= 14:
                freshness_score = 12
            elif days <= 21:
                freshness_score = 8
            else:
                freshness_score = 5

            # 제목 후킹 점수 (10%) - 특정 패턴 포함 시 가산
            hook_patterns = ["비밀", "진실", "충격", "눈물", "실화", "숨겨진", "마지막", "처음"]
            title = video["title"]
            hook_score = sum(3 for pattern in hook_patterns if pattern in title)
            hook_score = min(hook_score, 10)

            total_score = int(view_score + engagement_score + duration_score + freshness_score + hook_score)

            # 조회수 포맷팅
            views = video["view_count"]
            if views >= 1000000:
                views_str = f"{views / 1000000:.0f}만"
            elif views >= 10000:
                views_str = f"{views / 10000:.1f}만"
            elif views >= 1000:
                views_str = f"{views / 1000:.1f}천"
            else:
                views_str = str(views)

            # 길이 포맷팅
            duration_str = f"{int(video['duration_minutes'])}분"

            scored_videos.append({
                **video,
                "score": total_score,
                "views": views_str,
                "length": duration_str,
                "hook": self._extract_hook(video["title"], video["description"])
            })

        # 점수 순 정렬
        scored_videos.sort(key=lambda x: x["score"], reverse=True)

        # 순위 부여
        for i, video in enumerate(scored_videos):
            video["rank"] = i + 1

        return scored_videos

    def _extract_hook(self, title: str, description: str) -> str:
        """제목/설명에서 후킹 문구 추출"""
        # 제목에서 후킹 요소 추출
        hook_indicators = ["...", "?", "!", "…"]

        # 제목이 충분히 후킹력이 있으면 그대로 사용
        if len(title) <= 30:
            return title

        # 제목에서 핵심 문구 추출 시도
        # 따옴표 안의 내용
        quote_match = re.search(r'["\'](.+?)["\']', title)
        if quote_match:
            return quote_match.group(1)

        # 괄호 앞 내용
        bracket_match = re.search(r'^(.+?)[\[\(]', title)
        if bracket_match and len(bracket_match.group(1).strip()) > 5:
            return bracket_match.group(1).strip()

        # 첫 20자 + ...
        return title[:25] + "..."

    def get_trend_data(self, category: str) -> Dict:
        """전광판용 트렌드 데이터 반환"""
        try:
            videos = self.search_trending_videos(category, max_results=10)

            if not videos:
                return {
                    "videos": [],
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": "no_data"
                }

            return {
                "videos": videos,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": "youtube_api"
            }

        except Exception as e:
            print(f"[YouTubeTrendEngine] 트렌드 데이터 오류: {e}")
            return {
                "videos": [],
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": "error",
                "error": str(e)
            }


# 싱글톤 인스턴스
_engine_instance = None

def get_youtube_trend_engine() -> YouTubeTrendEngine:
    """YouTubeTrendEngine 싱글톤 인스턴스 반환"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = YouTubeTrendEngine()
    return _engine_instance


def fetch_trends(category: str) -> List[Dict]:
    """간편 함수: 카테고리별 트렌드 데이터 가져오기"""
    engine = get_youtube_trend_engine()
    if engine.is_available():
        return engine.search_trending_videos(category)
    return []
