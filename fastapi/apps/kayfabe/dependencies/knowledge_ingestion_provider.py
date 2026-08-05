from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.collectors.ontology_public_source_collector import (
    OntologyPublicSourceCollector,
)
from kayfabe.adapter.outbound.embedding.bge_m3_embedder import BgeM3Embedder
from kayfabe.adapter.outbound.pg.knowledge_chunk_pg_repository import (
    KnowledgeChunkPgRepository,
)
from kayfabe.app.ports.input.knowledge_ingestion_use_case import (
    KnowledgeIngestionUseCase,
)
from kayfabe.app.services.prediction_knowledge_sources import ALLOWED_DOMAINS
from kayfabe.app.use_cases.knowledge_ingestion_interactor import (
    KnowledgeIngestionInteractor,
)
from ontology.dependencies.public_source_provider import get_public_source_use_case


def get_knowledge_ingestion_use_case(db: AsyncSession) -> KnowledgeIngestionUseCase:
    """`Depends`가 아니라 세션을 직접 받는다.

    적재는 외부 사이트를 여러 번 오가는 긴 작업이라 HTTP 요청 안에서 돌리지 않는다
    (하네스 §2-D7). 지금 호출자는 `scripts/ingest_prediction_knowledge.py`뿐이다.
    """
    return KnowledgeIngestionInteractor(
        OntologyPublicSourceCollector(get_public_source_use_case(ALLOWED_DOMAINS)),
        BgeM3Embedder(),
        KnowledgeChunkPgRepository(db=db),
    )
