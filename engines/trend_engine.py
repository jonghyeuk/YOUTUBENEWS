"""
트렌드 분석 엔진 - YouTube 인기 영상 찾기
"""
import os
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class TrendVideo:
    """트렌드 영상 정보"""
    video_id: str
    title: str
    description: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    published_at: str
    channel_title: str
    thumbnail_url: str
    top_comments: List[str] = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


class TrendEngine:
    """YouTube 트렌드 분석 엔진"""

    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")

        if self.api_key:
            from googleapiclient.discovery import build
            self.youtube = build("youtube", "v3", developerKey=self.api_key)
            print("[TrendEngine] YouTube API 초기화 완료")
        else:
            self.youtube = None
            print("[TrendEngine] Warning: YOUTUBE_API_KEY 없음")

    def search_trending(
        self,
        keyword: str,
        min_views: int = 10000,
        max_results: int = 10,
        published_after: str = None,
        duration: str = "medium"  # short, medium, long
    ) -> List[TrendVideo]:
        """
        키워드로 인기 영상 검색

        Args:
            keyword: 검색 키워드 (예: "해외 감동 사연")
            min_views: 최소 조회수
            max_results: 최대 결과 수
            published_after: 업로드 날짜 필터 (ISO 8601, 예: "2024-01-01T00:00:00Z")
            duration: 영상 길이 (short: 4분 미만, medium: 4-20분, long: 20분 이상)

        Returns:
            TrendVideo 리스트
        """
        if not self.youtube:
            raise RuntimeError("YouTube API 키가 설정되지 않았습니다")

        # 검색 요청
        search_params = {
            "q": keyword,
            "type": "video",
            "part": "snippet",
            "maxResults": max_results * 2,  # 필터링 후 충분한 결과 확보
            "order": "viewCount",
            "videoDuration": duration,
            "relevanceLanguage": "ko",
        }

        if published_after:
            search_params["publishedAfter"] = published_after

        search_response = self.youtube.search().list(**search_params).execute()

        # 비디오 ID 수집
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

        if not video_ids:
            return []

        # 상세 정보 조회
        videos_response = self.youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids)
        ).execute()

        # 결과 필터링 및 변환
        results = []
        for item in videos_response.get("items", []):
            stats = item.get("statistics", {})
            view_count = int(stats.get("viewCount", 0))

            if view_count >= min_views:
                snippet = item["snippet"]
                trend_video = TrendVideo(
                    video_id=item["id"],
                    title=snippet["title"],
                    description=snippet.get("description", ""),
                    view_count=view_count,
                    like_count=int(stats.get("likeCount", 0)),
                    comment_count=int(stats.get("commentCount", 0)),
                    duration=item["contentDetails"]["duration"],
                    published_at=snippet["publishedAt"],
                    channel_title=snippet["channelTitle"],
                    thumbnail_url=snippet["thumbnails"]["high"]["url"]
                )
                results.append(trend_video)

                if len(results) >= max_results:
                    break

        print(f"[TrendEngine] '{keyword}' 검색 결과: {len(results)}개 영상")
        return results

    def get_top_comments(
        self,
        video_id: str,
        max_results: int = 20
    ) -> List[Dict]:
        """
        영상의 인기 댓글 가져오기 (시청자 열광 포인트 분석용)

        Args:
            video_id: 영상 ID
            max_results: 최대 댓글 수

        Returns:
            댓글 리스트 [{text, like_count, author}]
        """
        if not self.youtube:
            return []

        try:
            response = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_results,
                order="relevance"  # 인기순
            ).execute()

            comments = []
            for item in response.get("items", []):
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "text": snippet["textDisplay"],
                    "like_count": snippet["likeCount"],
                    "author": snippet["authorDisplayName"]
                })

            print(f"[TrendEngine] 댓글 {len(comments)}개 수집")
            return comments

        except Exception as e:
            print(f"[TrendEngine] 댓글 수집 실패: {e}")
            return []

    def analyze_engagement(self, video: TrendVideo) -> Dict:
        """
        영상 참여도 분석

        Returns:
            분석 결과 딕셔너리
        """
        # 참여율 계산
        engagement_rate = 0
        if video.view_count > 0:
            engagement_rate = (video.like_count + video.comment_count) / video.view_count * 100

        # 댓글 가져오기
        comments = self.get_top_comments(video.video_id)

        return {
            "video": video,
            "engagement_rate": round(engagement_rate, 2),
            "top_comments": comments,
            "viral_score": self._calculate_viral_score(video, engagement_rate)
        }

    def _calculate_viral_score(self, video: TrendVideo, engagement_rate: float) -> int:
        """바이럴 점수 계산 (0-100)"""
        score = 0

        # 조회수 점수 (최대 40점)
        if video.view_count >= 1000000:
            score += 40
        elif video.view_count >= 100000:
            score += 30
        elif video.view_count >= 10000:
            score += 20
        else:
            score += 10

        # 참여율 점수 (최대 30점)
        if engagement_rate >= 10:
            score += 30
        elif engagement_rate >= 5:
            score += 20
        elif engagement_rate >= 2:
            score += 10

        # 댓글 수 점수 (최대 30점)
        if video.comment_count >= 1000:
            score += 30
        elif video.comment_count >= 100:
            score += 20
        elif video.comment_count >= 10:
            score += 10

        return min(score, 100)
