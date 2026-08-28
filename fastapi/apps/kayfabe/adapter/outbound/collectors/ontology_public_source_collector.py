"""공개 소스 수집을 ontology 허브에 위임하는 어댑터.

`wrestler_chat_repository`가 생성을 허브에 넘기는 것과 같은 방향이다(§3-D7). 허브의
DTO·예외는 여기서 kayfabe의 것으로 갈아 끼운다 — 유스케이스가 허브 어휘를 모르게.
"""

from __future__ import annotations

from kayfabe.app.dtos.knowledge_ingestion_dto import SourceDocument
from kayfabe.app.ports.output.public_source_port import (
    PublicSourcePort,
    SourceNotAllowedError,
)
from ontology.app.ports.input.public_source_use_case import (
    PublicSourceUseCase,
)
from ontology.app.ports.input.public_source_use_case import (
    SourceNotAllowedError as HubSourceNotAllowedError,
)


class OntologyPublicSourceCollector(PublicSourcePort):
    def __init__(self, use_case: PublicSourceUseCase) -> None:
        self._use_case = use_case

    async def collect(self, url: str) -> SourceDocument | None:
        try:
            document = await self._use_case.collect(url)
        except HubSourceNotAllowedError as exc:
            raise SourceNotAllowedError(str(exc)) from exc

        if document is None:
            return None
        return SourceDocument(
            url=document.url,
            title=document.title,
            text=document.text,
            published_at=document.published_at,
            revision_id=document.revision_id,
            revised_at=document.revised_at,
        )
