"""오즈 수집가 — 북메이커 배당의 내재 확률로 판단한다.

**LLM을 쓰지 않는다.** 판단 근거가 숫자뿐이라 추론이 필요 없고, 그래서 이 에이전트는
비용도 지연도 없다. 세 에이전트 중 유일하게 항상 돌 수 있는 축이다.

기존 `ple_ai.derive_ai_pick_from_card()`와 고르는 쪽은 같지만(최저 배당) 결과가 다르다 —
그쪽은 "누구를 고를지"만 내놓고, 이쪽은 **얼마나 확신하는지(`weight`)** 를 함께 낸다.
그 값이 합성 단계에서 서사·루머와 겨루는 무게가 된다.
"""

from __future__ import annotations

from kayfabe.app.dtos.agent_prediction_dto import MatchContext
from kayfabe.app.ports.output.odds_scout_port import OddsScoutPort
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    AgentRuntime,
)

_NO_ODDS = "배당 정보가 없어 판단하지 않았습니다."

#: 이 에이전트 **로직**의 판 (Phase 4). 오버라운드 제거 방식이나 선택 기준이 바뀌면
#: 올린다 — 같은 배당에서 다른 확신도가 나오기 때문이다.
AGENT_VERSION = "odds@1"

#: **모델도 프롬프트도 없다.** 이 에이전트는 LLM을 쓰지 않으므로 두 칸은 영구히
#: 비어 있고, 그것이 이 축의 사실이다. 셋을 다 채우려고 없는 값을 만들지 않는다.
_RUNTIME = AgentRuntime(agent_version=AGENT_VERSION)


class BookmakerOddsScout(OddsScoutPort):
    async def analyze(self, context: MatchContext) -> AgentReport:
        probabilities = _implied_probabilities(context.bookmaker_decimal)
        if probabilities is None or len(probabilities) != len(context.options):
            return AgentReport(
                agent=AgentKind.ODDS,
                pick=None,
                weight=0.0,
                summary=_NO_ODDS,
                runtime=_RUNTIME,
            )

        best = max(range(len(probabilities)), key=lambda i: probabilities[i])
        option = context.options[best]
        share = probabilities[best]
        decimal = (context.bookmaker_decimal or ())[best]

        return AgentReport(
            agent=AgentKind.ODDS,
            pick=option.pick,
            # 내재 확률을 그대로 확신도로 쓴다. 배당이 팽팽하면(1.9 대 1.9) 0.5에
            # 가까워져 서사·루머 쪽 의견이 결과를 가르게 된다.
            weight=share,
            summary=(
                f"배당 {decimal:g}로 {option.name}이(가) 가장 낮습니다 "
                f"(내재 확률 {share * 100:.0f}%)."
            ),
            # 배당은 카드에 이미 실려 온 값이라 인용할 외부 URL이 없다.
            sources=(),
            runtime=_RUNTIME,
        )


def _implied_probabilities(
    decimals: tuple[float, ...] | None,
) -> tuple[float, ...] | None:
    """소수 배당 → 오버라운드를 제거한 내재 확률.

    배당의 역수(1/d)는 북메이커 마진 때문에 합이 1을 넘는다. 그대로 쓰면 확신도가
    실제보다 부풀므로 합이 1이 되도록 정규화한다.
    """
    if not decimals or any(value <= 0 for value in decimals):
        return None
    raw = [1.0 / value for value in decimals]
    total = sum(raw)
    if total <= 0:
        return None
    return tuple(value / total for value in raw)
