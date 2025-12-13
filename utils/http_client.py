import requests
from typing import Dict, Any, Optional


class HttpClient:
    """
    공통 HTTP 클라이언트
    - API 호출용
    - 에러 핸들링
    """

    def __init__(self, base_url: str = None, headers: Dict[str, str] = None):
        """
        Args:
            base_url: 기본 URL
            headers: 공통 헤더
        """
        self.base_url = base_url
        self.headers = headers or {}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        GET 요청

        Args:
            endpoint: API 엔드포인트
            params: 쿼리 파라미터

        Returns:
            응답 JSON
        """
        url = self._build_url(endpoint)
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: Dict[str, Any] = None,
             json: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        POST 요청

        Args:
            endpoint: API 엔드포인트
            data: 폼 데이터
            json: JSON 데이터

        Returns:
            응답 JSON
        """
        url = self._build_url(endpoint)
        response = self.session.post(url, data=data, json=json)
        response.raise_for_status()
        return response.json()

    def _build_url(self, endpoint: str) -> str:
        """URL 생성"""
        if self.base_url:
            return f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        return endpoint
