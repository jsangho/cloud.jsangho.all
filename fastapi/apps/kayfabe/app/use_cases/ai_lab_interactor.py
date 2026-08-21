"""AI LAB 유스케이스 (Phase 3-0·3-1).

읽어 온 행을 `ai_lab_integrity`에 넘겨 집계·판정을 받고, 시스템 상태를 **실측으로만**
만든다.

**가짜 초록불을 만들지 않는다** — 이 화면이 확인할 수 있는 것은 방금 자기가 한 조회와
DB에 남은 흔적뿐이다. Gemini가 지금 살아 있는지는 불러 봐야 알 수 있고, 이 화면은
LLM을 부르지 않기로 했으므로(§3-D1) 그 칸은 `unknown`으로 나간다. 초록불을 채우려고
헬스체크 호출을 넣으면 화면 진입이 곧 비용이 된다.
"""

from __future__ import annotations

import logging

from kayfabe.app.dtos.ai_lab_dto import (
    AgentReportItem,
    AiLabOverviewResponse,
    AiLabPredictionsResponse,
    PredictionEvent,
    PredictionItem,
    RecentPrediction,
    SystemComponent,
)
from kayfabe.app.ports.input.ai_lab_use_case import AiLabUseCase
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_integrity import (
    AgentActivity,
    CorpusFacts,
    PredictionRow,
    ReportRow,
    summarize_agents,
    summarize_integrity,
    summarize_predictions,
)

logger = logging.getLogger("uvicorn.error")

#: 개요 화면이 보여 주는 최근 예측 수. 전부 보내면 목록 화면(3-2)과 하는 일이 겹친다.
RECENT_LIMIT = 6


class AiLabInteractor(AiLabUseCase):
    def __init__(self, repository: AiLabRepository) -> None:
        self._repository = repository

    async def get_overview(self) -> AiLabOverviewResponse:
        predictions = await self._repository.list_predictions()
        reports = await self._repository.list_reports()
        corpus = await self._repository.corpus_facts()
        events_total = await self._repository.count_events()

        totals = summarize_predictions(predictions)
        integrity = summarize_integrity(
            predictions, reports, corpus, events_total=events_total
        )
        agents = summarize_agents(reports)

        logger.info(
            "[AiLabInteractor] get_overview | 예측=%d 채점=%d 청크=%d 일반화가능=%s",
            totals.total,
            totals.graded,
            corpus.chunks_total,
            integrity.generalizable,
        )

        return AiLabOverviewResponse(
            predictions=totals,
            integrity=integrity,
            system=_system_status(predictions, agents, corpus),
            agents=agents,
            recent=_recent(predictions),
        )

    async def list_predictions(self) -> AiLabPredictionsResponse:
        """저장된 예측 전체 + 리포트 + 무결성.

        **무결성을 목록과 같은 응답에 담는다.** 목록만 따로 받아 가면 화면이 적중률을
        맥락 없이 세울 수 있고, 같은 판정을 두 번 계산하게 된다 — 개요와 같은
        `summarize_integrity()`를 그대로 쓴다.
        """
        predictions = await self._repository.list_predictions()
        reports = await self._repository.list_reports()
        corpus = await self._repository.corpus_facts()
        events_total = await self._repository.count_events()

        grouped = _group_reports(reports)
        # 최근 생성이 위로. 같은 시각이면 대회·경기 순서를 지켜 재조회에도 흔들리지 않는다.
        ordered = sorted(
            predictions,
            key=lambda r: (r.generated_at, r.event_slug, r.match_key),
            reverse=True,
        )

        logger.info(
            "[AiLabInteractor] list_predictions | 예측=%d 리포트=%d",
            len(predictions),
            len(reports),
        )

        return AiLabPredictionsResponse(
            totals=summarize_predictions(predictions),
            integrity=summarize_integrity(
                predictions, reports, corpus, events_total=events_total
            ),
            events=_events(predictions),
            items=[
                PredictionItem(
                    event_slug=row.event_slug,
                    event_label=row.event_label,
                    match_key=row.match_key,
                    match_title=row.match_title,
                    pick=row.pick,
                    pick_name=row.pick_name,
                    win_probability=row.win_probability,
                    confidence=row.confidence,
                    rationale=row.rationale,
                    source=row.source,
                    generated_at=row.generated_at,
                    winner_name=row.winner_name,
                    correct=_correct(row),
                    reports=tuple(grouped.get((row.event_slug, row.match_key), ())),
                )
                for row in ordered
            ],
        )


def _correct(row: PredictionRow) -> bool | None:
    """채점 결과. **미채점은 `None`이다** — 실패(False)와 뭉치지 않는다."""
    if row.winner_pick is None:
        return None
    return row.pick == row.winner_pick


