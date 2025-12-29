"""
YouTube 업로드 엔진
- OAuth2 인증으로 YouTube 채널에 영상 업로드
- 제목, 설명, 태그, 썸네일 설정
"""

import os
import pickle
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# YouTube API 스코프 (업로드 + 썸네일 설정)
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",  # 썸네일 설정에 필요
]

# 파일 경로
CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_FILE = "youtube_token.pickle"

# 업로드 재시도 설정
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class YouTubeUploadEngine:
    """YouTube 영상 업로드 엔진"""

    def __init__(self):
        self.youtube = None
        self.credentials = None

    def authenticate(self) -> bool:
        """OAuth2 인증 수행"""
        creds = None

        # 저장된 토큰 확인
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)

        # 토큰이 없거나 만료된 경우
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # 토큰 갱신
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[YouTube] 토큰 갱신 실패: {e}")
                    creds = None

            if not creds:
                # 새로 인증
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    raise FileNotFoundError(
                        f"❌ {CLIENT_SECRETS_FILE} 파일이 없습니다.\n"
                        "Google Cloud Console에서 OAuth 클라이언트 ID를 생성하고 "
                        "JSON 파일을 다운로드하세요."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRETS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # 토큰 저장
            with open(TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)

        self.credentials = creds
        self.youtube = build("youtube", "v3", credentials=creds)
        return True

    def get_channel_info(self) -> Dict[str, Any]:
        """인증된 채널 정보 가져오기"""
        if not self.youtube:
            self.authenticate()

        request = self.youtube.channels().list(
            part="snippet,statistics",
            mine=True
        )
        response = request.execute()

        if response.get("items"):
            channel = response["items"][0]
            return {
                "id": channel["id"],
                "title": channel["snippet"]["title"],
                "description": channel["snippet"].get("description", ""),
                "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"],
                "subscribers": channel["statistics"].get("subscriberCount", "비공개"),
                "videos": channel["statistics"].get("videoCount", 0),
            }
        return {}

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: str,
        category_id: str = "22",  # 22 = People & Blogs
        privacy_status: str = "private",  # private, unlisted, public
        thumbnail_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        YouTube에 영상 업로드

        Args:
            video_path: 업로드할 영상 파일 경로
            title: 영상 제목
            description: 영상 설명
            tags: 태그 (쉼표 구분)
            category_id: 카테고리 ID (기본: 22 = People & Blogs)
            privacy_status: 공개 상태 (private/unlisted/public)
            thumbnail_path: 썸네일 이미지 경로 (선택)
            progress_callback: 진행률 콜백 함수 (uploaded_bytes, total_bytes)

        Returns:
            업로드된 영상 정보 (video_id, url 등)
        """
        if not self.youtube:
            self.authenticate()

        # 파일 존재 확인
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"영상 파일을 찾을 수 없습니다: {video_path}")

        # 태그 처리
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        # 영상 메타데이터
        body = {
            "snippet": {
                "title": title[:100],  # YouTube 제목 제한
                "description": description[:5000],  # 설명 제한
                "tags": tag_list[:500],  # 태그 제한
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # 미디어 업로드 설정
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 10,  # 10MB chunks
        )

        # 업로드 요청 생성
        request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        # 업로드 실행 (재시도 로직 포함)
        response = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()

                if status and progress_callback:
                    progress_callback(
                        status.resumable_progress,
                        status.total_size
                    )

            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504] and retry < MAX_RETRIES:
                    retry += 1
                    print(f"[YouTube] 업로드 재시도 {retry}/{MAX_RETRIES}...")
                    time.sleep(RETRY_DELAY * retry)
                else:
                    raise

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        result = {
            "video_id": video_id,
            "url": video_url,
            "title": response["snippet"]["title"],
            "status": response["status"]["privacyStatus"],
        }

        # 썸네일 업로드 (있는 경우)
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                self._upload_thumbnail(video_id, thumbnail_path)
                result["thumbnail_uploaded"] = True
            except Exception as e:
                print(f"[YouTube] 썸네일 업로드 실패: {e}")
                result["thumbnail_uploaded"] = False
                result["thumbnail_error"] = str(e)

        return result

    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """영상 썸네일 업로드"""
        media = MediaFileUpload(
            thumbnail_path,
            mimetype="image/jpeg",
        )

        self.youtube.thumbnails().set(
            videoId=video_id,
            media_body=media,
        ).execute()

        print(f"[YouTube] 썸네일 업로드 완료: {video_id}")

    def check_auth_status(self) -> Dict[str, Any]:
        """인증 상태 확인"""
        result = {
            "has_client_secrets": os.path.exists(CLIENT_SECRETS_FILE),
            "has_token": os.path.exists(TOKEN_FILE),
            "authenticated": False,
            "channel": None,
        }

        if result["has_token"]:
            try:
                self.authenticate()
                channel = self.get_channel_info()
                if channel:
                    result["authenticated"] = True
                    result["channel"] = channel
            except Exception as e:
                result["error"] = str(e)

        return result


# 카테고리 ID 참조
YOUTUBE_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",  # 기본값
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}
