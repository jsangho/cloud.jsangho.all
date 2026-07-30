from __future__ import annotations

from abc import ABC, abstractmethod


class GraphRetrievalPort(ABC):
    @abstractmethod
    async def search_documents(self, keywords: list[str]) -> list[str]:
        """`(:Document)` 텍스트를 조회한다.

        keywords가 있으면 텍스트에 해당 키워드를 포함한 문서만, 비어 있으면
        최근 업로드된 문서를 반환한다(근거 부족 시 재검색 폴백용).
        """
        ...