def _group_reports(
    reports: list[ReportRow],
) -> dict[tuple[str, str], list[AgentReportItem]]:
    """리포트를 경기별로 묶는다. 순서는 리포지토리가 준 순서(`id`)를 지킨다."""
    grouped: dict[tuple[str, str], list[AgentReportItem]] = {}
    for report in reports:
        grouped.setdefault((report.event_slug, report.match_key), []).append(
            AgentReportItem(
                agent=report.agent,
                pick=report.pick,
                weight=report.weight,
                summary=report.summary,
                sources=report.sources,
            )
        )
    return grouped


def _events(rows: list[PredictionRow]) -> list[PredictionEvent]:
    """예측이 **실제로 있는** 대회만. 목록을 화면에 박지 않는다."""
    counts: dict[str, tuple[str, int]] = {}
    for row in rows:
        label, count = counts.get(row.event_slug, (row.event_label, 0))
        counts[row.event_slug] = (label, count + 1)
    return [
        PredictionEvent(slug=slug, label=label, count=count)
        for slug, (label, count) in sorted(counts.items())
    ]


def _recent(rows: list[PredictionRow]) -> list[RecentPrediction]:
    """최근 생성 순. **미채점은 `correct=None`이다** — 실패(False)와 구분한다."""
    newest = sorted(rows, key=lambda r: r.generated_at, reverse=True)[:RECENT_LIMIT]
    return [
        RecentPrediction(
            event_slug=row.event_slug,
            event_label=row.event_label,
            match_key=row.match_key,
            match_title=row.match_title,
            pick_name=row.pick_name,
            win_probability=row.win_probability,
            confidence=row.confidence,
            source=row.source,
            generated_at=row.generated_at,
            winner_name=row.winner_name,
            correct=_correct(row),
        )
        for row in newest
    ]


def _system_status(
    predictions: list[PredictionRow],
    agents: list[AgentActivity],
    corpus: CorpusFacts,
) -> list[SystemComponent]:
    """실측만으로 만든 상태 카드."""
    return [
        SystemComponent(
            key="database",
            label="Data Pipeline",
            # 이 응답을 만들려고 방금 네 번 조회했다. 그 사실 자체가 증거다.
            state="operational",
            detail=f"예측·리포트·지식·대회를 방금 조회했습니다 (예측 {len(predictions)}건).",
        ),
        SystemComponent(
            key="knowledge",
            label="RAG",
            state=_knowledge_state(corpus),
            detail=_knowledge_detail(corpus),
        ),
        SystemComponent(
            key="engine",
            label="Prediction Engine",
            state="operational" if predictions else "empty",
            detail=_engine_detail(predictions),
        ),
        SystemComponent(
            key="agents",
            label="Agents",
            state="operational" if agents else "empty",
            detail=_agents_detail(agents),
        ),
        SystemComponent(
            key="llm",
            label="LLM (Gemini)",
            # 불러 봐야 알 수 있고, 이 화면은 부르지 않는다.
            state="unknown",
            detail="이 화면은 LLM을 호출하지 않으므로 가동 여부를 확인하지 않았습니다.",
        ),
    ]


def _knowledge_state(corpus: CorpusFacts) -> str:
    if corpus.chunks_total == 0:
        return "empty"
    if corpus.chunks_embedded < corpus.chunks_total:
        return "degraded"
    return "operational"


def _knowledge_detail(corpus: CorpusFacts) -> str:
    if corpus.chunks_total == 0:
        return "적재된 지식이 없습니다 — 에이전트는 의견 없음만 냅니다."
    missing = corpus.chunks_total - corpus.chunks_embedded
    head = (
        f"문서 {corpus.documents}건 · 청크 {corpus.chunks_total}건 "
        f"· 도메인 {corpus.domains}종"
    )
    if missing > 0:
        return f"{head}. 임베딩이 없는 청크 {missing}건은 검색되지 않습니다."
    return f"{head}. 전부 임베딩되어 검색 대상입니다."


def _engine_detail(predictions: list[PredictionRow]) -> str:
    if not predictions:
        return "저장된 예측이 없습니다."
    latest = max(row.generated_at for row in predictions)
    events = len({row.event_slug for row in predictions})
    return (
        f"예측 {len(predictions)}건 · 대회 {events}개 "
        f"· 마지막 생성 {latest.date().isoformat()}."
    )


def _agents_detail(agents: list[AgentActivity]) -> str:
    if not agents:
        return "리포트를 낸 에이전트가 없습니다."
    parts = [f"{a.agent} {a.with_pick}/{a.reports}" for a in agents]
    return "의견을 낸 리포트 / 전체 리포트 — " + " · ".join(parts)
