import os
import requests
from typing import List, Dict, Optional
from pathlib import Path
from anthropic import Anthropic


class VideoClipEngine:
    """
    스톡 비디오 클립 엔진 (Pexels API)
    - Scene에 대한 B-roll 비디오 검색 및 다운로드
    - 시니어 맞춤 비디오 필터링
    """

    PEXELS_API_URL = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Pexels API 키 (환경변수 PEXELS_API_KEY에서 가져오거나 직접 전달)
        """
        self.api_key = api_key or os.getenv("PEXELS_API_KEY")
        if self.api_key:
            self.enabled = True
        else:
            self.enabled = False
            print("[VideoClipEngine] Warning: No Pexels API key provided. Video clip feature disabled.")

        # Claude API 클라이언트 (번역용)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.claude_client = Anthropic(api_key=anthropic_key)
            self.translation_enabled = True
        else:
            self.claude_client = None
            self.translation_enabled = False
            print("[VideoClipEngine] Warning: No Anthropic API key. Korean queries will be used directly.")

        # 비디오 해상도 및 방향 설정
        resolution = os.getenv("VIDEO_RESOLUTION", "1920x1080")
        width, height = map(int, resolution.split('x'))

        # Shorts (세로) vs 일반 영상 (가로) 판단
        if height > width:  # 1080x1920 (세로)
            self.orientation = "portrait"
            self.target_width = 1080
            self.target_height = 1920
            self.target_ratio = 9 / 16  # 0.5625
            print(f"[VideoClipEngine] Mode: YouTube Shorts (9:16 세로 영상 검색)")
        else:  # 1920x1080 (가로)
            self.orientation = "landscape"
            self.target_width = 1920
            self.target_height = 1080
            self.target_ratio = 16 / 9  # 1.7778
            print(f"[VideoClipEngine] Mode: 일반 영상 (16:9 가로 영상 검색)")

    def search_and_download_clips(self, scenes: List, output_dir: str) -> Dict[int, str]:
        """
        use_video=True인 scene들에 대해 B-roll 비디오 검색 및 다운로드

        Args:
            scenes: Scene 리스트
            output_dir: 비디오 저장 디렉토리

        Returns:
            scene_idx -> video_path 딕셔너리
        """
        if not self.enabled:
            print("[VideoClipEngine] Skipping video clip download (API not configured)")
            return {}

        os.makedirs(output_dir, exist_ok=True)
        video_paths = {}

        for idx, scene in enumerate(scenes):
            # use_video=True이고 broll_query가 있는 scene만 처리
            if not getattr(scene, 'use_video', False):
                continue

            broll_query = getattr(scene, 'broll_query', '')
            if not broll_query:
                print(f"[VideoClipEngine] Warning: Scene {idx} has use_video=True but no broll_query")
                continue

            try:
                print(f"[VideoClipEngine] Searching video for scene {idx}: '{broll_query}'")

                # 한국어 검색어를 영어로 번역 (Pexels는 영어 검색이 더 정확)
                english_query = self._translate_to_english(broll_query)

                # Pexels API로 비디오 검색
                video_url = self._search_video(english_query, scene.duration_sec)

                if video_url:
                    # 비디오 다운로드
                    video_path = os.path.join(output_dir, f"broll_{idx:03d}_{scene.safe_filename_id}.mp4")
                    self._download_video(video_url, video_path)
                    video_paths[idx] = video_path
                    print(f"  ✓ Downloaded: {video_path}")
                else:
                    print(f"  ✗ No suitable video found for '{broll_query}'")

            except Exception as e:
                print(f"[VideoClipEngine] Error processing scene {idx}: {e}")
                continue

        return video_paths

    def _translate_to_english(self, korean_query: str) -> str:
        """
        한국어 검색어를 영어로 번역 (Claude API 사용)

        Pexels는 영어 검색이 더 정확하므로 한국어 키워드를 영어로 번역합니다.

        Args:
            korean_query: 한국어 검색어

        Returns:
            영어 검색어 (번역 실패 시 원본 반환)
        """
        # 이미 영어인 경우 그대로 반환
        if korean_query.isascii():
            return korean_query

        # Claude API가 없으면 원본 반환
        if not self.translation_enabled or not self.claude_client:
            return korean_query

        try:
            prompt = f"""다음 한국어 검색어를 Pexels 비디오 검색에 최적화된 영어로 번역해주세요.
