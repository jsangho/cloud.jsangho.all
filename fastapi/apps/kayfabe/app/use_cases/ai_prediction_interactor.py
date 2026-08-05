"""AI 승부예측 코디네이터 — 멀티 에이전트의 허브.

`_docs/ai-match-predictions-harness.md` §2-D2. **앱 레벨 스타 토폴로지의 허브가
아니라 kayfabe 안의 유스케이스다.** 세 에이전트에게 같은 경기를 물어보고, 돌아온
리포트를 도메인 합성 규칙으로 합쳐 예측 하나를 만든다.

이 유스케이스는 Gemini도 pgvector도 크롤러도 모른다 — 전부 출력 포트 뒤에 있다.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from kayfabe.app.dtos.agent_prediction_dto import (
    AgentPredictionDto,
    AgentReportDto,
    GeneratePredictionCommand,
    GenerationSummary,
    KnowledgeChunk,
    MatchContext,
    MatchOption,
)
from kayfabe.app.ports.input.ai_prediction_use_case import AiPredictionUseCase
from kayfabe.app.ports.output.agent_prediction_repository import (
    AgentPredictionRepository,
)
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.app.ports.output.prediction_knowledge_port import (
    KnowledgeSourceUnavailableError,
    PredictionKnowledgePort,
)
from kayfabe.app.ports.output.rumor_scout_port import RumorScoutPort
from kayfabe.app.ports.output.storyline_analyst_port import StorylineAnalystPort
from kayfabe.domain.entities.agent_prediction import (
    AgentPrediction,
    AgentReport,
    PredictionSource,
)
from kayfabe.domain.services.prediction_synthesis import (
    ReportsUnavailableError,
    synthesize,
)

logger = logging.getLogger("uvicorn.error")

#: 물어보는 에이전트 수. 합의도 계산의 분모라 실제 호출 수와 같아야 한다.
AGENT_COUNT = 3

#: 경기 하나에 딸려 보내는 지식 청크 수. `wrestler_chat_repository`와 같은 값.
KNOWLEDGE_TOP_K = 5


class AiPredictionInteractor(AiPredictionUseCase):
    def __init__(
        self,
        repository: AgentPredictionRepository,
        knowledge: PredictionKnowledgePort,
        storyline: StorylineAnalystPort,
        odds: OddsScoutPort,
        rumor: RumorScoutPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._knowledge = knowledge
        self._storyline = storyline
        self._odds = odds
        self._rumor = rumor
        self._clock = clock or (lambda: datetime.now(UTC))

    async def list_predictions(self, *, event_slug: str) -> list[AgentPredictionDto]:
        predictions = await self._repository.list_by_event(event_slug=event_slug)
        return [_to_dto(prediction) for prediction in predictions]

    async def generate(self, command: GeneratePredictionCommand) -> GenerationSummary:
        contexts = await self._repository.load_contexts(
            event_slug=command.event_slug, match_keys=command.match_keys
        )
        targets = await self._targets(command, contexts)
        skipped = len(contexts) - len(targets)

        generated = 0
        failed = 0
        for context in targets:
            prediction = await self._predict_one(context)
            if prediction is None:
                failed += 1
                continue
            await self._repository.save(prediction)
            generated += 1

        logger.info(
            "[kayfabe.ai_prediction] 생성 완료 | event=%s | 생성=%d 건너뜀=%d 실패=%d",
            command.event_slug,
            generated,
            skipped,
            failed,
        )
        return GenerationSummary(
            requested=len(contexts),
            generated=generated,
            skipped=skipped,
            failed=failed,
        )

    async def _targets(
        self, command: GeneratePredictionCommand, contexts: list[MatchContext]
    ) -> list[MatchContext]:
        if command.force:
            return contexts
        existing = await self._repository.existing_match_keys(
            event_slug=command.event_slug
        )
        return [c for c in contexts if c.match_key not in existing]

    async def _predict_one(self, context: MatchContext) -> AgentPrediction | None:
        """경기 하나. 실패는 이 경기에서 끝나고 다음 경기로 넘어간다."""
        knowledge = await self._search_knowledge(context)
        reports = await self._collect_reports(context, knowledge)

        try:
            synthesis = synthesize(
                reports,
                agent_count=AGENT_COUNT,
                options=[option.pick for option in context.options],
            )
        except ReportsUnavailableError:
            # 아무도 의견을 내지 못했다 — 화면은 그래도 예측을 보여줘야 하므로
            # 북메이커 배당으로 강등한다. 대신 source에 그 사실을 남긴다.
            return self._bookmaker_fallback(context)

        option = _option_for(context, synthesis.pick)
        if option is None:
            # 합성까지 갔는데 카드에 없는 pick이면 저장하지 않는다. 채점이 불가능한
            # 예측을 남기느니 실패로 두는 편이 낫다.
            logger.warning(
                "[kayfabe.ai_prediction] 카드에 없는 pick | match=%s | pick=%s",
                context.match_key,
                synthesis.pick,
            )
            return None

        return AgentPrediction(
            event_slug=context.event_slug,
            match_key=context.match_key,
            pick=synthesis.pick,
            pick_name=option.name,
            win_probability=synthesis.win_probability,
            confidence=synthesis.confidence,
            rationale=_compose_rationale(reports, synthesis.pick, option.name),
            source=PredictionSource.AGENTS,
            generated_at=self._clock(),
            reports=tuple(reports),
        )

    async def _search_knowledge(self, context: MatchContext) -> list[KnowledgeChunk]:
        """지식 조회 실패는 이 경기의 실패가 아니다.

        서사·루머 에이전트는 근거가 없으면 의견 없음을 내고, 오즈 에이전트는 애초에
        지식을 쓰지 않는다. 그러면 합의도가 낮은 예측이 나오는데, 그건 **정직한 결과**다 —
        지식이 없어서 확신이 낮다는 사실이 숫자에 그대로 드러난다.
        """
        try:
            return await self._knowledge.search(
                query=_knowledge_query(context), top_k=KNOWLEDGE_TOP_K
            )
        except KnowledgeSourceUnavailableError as exc:
            logger.warning(
                "[kayfabe.ai_prediction] 지식 조회 실패 | match=%s | %s",
                context.match_key,
                exc,
            )
            return []

    async def _collect_reports(
        self, context: MatchContext, knowledge: Sequence[KnowledgeChunk]
    ) -> list[AgentReport]:
        """세 에이전트를 동시에 부른다. 하나가 죽어도 나머지로 합성한다."""
        results = await asyncio.gather(
            self._storyline.analyze(context, knowledge),
            self._odds.analyze(context),
            self._rumor.analyze(context, knowledge),
            return_exceptions=True,
        )

        reports: list[AgentReport] = []
        allowed = {option.pick for option in context.options}
        for result in results:
            if isinstance(result, BaseException):
                logger.warning(
                    "[kayfabe.ai_prediction] 에이전트 실패 | match=%s | %r",
                    context.match_key,
                    result,
                )
                continue
            reports.append(_sanitized(result, allowed, context.match_key))
        return reports

    def _bookmaker_fallback(self, context: MatchContext) -> AgentPrediction | None:
        favorite = _bookmaker_favorite(context)
        if favorite is None or (probability := _implied_probability(context)) is None:
            logger.warning(
                "[kayfabe.ai_prediction] 폴백 불가 | match=%s | 배당 없음",
                context.match_key,
            )
            return None

        logger.info(
            "[kayfabe.ai_prediction] 북메이커 폴백 | match=%s | pick=%s",
            context.match_key,
            favorite.pick,
        )
        return AgentPrediction(
            event_slug=context.event_slug,
            match_key=context.match_key,
            pick=favorite.pick,
            pick_name=favorite.name,
            #: 배당의 내재 확률이다. 임의의 0.5보다 정직하다 — 시장이 실제로 매긴 값이다.
            win_probability=probability,
            # 에이전트가 아무도 답하지 못했으므로 합의는 없다.
            confidence=0.0,
            rationale=(
                "분석 에이전트의 의견을 모으지 못해 북메이커 배당이 가장 낮은 쪽을 "
                f"골랐습니다: {favorite.name}."
            ),
            source=PredictionSource.BOOKMAKER_FALLBACK,
            generated_at=self._clock(),
            reports=(),
        )


def _knowledge_query(context: MatchContext) -> str:
    names = " ".join(option.name for option in context.options)
    return f"{context.title} {names}".strip()


def _option_for(context: MatchContext, pick: str) -> MatchOption | None:
    return next((o for o in context.options if o.pick == pick), None)


def _sanitized(report: AgentReport, allowed: set[str], match_key: str) -> AgentReport:
    """카드에 없는 pick을 낸 리포트는 **의견 없음으로 낮춘다.**

    버리지 않는 이유는 요약 자체가 근거로 쓸 만하기 때문이고, 그대로 두지 않는
    이유는 존재하지 않는 선택지가 득표를 가져가면 승률이 통째로 틀어지기 때문이다.
    """
    if report.pick is None or report.pick in allowed:
        return report
    logger.warning(
        "[kayfabe.ai_prediction] 리포트의 pick이 카드에 없음 | match=%s | agent=%s | pick=%s",
        match_key,
        report.agent,
        report.pick,
    )
    return AgentReport(
        agent=report.agent,
        pick=None,
        weight=0.0,
        summary=report.summary,
        sources=report.sources,
    )


def _bookmaker_favorite(context: MatchContext) -> MatchOption | None:
    """배당이 가장 낮은 선택지. `ple_ai.derive_ai_pick_from_card`와 같은 규칙이다."""
    decimals = context.bookmaker_decimal
    if not decimals or len(decimals) != len(context.options):
        return None
    if any(value <= 0 for value in decimals):
        return None
    best = min(range(len(decimals)), key=lambda i: decimals[i])
    return context.options[best]


def _implied_probability(context: MatchContext) -> float | None:
    """배당 favorite의 내재 확률. 오버라운드(북메이커 마진)를 정규화로 걷어낸다."""
    decimals = context.bookmaker_decimal
    if not decimals or len(decimals) != len(context.options):
        return None
    if any(value <= 0 for value in decimals):
        return None
    inverses = [1.0 / value for value in decimals]
    total = sum(inverses)
    return max(inverses) / total if total > 0 else None


def _compose_rationale(
    reports: Sequence[AgentReport], pick: str, pick_name: str
) -> str:
    """근거 문장을 리포트 요약으로 엮는다.

    여기서 LLM을 한 번 더 부르지 않는다 — 호출이 경기마다 하나 더 늘고, 이미 확보한
    근거를 다시 요약하다 원문에 없는 말이 섞일 수 있다.
    """
    agreeing = [r for r in reports if r.pick == pick]
    opinionated = [r for r in reports if r.has_opinion]

    head = f"{len(agreeing)}/{len(opinionated)} 분석이 {pick_name}을(를) 골랐습니다."
    bodies = [
        f"- {report.agent}: {report.summary}" for report in reports if report.summary
    ]
    return "\n".join([head, *bodies])


def _to_dto(prediction: AgentPrediction) -> AgentPredictionDto:
    return AgentPredictionDto(
        match_key=prediction.match_key,
        pick=prediction.pick,
        pick_name=prediction.pick_name,
        win_probability=prediction.win_probability,
        confidence=prediction.confidence,
        rationale=prediction.rationale,
        source=str(prediction.source),
        generated_at=prediction.generated_at,
        reports=tuple(
            AgentReportDto(
                agent=str(report.agent),
                pick=report.pick,
                weight=report.weight,
                summary=report.summary,
                sources=report.sources,
            )
            for report in prediction.reports
        ),
    )
