"""에이전트 리포트 → 최종 pick·승률 합성. 순수 함수다.

`_docs/ai-match-predictions-harness.md` §5. LLM·DB·HTTP를 모르므로 고정 리포트
픽스처만으로 테스트가 돌아간다(하네스 §3-D3).

**에이전트별 기본 가중치를 여기에 박지 않는다.** 서사·오즈·루머 중 무엇을 더 믿을지는
아직 정해지지 않았고(하네스 §13-Q2), 근거 없는 숫자를 코드에 남기지 않기 위해서다.
이 함수는 리포트가 실어 온 `weight`를 분포로 펴서 평균할 뿐이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

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
    #: 선택지별 승률. 합은 1.0이다. 상대가 나눠 가진 몫이 여기 남는다.
    probabilities: dict[str, float] = field(default_factory=dict)


def synthesize(
    reports: Sequence[AgentReport], *, agent_count: int, options: Sequence[str]
) -> PredictionSynthesis:
    """리포트를 합쳐 **선택지 전체의 승률 분포**를 만든다.

    각 에이전트의 의견은 그 자체로 분포다 — "Roman에 0.7 확신"은 곧 `Roman 0.7 ·
    나머지 0.3`이다. 그 분포들을 평균해 최종 승률을 낸다. 득표 비중만 쓰던 이전
    방식은 **의견을 낸 에이전트가 전원 같은 쪽이면 무조건 100%** 가 되어, 오즈가
    배당에서 계산해 온 내재 확률이 정규화 과정에서 통째로 사라졌다.

    `agent_count`는 **코디네이터가 물어본 에이전트 수**다. 리포트 목록의 길이가
    아니라 이 값을 받는 이유는, 실패해서 리포트를 못 낸 에이전트가 목록에서 아예
    빠지기 때문이다. 그 경우까지 합의도가 만점이 되면 "셋 중 하나만 답했는데
    확신 100%"가 되어 화면이 사용자를 오도한다.

    동점이면 pick 문자열 오름차순으로 고른다 — 같은 입력에 같은 결과가 나와야
    재생성했을 때 예측이 흔들리지 않는다.
    """
    if agent_count < 1:
        raise ValueError(f"agent_count는 1 이상이어야 합니다: {agent_count}")
    if not options:
        raise ValueError("options는 비어 있을 수 없습니다.")

    opinionated = [report for report in reports if report.has_opinion]
    if not opinionated:
        raise ReportsUnavailableError("의견을 낸 에이전트가 없습니다.")

    probabilities = _averaged_distribution(opinionated, options)
    pick = min(probabilities, key=lambda c: (-probabilities[c], c))

    agreement = sum(1 for r in opinionated if r.pick == pick) / len(opinionated)
    # 물어본 에이전트 중 몇이 답했는가. 목록이 요청 수보다 길면(중복 리포트 등)
    # 1.0을 넘지 않게 자른다.
    coverage = min(1.0, len(opinionated) / agent_count)

    return PredictionSynthesis(
        pick=pick,
        win_probability=probabilities[pick],
        confidence=agreement * coverage,
        probabilities=probabilities,
    )


def _averaged_distribution(
    opinionated: list[AgentReport], options: Sequence[str]
) -> dict[str, float]:
    """에이전트별 분포의 산술 평균. 합은 1.0이다.

    카드에 없는 pick은 여기 오지 않는다 — 코디네이터가 의견 없음으로 낮춰서 보낸다.
    그래도 남아 있으면 그 리포트는 분포에 기여하지 못하므로 무시한다.
    """
    codes = list(dict.fromkeys(options))
    totals = dict.fromkeys(codes, 0.0)

    counted = 0
    for report in opinionated:
        if report.pick not in totals:
            continue
        counted += 1
        for code, value in _one_report_distribution(report, codes).items():
            totals[code] += value

    if counted == 0:
        # 의견은 있는데 전부 카드 밖이다. 어느 쪽도 밀 근거가 없으므로 균등하게 본다.
        return dict.fromkeys(codes, 1.0 / len(codes))
    return {code: value / counted for code, value in totals.items()}


def _one_report_distribution(report: AgentReport, codes: list[str]) -> dict[str, float]:
    """리포트 하나를 분포로 편다: pick에 `weight`, 나머지가 남은 몫을 나눠 갖는다.

    **`weight`는 균등(1/n) 아래로 내려가지 않는다.** 확신이 낮다는 것은 "잘 모르겠다"
    이지 "내가 고른 쪽이 질 것 같다"가 아니다. 바닥을 두지 않으면 확신 0.2짜리 의견이
    2파전에서 자기 pick의 승률을 20%로 끌어내려, 고른 쪽에 반대표를 던지는 꼴이 된다.
    """
    if len(codes) == 1:
        return {codes[0]: 1.0}

    uniform = 1.0 / len(codes)
    weight = max(report.weight, uniform)
    rest = (1.0 - weight) / (len(codes) - 1)
    return {code: (weight if code == report.pick else rest) for code in codes}
