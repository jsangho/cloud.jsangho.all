from __future__ import annotations

from abc import ABC, abstractmethod

from auth.domain.value_objects.kakao_identity import KakaoProfile, KakaoTokenSet


class KakaoMobileIdentityProvider(ABC):
    """모바일 전용 카카오 포트.

    기존 `OAuthIdentityProvider`(google·naver가 공유)와 분리한 이유는 인터페이스 분리
    원칙이다. 모바일 경로에만 필요한 `redirect_uri` 인자·카카오 토큰 반환·unlink를
    공용 포트에 밀어 넣으면 google·naver 어댑터가 쓰지 않는 메서드를 떠안는다.
    """

    @abstractmethod
    async def exchange_code(self, *, code: str, redirect_uri: str) -> KakaoTokenSet: ...

    @abstractmethod
    async def fetch_profile(self, *, access_token: str) -> KakaoProfile: ...

    @abstractmethod
    async def unlink(self, *, kakao_access_token: str) -> None:
        """연결 해제. 서버가 보관한 카카오 토큰으로 호출한다."""
