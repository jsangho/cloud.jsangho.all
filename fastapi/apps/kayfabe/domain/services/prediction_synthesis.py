"""에이전트 리포트 → 최종 pick·승률 합성. 순수 함수다.

`_docs/ai-match-predictions-harness.md` §5. LLM·DB·HTTP를 모르므로 고정 리포트
픽스처만으로 테스트가 돌아간다(하네스 §3-D3).

**에이전트별 기본 가중치를 여기에 박지 않는다.** 서사·오즈·루머 중 무엇을 더 믿을지는
아직 정해지지 않았고(하네스 §13-Q2), 근거 없는 숫자를 코드에 남기지 않기 위해서다.
이 함수는 리포트가 실어 온 `weight`를 그대로 정규화할 뿐이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kayfabe.domain.entities.agent_prediction import AgentReport


class ReportsUnavailableError(Exception):
    """의견을 낸 리포트가 하나도 없다. 클라이언트에는 503.

    "우열을 가리지 못했다"와 "물어보지 못했다"는 다른 상태다. 후자에 임의 승률
    0.5를 채워 넣지 않기 위해 예외로 구분한다(하네스 §3-D6).
    """


@dataclass(frozen=True)
class PredictionSynthesis:
    """합성 결과. 표시용 반올림은 하지 않는다 — 화면에서 한 번만 한다(§3-D4)."""

    pick: str
    win_probability: float
    confidence: float


def synthesize(
    reports: Sequence[AgentReport], *, agent_count: int
) -> PredictionSynthesis:
    """리포트를 합쳐 최종 예측을 만든다.

    `agent_count`는 **코디네이터가 물어본 에이전트 수**다. 리포트 목록의 길이가
    아니라 이 값을 받는 이유는, 실패해서 리포트를 못 낸 에이전트가 목록에서 아예
    빠지기 때문이다. 그 경우까지 합의도가 만점이 되면 "셋 중 하나만 답했는데
    확신 100%"가 되어 화면이 사용자를 오도한다.

    동점이면 pick 문자열 오름차순으로 고른다 — 같은 입력에 같은 결과가 나와야
    재생성했을 때 예측이 흔들리지 않는다.
    """
    if agent_count < 1:
        raise ValueError(f"agent_count는 1 이상이어야 합니다: {agent_count}")

    opinionated = [report for report in reports if report.has_opinion]
    if not opinionated:
        raise ReportsUnavailableError("의견을 낸 에이전트가 없습니다.")

    shares = _weighted_shares(opinionated)
    pick = min(shares, key=lambda candidate: (-shares[candidate], candidate))

    agreement = sum(1 for r in opinionated if r.pick == pick) / len(opinionated)
    # 물어본 에이전트 중 몇이 답했는가. 목록이 요청 수보다 길면(중복 리포트 등)
    # 1.0을 넘지 않게 자른다.
    coverage = min(1.0, len(opinionated) / agent_count)

    return PredictionSynthesis(
        pick=pick,
        win_probability=shares[pick],
        confidence=agreement * coverage,
    )


def _weighted_shares(opinionated: list[AgentReport]) -> dict[str, float]:
    """pick별 가중 득표 비중. 합은 1.0이다."""
    totals: dict[str, float] = {}
    for report in opinionated:
        assert report.pick is not None  # has_opinion으로 걸렀다
        totals[report.pick] = totals.get(report.pick, 0.0) + report.weight

    total_weight = sum(totals.values())
    if total_weight <= 0.0:
        # 전원이 weight 0으로 답한 경우. 나눗셈이 불가능하므로 동일 가중으로 본다 —
        # 여기서 예외를 던지면 "의견은 냈는데 확신이 없다"는 정상 상태가 실패가 된다.
        return {pick: 1.0 / len(totals) for pick in totals}

    return {pick: weight / total_weight for pick, weight in totals.items()}