간결하고 구체적인 영어 키워드만 반환하세요. 설명은 필요 없습니다.

한국어: {korean_query}

영어 키워드:"""

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=100,
                temperature=0.3,  # 낮은 temperature로 일관성 있는 번역
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            english_query = response.content[0].text.strip()

            # 번역 결과 검증 (너무 길면 원본 사용)
            if len(english_query) > 100 or '\n' in english_query:
                print(f"[VideoClipEngine] ⚠️ 번역 결과가 이상함, 원본 사용: {korean_query}")
                return korean_query

            print(f"[VideoClipEngine] 🌐 번역: '{korean_query}' → '{english_query}'")
            return english_query

        except Exception as e:
            print(f"[VideoClipEngine] ⚠️ 번역 실패 ({e}), 원본 사용: {korean_query}")
            return korean_query

    def _search_video(self, query: str, min_duration: int = 5) -> Optional[str]:
        """
        Pexels API로 비디오 검색

        Args:
            query: 검색 키워드
            min_duration: 최소 비디오 길이 (초)

        Returns:
            비디오 다운로드 URL (None이면 검색 실패)
        """
        try:
            headers = {
                "Authorization": self.api_key
            }

            params = {
                "query": query,
                "per_page": 15,  # 여러 옵션 중 선택
                "orientation": self.orientation,  # 동적으로 설정 (portrait/landscape)
                "size": "medium"  # HD 품질
            }

            response = requests.get(
                self.PEXELS_API_URL,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                print(f"[VideoClipEngine] Pexels API error: {response.status_code}")
                return None

            data = response.json()
            videos = data.get("videos", [])

            if not videos:
                print(f"[VideoClipEngine] No videos found for query: {query}")
                return None

            # 시니어 맞춤 비디오 필터링
            suitable_videos = []
            for video in videos:
                duration = video.get("duration", 0)

                # 최소 길이 조건
                if duration < min_duration:
                    continue

                # 비디오 파일 가져오기 (HD 우선)
                video_files = video.get("video_files", [])
                for vf in video_files:
                    # 1080p 또는 720p HD 비디오 선택
                    if vf.get("quality") in ["hd", "sd"] and vf.get("width", 0) >= 1280:
                        suitable_videos.append({
                            "url": vf.get("link"),
                            "duration": duration,
                            "width": vf.get("width"),
                            "height": vf.get("height")
                        })
                        break

            if not suitable_videos:
                print(f"[VideoClipEngine] No suitable HD videos found")
                return None

            # 가장 적합한 비디오 선택 (해상도 우선)
            best_video = max(suitable_videos, key=lambda v: v["width"])
            print(f"  Selected video: {best_video['width']}x{best_video['height']}, {best_video['duration']}s")

            return best_video["url"]

        except Exception as e:
            print(f"[VideoClipEngine] Error searching video: {e}")
            return None

    def _download_video(self, url: str, output_path: str) -> bool:
        """
        비디오 다운로드

        Args:
            url: 비디오 다운로드 URL
            output_path: 저장 경로

        Returns:
            성공 여부
        """
        try:
            # 이미 존재하면 스킵
            if os.path.exists(output_path):
                print(f"  Video already exists: {output_path}")
                return True

            print(f"  Downloading video from Pexels...")

            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # 청크 단위로 다운로드
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return True

        except Exception as e:
            print(f"[VideoClipEngine] Error downloading video: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False

    def get_fallback_query(self, scene_id: str, category: str) -> str:
        """
        Scene ID와 카테고리에 따른 기본 B-roll 쿼리 생성

        Args:
            scene_id: Scene ID
            category: 카테고리

        Returns:
            검색 쿼리
        """
        # 카테고리별 기본 쿼리
        category_queries = {
            "health": "healthy lifestyle senior exercise",
            "money": "retirement planning financial security",
            "emotion": "family love warm moments",
            "memory": "nostalgic old times vintage",
            "general": "peaceful nature calm scenery"
        }

        # Scene ID별 특화 쿼리
        scene_queries = {
            "hook": "attention grabbing interesting",
            "empathy": "relatable everyday life",
            "summary": "conclusion summary peaceful",
            "action": "motivation positive energy"
        }

        base = category_queries.get(category, "peaceful nature")
        scene_modifier = scene_queries.get(scene_id, "")

        if scene_modifier:
            return f"{base} {scene_modifier}"
        return base
