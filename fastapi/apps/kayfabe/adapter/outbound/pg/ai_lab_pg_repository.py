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

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    SOURCE_SEPARATOR,
    AgentPredictionModel,
    AgentReportModel,
    PredictionRetrievalModel,
)
from kayfabe.adapter.outbound.orm.knowledge_chunk_orm import KnowledgeChunkModel
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.adapter.outbound.pg.agent_prediction_pg_repository import (
    options_from_card,
)
from kayfabe.app.dtos.agent_prediction_dto import MatchOption
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_evaluation import RetrievalRow
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_readiness import EventRow

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
                # 경기 행이 아직 있는가 (Stage 9). `title`이 비었는지로 대신 볼 수도
                # 있지만 그것은 값의 성질이고, 여기서 묻는 것은 **행의 존재**다.
                PleMatchModel.id.label("match_id"),
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
                # 표본의 계보 (Phase 3-7). 결과가 **시스템 밖에서** 이미 알려져
                # 있었는지는 어떤 시각 컬럼으로도 알 수 없어 따로 적어 둔 값이다.
                AgentPredictionModel.outcome_known_externally,
                AgentPredictionModel.provenance_note,
                # 검색 질의 (Phase 3). 감사 화면만 읽는다 — 판정은 보지 않는다.
                AgentPredictionModel.knowledge_query,
                # 대회 날짜 (Phase 3-12). 코퍼스 규칙이 "인용 문서가 경기보다 앞선
                # 개정본인가"를 재는 데 쓴다. 컬럼 하나가 늘 뿐 조인은 그대로다.
                PleEventModel.start_date,
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
                outcome_known_externally=row.outcome_known_externally,
                provenance_note=row.provenance_note,
                event_start_date=row.start_date,
                match_exists=row.match_id is not None,
                knowledge_query=row.knowledge_query,
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
                # 실행 조건 (Phase 4). 감사 화면만 읽는다 — 집계는 보지 않는다.
                AgentReportModel.agent_version,
                AgentReportModel.prompt_version,
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
                agent_version=row.agent_version,
                prompt_version=row.prompt_version,
            )
            for row in result.all()
        ]
        logger.info("[AiLabPgRepository] list_reports <- count=%d", len(rows))
        return rows

    async def list_retrievals(self) -> list[RetrievalRow]:
        """예측이 그때 읽은 청크 기록 (Phase 3-13 Stage 4-B).

        **판정이 보는 것은 여전히 두 칸뿐이다**(`source_url`·`source_revised_at`).
        나머지는 감사 화면(Phase 9)이 증거를 늘어놓을 때 쓰고, 그 값이 판정을
        바꾸지 않는다 — `RetrievalRow`의 주석이 그 경계를 적어 두고 있다.

        본문과 해시는 여전히 뽑지 않는다. 화면에 원문을 싣지 않기로 했고(§4-8),
        해시는 대조할 상대가 있을 때 필요한 값이다.

        옛 예측에는 행이 아예 없어서 결과가 비는 것이 정상이다.
        """
        result = await self.db.execute(
            select(
                PleEventModel.slug,
                AgentPredictionModel.match_key,
                PredictionRetrievalModel.source_url,
                PredictionRetrievalModel.source_revised_at,
                PredictionRetrievalModel.rank,
                PredictionRetrievalModel.source_revision_id,
                PredictionRetrievalModel.published_at,
                PredictionRetrievalModel.distance,
            )
            .join(
                AgentPredictionModel,
                PredictionRetrievalModel.prediction_id == AgentPredictionModel.id,
            )
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            .order_by(
                PredictionRetrievalModel.prediction_id, PredictionRetrievalModel.rank
            )
        )
        rows = [
            RetrievalRow(
                event_slug=row.slug,
                match_key=row.match_key,
                source_url=row.source_url,
                source_revised_at=row.source_revised_at,
                rank=row.rank,
                source_revision_id=row.source_revision_id,
                published_at=row.published_at,
                distance=row.distance,
            )
            for row in result.all()
        ]
        logger.info("[AiLabPgRepository] list_retrievals <- count=%d", len(rows))
        return rows

    async def corpus_facts(self) -> CorpusFacts:
        result = await self.db.execute(
            select(
                func.count(),
                func.count(KnowledgeChunkModel.embedding),
                func.count(KnowledgeChunkModel.published_at),
                # 계보 (Phase 3-13). 시간 판정이 보는 것은 발행일이 아니라 이쪽이다.
                func.count(KnowledgeChunkModel.source_revised_at),
                func.count(func.distinct(KnowledgeChunkModel.source_url)),
                func.count(func.distinct(KnowledgeChunkModel.source_domain)),
                func.max(KnowledgeChunkModel.collected_at),
            ).select_from(KnowledgeChunkModel)
        )
        total, embedded, published, revisions, documents, domains, collected = (
            result.one()
        )
        facts = CorpusFacts(
            chunks_total=int(total or 0),
            chunks_embedded=int(embedded or 0),
            chunks_with_published_at=int(published or 0),
            chunks_with_revision=int(revisions or 0),
            documents=int(documents or 0),
            domains=int(domains or 0),
            last_collected_at=collected,
        )
        logger.info(
            "[AiLabPgRepository] corpus_facts <- 청크=%d 계보=%d 발행일=%d",
            facts.chunks_total,
            facts.chunks_with_revision,
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
                # 계보 (Phase 3-12). **가장 늦은** 개정본을 집는다 — 경기 뒤 개정본이
                # 하나라도 섞여 있으면 그 문서는 통과시키지 않는다.
                func.count(KnowledgeChunkModel.source_revised_at),
                func.max(KnowledgeChunkModel.source_revised_at),
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
                chunks_with_revision=int(revisions or 0),
                latest_revised_at=latest_revised,
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
                revisions,
                latest_revised,
            ) in result.all()
        ]
        logger.info("[AiLabPgRepository] list_documents <- count=%d", len(rows))
        return rows

    async def count_events(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(PleEventModel))
        return int(result.scalar_one())

    async def list_events(self) -> list[EventRow]:
        """대회 전체 + 경기 수 (Phase 8). **한 번의 SELECT다.**

        경기 수는 `outerjoin` + `count(match_id)`로 센다 — 경기가 없는 대회도 0으로
        남아야 하기 때문이다. `count(*)`로 세면 그런 대회가 1이 된다.
        """
        result = await self.db.execute(
            select(
                PleEventModel.slug,
                PleEventModel.label,
                PleEventModel.start_date,
                PleEventModel.status,
                func.count(PleMatchModel.id),
            )
            .outerjoin(PleMatchModel, PleMatchModel.event_id == PleEventModel.id)
            .group_by(
                PleEventModel.slug,
                PleEventModel.label,
                PleEventModel.start_date,
                PleEventModel.status,
            )
        )
        rows = [
            EventRow(
                slug=slug,
                label=label,
                start_date=start_date,
                status=status,
                matches=int(matches or 0),
            )
            for slug, label, start_date, status, matches in result.all()
        ]
        logger.info("[AiLabPgRepository] list_events <- count=%d", len(rows))
        return rows

    async def load_match_options(
        self, *, event_slug: str, match_key: str
    ) -> tuple[MatchOption, ...]:
        """감사 화면 한 건에만 붙는 쿼리다 (Phase 5).

        `list_predictions`에 `card_json`을 얹지 않은 이유는 그쪽이 목록·개요·평가가
        함께 쓰는 전량 조회라서다 — 화면이 쓰지도 않는 카드 원문을 모든 행에
        딸려 보내게 된다. 재현은 한 건짜리 화면에만 있으므로 그 자리에서만 읽는다.
        """
        result = await self.db.execute(
            select(PleMatchModel.card_json)
            .join(PleEventModel, PleMatchModel.event_id == PleEventModel.id)
            .where(PleEventModel.slug == event_slug)
            .where(PleMatchModel.match_key == match_key)
        )
        raw = result.scalar_one_or_none()
        if raw is None:
            # 경기 행이 사라졌다. 재현 불가로 남을 뿐 오류가 아니다.
            return ()
        try:
            card = json.loads(raw)
        except (TypeError, ValueError):
            return ()
        return options_from_card(card) if isinstance(card, dict) else ()


def _split_sources(raw: str | None) -> tuple[str, ...]:
    """`sources`는 개행으로 이은 URL 목록이다. 빈 줄은 출처가 아니다."""
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(SOURCE_SEPARATOR) if part.strip())
