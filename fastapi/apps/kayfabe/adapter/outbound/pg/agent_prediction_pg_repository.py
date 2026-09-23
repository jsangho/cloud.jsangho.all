"""AI 예측 저장·조회 어댑터 (Neon PostgreSQL).

경기 정보(`MatchContext`)는 `ple_matches.card_json`에서 뽑는다 — 카드가 이미 저장돼
있으므로 에이전트에게 넘길 사실을 따로 관리하지 않는다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.agent_prediction_orm import (
    SOURCE_SEPARATOR,
    AgentPredictionModel,
    AgentReportModel,
    PredictionRetrievalModel,
)
from kayfabe.adapter.outbound.orm.ple_orm import PleEventModel, PleMatchModel
from kayfabe.app.dtos.agent_prediction_dto import MatchContext, MatchOption
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
    MatchNotFoundError,
)
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentPrediction,
    AgentReport,
    AgentRuntime,
    KnowledgeRetrieval,
    PredictionSource,
)

logger = logging.getLogger("uvicorn.error")


class AgentPredictionPgRepository(AgentPredictionRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_event(self, *, event_slug: str) -> list[AgentPrediction]:
        stmt = (
            select(AgentPredictionModel)
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            .where(PleEventModel.slug == event_slug)
            .order_by(AgentPredictionModel.id)
        )
        rows = (await self.db.scalars(stmt)).all()
        logger.info(
            "[AgentPredictionPgRepository] list_by_event <- Neon | event=%s | %d건",
            event_slug,
            len(rows),
        )
        return [_to_entity(row, event_slug) for row in rows]

    async def load_contexts(
        self, *, event_slug: str, match_keys: Sequence[str]
    ) -> list[MatchContext]:
        event = await self._event(event_slug)
        stmt = (
            select(PleMatchModel)
            .where(PleMatchModel.event_id == event.id)
            .order_by(PleMatchModel.sort_order, PleMatchModel.id)
        )
        rows = (await self.db.scalars(stmt)).all()
        wanted = set(match_keys)
        if wanted:
            rows = [row for row in rows if row.match_key in wanted]

        contexts = []
        for row in rows:
            context = _to_context(row, event)
            if context is None:
                # 선택지를 못 읽는 카드에는 예측을 만들 수 없다. 조용히 건너뛰되
                # 로그로 남긴다 — 카드 형식이 바뀐 신호일 수 있다.
                logger.warning(
                    "[AgentPredictionPgRepository] 카드에서 선택지를 읽지 못함 | match=%s",
                    row.match_key,
                )
                continue
            contexts.append(context)
        return contexts

    async def existing_match_keys(self, *, event_slug: str) -> set[str]:
        stmt = (
            select(AgentPredictionModel.match_key)
            .join(PleEventModel, AgentPredictionModel.event_id == PleEventModel.id)
            .where(PleEventModel.slug == event_slug)
        )
        return set((await self.db.scalars(stmt)).all())

    async def save(self, prediction: AgentPrediction) -> None:
        event = await self._event(prediction.event_slug)

        # 경기당 예측은 하나다. 재생성이면 기존 행을 지우고 새로 넣는다 —
        # 리포트까지 갈아끼워야 해서 부분 갱신보다 이쪽이 단순하다.
        await self.db.execute(
            delete(AgentPredictionModel).where(
                AgentPredictionModel.event_id == event.id,
                AgentPredictionModel.match_key == prediction.match_key,
            )
        )

        row = AgentPredictionModel(
            event_id=event.id,
            match_key=prediction.match_key,
            pick=prediction.pick,
            pick_name=prediction.pick_name,
            win_probability=prediction.win_probability,
            confidence=prediction.confidence,
            rationale=prediction.rationale,
            source=str(prediction.source),
            generated_at=prediction.generated_at,
            reports=[
                AgentReportModel(
                    agent=str(report.agent),
                    pick=report.pick,
                    weight=report.weight,
                    summary=report.summary,
                    sources=SOURCE_SEPARATOR.join(report.sources),
                    # 실행 조건 (Phase 4). 기록이 없는 리포트는 세 칸 모두 NULL로
                    # 남는다 — 비어 있는 것이 "기록하지 않았다"는 정직한 상태다.
                    model_version=report.runtime.model if report.runtime else None,
                    prompt_version=(
                        report.runtime.prompt_version if report.runtime else None
                    ),
                    agent_version=(
                        report.runtime.agent_version if report.runtime else None
                    ),
                )
                for report in prediction.reports
            ],
            # 검색 기록 (Phase 3-13). 청크를 참조하지 않고 그때 값을 베껴 둔다 —
            # 재수집이 옛 청크를 지우므로 참조로는 증거가 남지 않는다.
            retrievals=[
                PredictionRetrievalModel(
                    rank=item.rank,
                    chunk_id=item.chunk_id,
                    source_url=item.source_url,
                    content_hash=item.content_hash,
                    source_revision_id=item.source_revision_id,
                    source_revised_at=item.source_revised_at,
                    published_at=item.published_at,
                    distance=item.distance,
                )
                for item in prediction.retrievals
            ],
        )
        self.db.add(row)
        await self.db.flush()

    async def _event(self, event_slug: str) -> PleEventModel:
        event = await self.db.scalar(
            select(PleEventModel).where(PleEventModel.slug == event_slug)
        )
        if event is None:
            raise MatchNotFoundError(f"이벤트를 찾을 수 없습니다: {event_slug}")
        return event


def _to_entity(row: AgentPredictionModel, event_slug: str) -> AgentPrediction:
    return AgentPrediction(
        event_slug=event_slug,
        match_key=row.match_key,
        pick=row.pick,
        pick_name=row.pick_name,
        win_probability=row.win_probability,
        confidence=row.confidence,
        rationale=row.rationale,
        source=PredictionSource(row.source),
        generated_at=row.generated_at,
        reports=tuple(
            AgentReport(
                agent=AgentKind(report.agent),
                pick=report.pick,
                weight=report.weight,
                summary=report.summary,
                sources=tuple(s for s in report.sources.split(SOURCE_SEPARATOR) if s),
                runtime=_to_runtime(report),
            )
            for report in row.reports
        ),
        # 읽는 쪽도 채운다 — 한쪽만 매핑하면 왕복시킨 엔티티가 기록을 조용히 잃는다.
        retrievals=tuple(
            KnowledgeRetrieval(
                rank=item.rank,
                chunk_id=item.chunk_id,
                source_url=item.source_url,
                content_hash=item.content_hash,
                source_revision_id=item.source_revision_id,
                source_revised_at=item.source_revised_at,
                published_at=item.published_at,
                distance=item.distance,
            )
            for item in row.retrievals
        ),
    )


def _to_runtime(report: AgentReportModel) -> AgentRuntime | None:
    """실행 조건 기록 (Phase 4). **`agent_version`이 있는지로 판단한다.**

    셋 중 이 칸만 기록된 모든 리포트에 존재한다 — 모델과 프롬프트는 LLM을 부른
    리포트에만 있다. `model_version`을 기준으로 삼으면 오즈 에이전트의 기록이
    통째로 "기록 없음"이 되어, 기록하지 않은 옛 행과 구분되지 않는다.
    """
    if report.agent_version is None:
        return None
    return AgentRuntime(
        agent_version=report.agent_version,
        model=report.model_version,
        prompt_version=report.prompt_version,
    )


def _to_context(row: PleMatchModel, event: PleEventModel) -> MatchContext | None:
    try:
        card: dict[str, Any] = json.loads(row.card_json)
    except (TypeError, ValueError):
        return None

    options = _options_from_card(card)
    if not options:
        return None

    return MatchContext(
        event_slug=event.slug,
        event_label=event.label,
        match_key=row.match_key,
        title=row.title,
        match_format=row.format,
        options=options,
        bookmaker_decimal=_odds_from_card(card, len(options)),
    )


def _options_from_card(card: dict[str, Any]) -> tuple[MatchOption, ...]:
    """카드 JSON → 선택지. `pick` 값은 `ple_matches.winner_pick`과 같은 형식이다."""
    if card.get("format") == "singles":
        sides = []
        for pick in ("left", "right"):
            side = card.get(pick) or {}
            name = str(side.get("name", "")).strip()
            if not name:
                return ()
            sides.append(
                MatchOption(
                    pick=pick, name=name, is_champion=bool(side.get("isChampion"))
                )
            )
        return tuple(sides)

    competitors = card.get("competitors") or []
    if not isinstance(competitors, list) or not competitors:
        return ()
    return tuple(
        MatchOption(
            pick=str(index),
            name=str(competitor.get("name", f"#{index + 1}")),
            is_champion=bool(competitor.get("isChampion")),
        )
        for index, competitor in enumerate(competitors)
    )


def _odds_from_card(
    card: dict[str, Any], option_count: int
) -> tuple[float, ...] | None:
    """배당이 없거나 선택지 수와 어긋나면 `None` — 오즈 에이전트가 의견 없음을 낸다."""
    odds = card.get("bookmakerDecimal")
    values: list[Any]
    if isinstance(odds, dict):
        values = [odds.get("left"), odds.get("right")]
    elif isinstance(odds, list):
        values = list(odds)
    else:
        return None

    if len(values) != option_count:
        return None
    try:
        decimals = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    return decimals if all(value > 0 for value in decimals) else None
