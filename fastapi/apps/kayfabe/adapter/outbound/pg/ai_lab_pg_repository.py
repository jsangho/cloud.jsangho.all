"""AI LAB Postgres 어댑터 — 읽기 전용 (Phase 3-0·3-1·3-4).

**세지 않는다. 읽어만 준다.** 집계와 신뢰성 판정은 `app/services/ai_lab_integrity.py`가
한다 — 그 판정이 이 화면의 핵심이라 DB 없이 테스트되어야 한다.

쿼리는 다섯이다: 예측 ⨝ 대회 ⟕ 경기 · 리포트 ⨝ 예측 ⨝ 대회 · 지식 카운트 ·
문서별 지식 카운트(3-4) · 대회 수. 지금 규모(예측 12 · 리포트 30 · 청크 668)에서
카운트를 뺀 둘은 전량 조회가 가장 단순하다.

**문서 단위 집계만 예외로 DB에서 센다** — 청크를 전량 읽으면 화면에 쓰지 않는
본문(`content`)까지 딸려 오기 때문이다.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    SOURCE_SEPARATOR,
    AgentPredictionModel,
    AgentReportModel,
)
from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

logger = logging.getLogger("uvicorn.error")


class AiLabPgRepository(AiLabRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_predictions(self) -> list[PredictionRow]:
        result = await self.db.execute(
            select(
                PleEventModel.slug,
                PleEventModel.label,
                AgentPredictionModel.match_key,
                PleMatchModel.title,
                AgentPredictionModel.pick,
                AgentPredictionModel.pick_name,
                AgentPredictionModel.win_probability,
                AgentPredictionModel.confidence,
                AgentPredictionModel.rationale,
                AgentPredictionModel.source,
                AgentPredictionModel.generated_at,
                PleMatchModel.winner_pick,
                PleMatchModel.winner_name,
                # 결과가 기록된 시각 (Phase 3-6). 평가 자격 판정이 "예측을 만들 때
                # 정답이 이미 시스템 안에 있었는가"를 묻는 데 쓴다. 컬럼 하나가
                # 늘 뿐 쿼리 수도 조인도 그대로다.
                PleMatchModel.finished_at,
            )
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            # 경기 행이 사라져도 예측은 남는다 — 그때 채점 불가로 두고 버리지 않는다.
            .outerjoin(
                PleMatchModel,
                (PleMatchModel.event_id == AgentPredictionModel.event_id)
                & (PleMatchModel.match_key == AgentPredictionModel.match_key),
            )
            .order_by(AgentPredictionModel.generated_at)
        )
        rows = [
            PredictionRow(
                event_slug=row.slug,
                event_label=row.label,
                match_key=row.match_key,
                match_title=row.title or row.match_key,
                pick=row.pick,
                pick_name=row.pick_name,
                win_probability=row.win_probability,
                confidence=row.confidence,
                rationale=row.rationale,
                source=row.source,
                generated_at=row.generated_at,
                winner_pick=row.winner_pick,
                winner_name=row.winner_name,
                finished_at=row.finished_at,
            )
            for row in result.all()
        ]
        logger.info("[AiLabPgRepository] list_predictions <- count=%d", len(rows))
        return rows

    async def list_reports(self) -> list[ReportRow]:
        result = await self.db.execute(
            select(
                PleEventModel.slug,
                AgentPredictionModel.match_key,
                AgentReportModel.agent,
                AgentReportModel.pick,
                AgentReportModel.weight,
                AgentReportModel.summary,
                AgentReportModel.sources,
            )
            .join(
                AgentPredictionModel,
                AgentReportModel.prediction_id == AgentPredictionModel.id,
            )
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            .order_by(AgentReportModel.id)
        )
        rows = [
            ReportRow(
                event_slug=row.slug,
                match_key=row.match_key,
                agent=row.agent,
                pick=row.pick,
                weight=row.weight,
                summary=row.summary,
                sources=_split_sources(row.sources),
            )
            for row in result.all()
        ]
        logger.info("[AiLabPgRepository] list_reports <- count=%d", len(rows))
        return rows

    async def corpus_facts(self) -> CorpusFacts:
        result = await self.db.execute(
            select(
                func.count(),
                func.count(KnowledgeChunkModel.embedding),
                func.count(KnowledgeChunkModel.published_at),
                func.count(func.distinct(KnowledgeChunkModel.source_url)),
                func.count(func.distinct(KnowledgeChunkModel.source_domain)),
                func.max(KnowledgeChunkModel.collected_at),
            ).select_from(KnowledgeChunkModel)
        )
        total, embedded, published, documents, domains, collected = result.one()
        facts = CorpusFacts(
            chunks_total=int(total or 0),
            chunks_embedded=int(embedded or 0),
            chunks_with_published_at=int(published or 0),
            documents=int(documents or 0),
            domains=int(domains or 0),
            last_collected_at=collected,
        )
        logger.info(
            "[AiLabPgRepository] corpus_facts <- 청크=%d 발행일=%d",
            facts.chunks_total,
            facts.chunks_with_published_at,
        )
        return facts

    async def list_documents(self) -> list[DocumentRow]:
        """출처 URL로 묶는다 — **집계는 DB가 하고 SELECT는 한 번이다.**

        청크 668건을 전량 읽어 파이썬에서 접을 수도 있지만, 그러면 본문(`content`)까지
        딸려 온다. 화면에 안 쓰는 텍스트를 응답 하나마다 통째로 실어 나르게 된다.

        제목은 같은 URL의 청크가 공유하므로 `min()`으로 대표 하나를 집는다 — NULL은
        `min()`이 건너뛰므로, 일부 청크에만 제목이 있어도 그 값이 살아남는다.
        """
        result = await self.db.execute(
            select(
                KnowledgeChunkModel.source_url,
                func.min(KnowledgeChunkModel.source_domain),
                func.min(KnowledgeChunkModel.title),
                func.count(),
                func.count(KnowledgeChunkModel.embedding),
                func.count(KnowledgeChunkModel.published_at),
                func.min(KnowledgeChunkModel.published_at),
                func.max(KnowledgeChunkModel.collected_at),
            ).group_by(KnowledgeChunkModel.source_url)
        )
        rows = [
            DocumentRow(
                source_url=url,
                source_domain=domain,
                title=title,
                chunks=int(chunks or 0),
                chunks_embedded=int(embedded or 0),
                chunks_with_published_at=int(published or 0),
                first_published_at=first_published,
                last_collected_at=collected,
            )
            for (
                url,
                domain,
                title,
                chunks,
                embedded,
                published,
                first_published,
                collected,
            ) in result.all()
        ]
        logger.info("[AiLabPgRepository] list_documents <- count=%d", len(rows))
        return rows

    async def count_events(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(PleEventModel))
        return int(result.scalar_one())


def _split_sources(raw: str | None) -> tuple[str, ...]:
    """`sources`는 개행으로 이은 URL 목록이다. 빈 줄은 출처가 아니다."""
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(SOURCE_SEPARATOR) if part.strip())
