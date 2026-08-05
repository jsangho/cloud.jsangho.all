"""공개 소스 수집 출력 포트.

실제 HTTP는 ontology 허브가 한다(§2-D2). kayfabe는 **자기 말로 된 포트**만 두고,
어댑터가 허브의 유스케이스로 옮겨 준다 — 허브의 DTO·예외가 이 앱 안으로 새지 않게.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.knowledge_ingestion_dto import SourceDocument


class SourceNotAllowedError(Exception):
    """허용 도메인 목록(§3-D10) 밖의 주소다. 요청을 보내기 전에 난다."""


class PublicSourcePort(ABC):
    @abstractmethod
    async def collect(self, url: str) -> SourceDocument | None:
        """문서 하나를 가져온다. 읽지 않기로 했으면 `None`이다.

        `None`인 경우: robots.txt가 막았거나, 응답이 200이 아니거나, 본문이 비었다.
        허용 도메인 밖이면 `SourceNotAllowedError`.
        """
