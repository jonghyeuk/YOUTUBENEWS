"""
Google Cloud 인증 간소화 래퍼

환경 변수 설정 없이 프로젝트 폴더에 key.json 파일만 넣으면 작동합니다.

사용법:
    auth = GoogleAuthManager("key.json")
    if auth.authenticate():
        # Vertex AI 사용 가능
        model = ImageGenerationModel.from_pretrained("imagegeneration@006")
"""
import os
from typing import Optional

# Vertex AI 및 인증 관련 import (선택적)
try:
    import vertexai
    from google.oauth2 import service_account
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False


class GoogleAuthManager:
    """
    Google Cloud 인증 관리자

    JSON 키 파일을 사용하여 Vertex AI를 간편하게 초기화합니다.
    환경 변수 설정이 필요 없습니다.
    """

    def __init__(self, key_file: str = "key.json", location: str = "us-central1"):
        """
        Args:
            key_file: 서비스 계정 JSON 키 파일 경로 (기본값: "key.json")
            location: Vertex AI 리전 (기본값: "us-central1")
        """
        self.key_file = key_file
        self.location = location
        self.credentials = None
        self.project_id = None
        self.is_authenticated = False

    def authenticate(self) -> bool:
        """
        JSON 키 파일을 로드하여 Vertex AI를 초기화합니다.

        Returns:
            성공하면 True, 실패하면 False
        """
        if not VERTEX_AI_AVAILABLE:
            print("⚠️ [GoogleAuth] google-cloud-aiplatform가 설치되지 않았습니다.")
            print("   설치: pip install google-cloud-aiplatform")
            return False

        if not os.path.exists(self.key_file):
            print(f"⚠️ [GoogleAuth] 키 파일이 없습니다: {self.key_file}")
            print(f"   프로젝트 루트에 {self.key_file} 파일을 넣어주세요.")
            return False

        try:
            # 1. 서비스 계정 파일로 자격 증명 로드
            self.credentials = service_account.Credentials.from_service_account_file(self.key_file)

            # 2. JSON 내부에서 project_id 자동 추출
            self.project_id = self.credentials.project_id

            # 3. Vertex AI SDK 초기화 (환경변수 불필요)
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )

            self.is_authenticated = True
            print(f"✅ [GoogleAuth] 인증 성공! (Project: {self.project_id}, Location: {self.location})")
            return True

        except Exception as e:
            print(f"❌ [GoogleAuth] 인증 실패: {str(e)}")
            return False

    def get_project_id(self) -> Optional[str]:
        """
        인증된 프로젝트 ID를 반환합니다.

        Returns:
            프로젝트 ID (인증되지 않았으면 None)
        """
        return self.project_id if self.is_authenticated else None

    def get_credentials(self):
        """
        인증된 자격 증명 객체를 반환합니다.

        Returns:
            Credentials 객체 (인증되지 않았으면 None)
        """
        return self.credentials if self.is_authenticated else None
