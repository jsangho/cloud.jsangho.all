"""오즈 수집가 — 북메이커 배당의 내재 확률로 판단한다.

**LLM을 쓰지 않는다.** 판단 근거가 숫자뿐이라 추론이 필요 없고, 그래서 이 에이전트는
비용도 지연도 없다. 세 에이전트 중 유일하게 항상 돌 수 있는 축이다.

기존 `ple_ai.derive_ai_pick_from_card()`와 고르는 쪽은 같지만(최저 배당) 결과가 다르다 —
그쪽은 "누구를 고를지"만 내놓고, 이쪽은 **얼마나 확신하는지(`weight`)** 를 함께 낸다.
그 값이 합성 단계에서 서사·루머와 겨루는 무게가 된다.

**여러 북메이커를 모은다** (2026-09-30). 한 곳만 보던 때는 그 한 곳이 틀리면 축 전체가
틀렸고, 무엇보다 "북메이커들이 서로 다른 말을 하고 있다"는 사실을 표현할 자리가 없었다.
합의·분산 계산은 `domain/services/odds_consensus.py`에 있다.
"""

from __future__ import annotations

from kayfabe.app.dtos.agent_prediction_dto import MatchContext
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)
from kayfabe.domain.services.odds_consensus import (
    BookmakerQuote,
    OddsConsensus,
    confidence_from,
    consensus,
)

_NO_ODDS = "배당 정보가 없어 판단하지 않았습니다."

#: 이 에이전트 **로직**의 판 (Phase 4). 오버라운드 제거 방식이나 선택 기준이 바뀌면
#: 올린다 — 같은 배당에서 다른 확신도가 나오기 때문이다.
#:
#: `odds@2` (2026-09-30): 북메이커 하나 → 여러 곳의 중앙값 + 분산 감쇠. 호가가 한
#: 곳뿐인 경기의 값은 `odds@1`과 같지만, 산식이 달라졌으므로 판을 올린다.
AGENT_VERSION = "odds@2"

#: **모델도 프롬프트도 없다.** 이 에이전트는 LLM을 쓰지 않으므로 두 칸은 영구히
#: 비어 있고, 그것이 이 축의 사실이다. 셋을 다 채우려고 없는 값을 만들지 않는다.
_RUNTIME = AgentRuntime(agent_version=AGENT_VERSION)


class BookmakerOddsScout(OddsScoutPort):
    async def analyze(self, context: MatchContext) -> AgentReport:
        merged = consensus(_quotes_of(context), len(context.options))
        if merged is None:
            return AgentReport(
                agent=AgentKind.ODDS,
                pick=None,
                weight=0.0,
                summary=_NO_ODDS,
                runtime=_RUNTIME,
            )

        best = max(
            range(len(merged.probabilities)), key=lambda i: merged.probabilities[i]
        )
        option = context.options[best]

        return AgentReport(
            agent=AgentKind.ODDS,
            pick=option.pick,
            # 합의 확률을 확신도로 쓰되, 북메이커끼리 갈릴수록 균등분포 쪽으로 당긴다.
            # 배당이 팽팽하면(1.9 대 1.9) 0.5에 가까워져 서사·루머가 결과를 가른다.
            weight=confidence_from(merged, best),
            summary=_summary(merged, option.name, best),
            # 배당은 카드에 이미 실려 온 값이라 인용할 외부 URL이 없다. 호가에
            # 출처가 적혀 있으면 그것을 싣는다 — 어디서 본 숫자인지가 근거다.
            sources=_sources(context),
            runtime=_RUNTIME,
        )


def _quotes_of(context: MatchContext) -> tuple[BookmakerQuote, ...]:
    """호가 목록. 없으면 카드에 직접 적힌 배당 한 벌을 이름 없는 호가로 감싼다.

    **옛 카드를 위한 길이다.** `bookmakerQuotes`를 적지 않은 경기가 아직 많고,
    그쪽 판단이 이 변경으로 달라지면 안 된다 — 호가 하나짜리 합의는 분산이 0이라
    `odds@1`과 같은 값을 낸다.
    """
    if context.bookmaker_quotes:
        return context.bookmaker_quotes
    if context.bookmaker_decimal is None:
        return ()
    return (BookmakerQuote(book="", decimals=context.bookmaker_decimal),)


def _summary(merged: OddsConsensus, name: str, index: int) -> str:
    """**몇 곳이 무엇을 말했는지**까지 적는다. 확률만 적으면 근거가 사라진다."""
    share = f"{merged.probabilities[index] * 100:.0f}%"
    named = [book for book in merged.books if book]
    if len(named) <= 1:
        where = f"{named[0]} 배당" if named else "배당"
        return f"{where} 기준 {name}의 내재 확률이 {share}로 가장 높습니다."

    spread = f"{merged.dispersion * 100:.0f}%p"
    return (
        f"북메이커 {len(named)}곳({', '.join(named)}) 합의로 {name}이(가) {share}입니다 "
        f"— 곳별 편차 {spread}."
    )


def _sources(context: MatchContext) -> tuple[str, ...]:
    """호가에 적힌 출처. 중복은 접고 순서는 적힌 대로 둔다."""
    seen: dict[str, None] = {}
    for quote in context.bookmaker_quotes:
        if quote.source_url:
            seen.setdefault(quote.source_url, None)
    return tuple(seen)
