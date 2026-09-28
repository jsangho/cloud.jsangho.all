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

#: 기권을 분포에서 빼고 의견 낸 리포트만 평균했던 산식. **옛 예측을 재현하려면
#: 남겨야 한다** — 저장된 승률은 이 함수가 만든 값이고, 지워 버리면 그때의 숫자를
#: 다시 만들 수 없어 재현 화면이 근거 없이 `diverged`를 말한다.
SYNTHESIS_V1 = "1"

#: 기권을 **균등분포**로 세어 `agent_count`로 나누는 산식 (2026-09-28).
SYNTHESIS_V2 = "2"

#: 지금 쓰는 판본. 새 예측은 이 값으로 기록된다.
SYNTHESIS_VERSION = SYNTHESIS_V2


def resolved_synthesis_version(recorded: str | None) -> str:
    """저장된 판본을 **실제로 그 숫자를 만든 산식**의 이름으로 읽는다.

    비어 있으면 `v1`이다 — 칼럼이 `v2`와 함께 생겼으므로 기록이 없는 행은 전부
    `v1`이 만든 것이다.

    **이 규칙을 두 군데서 적지 않기 위해 함수로 둔다.** 재현이 산식을 고를 때와
    화면이 판본을 적을 때가 같은 답을 내야 한다 — 한쪽만 바뀌면 화면은 `v2`라고
    적는데 재현은 `v1`으로 돌리는 상태가 되고, 그 어긋남은 아무 데서도 안 보인다.
    """
    return recorded or SYNTHESIS_V1


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
    reports: Sequence[AgentReport],
    *,
    agent_count: int,
    options: Sequence[str],
    version: str = SYNTHESIS_VERSION,
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

    ## `version` — 기권을 분포에 세는가 (2026-09-28)

    **`v1`은 기권을 분포에서 뺐다.** 그래서 셋 중 하나만 답하고 그 하나가 확신
    1.0이면 **6인 경기에도 승률 100%** 가 나왔다. 약함을 말하는 칸은 `confidence`
    하나뿐이라, 승률만 보는 화면·집계는 그것을 확정으로 읽는다.

    **`v2`는 기권을 "모르겠다" = 균등분포로 세고 `agent_count`로 나눈다.** 전원이
    답하면 v1과 **같은 값**이고, 답한 수가 줄수록 균등 쪽으로 끌려간다.
    실측(운영 20건): 값이 바뀌는 예측 16건 · 그대로 4건(3/3이 답한 것) ·
    **`pick`은 한 건도 바뀌지 않는다** — 채점과 적중률은 영향이 없다.

    `v1`을 지우지 않는 이유는 **저장된 예측을 재현하려면 그때의 함수가 필요하기**
    때문이다. 판본은 `ple_agent_predictions.synthesis_version`에 남고, 재현은 그
    값으로 이 함수를 부른다. 그 칼럼이 비어 있으면 `v1`이다 — 칼럼이 `v2`와 함께
    생겼으므로 기록이 없는 행은 전부 `v1`이 만든 것이다.

    **`confidence`는 두 판본이 같다.** 그쪽은 이미 `coverage`로 기권을 세고 있어
    고칠 것이 없었다.
    """
    if agent_count < 1:
        raise ValueError(f"agent_count는 1 이상이어야 합니다: {agent_count}")
    if not options:
        raise ValueError("options는 비어 있을 수 없습니다.")
    if version not in (SYNTHESIS_V1, SYNTHESIS_V2):
        # 모르는 판본을 아무 산식으로 처리하면 재현이 거짓말을 한다.
        raise ValueError(f"알 수 없는 합성 판본입니다: {version!r}")

    opinionated = [report for report in reports if report.has_opinion]
    if not opinionated:
        raise ReportsUnavailableError("의견을 낸 에이전트가 없습니다.")

    probabilities = _averaged_distribution(
        opinionated,
        options,
        agent_count=agent_count,
        count_abstentions=version == SYNTHESIS_V2,
    )
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
    opinionated: list[AgentReport],
    options: Sequence[str],
    *,
    agent_count: int,
    count_abstentions: bool,
) -> dict[str, float]:
    """에이전트별 분포의 산술 평균. 합은 1.0이다.

    카드에 없는 pick은 여기 오지 않는다 — 코디네이터가 의견 없음으로 낮춰서 보낸다.
    그래도 남아 있으면 그 리포트는 분포에 기여하지 못하므로 무시한다.

    `count_abstentions`가 참이면(`v2`) **답하지 않은 자리를 균등분포로 세어** 평균에
    넣는다. "모르겠다"는 어느 쪽도 밀지 않는다는 뜻이고, 그것을 평균에서 빼면 답한
    하나의 의견이 전체 의견인 척하게 된다. 카드 밖 pick도 같은 자리에 둔다 — 분포에
    기여할 수 없으니 답하지 않은 것과 다르지 않다.

    **거짓이면(`v1`) 분모를 건드리지 않는다.** 이 함수가 옛 예측의 저장값을 다시
    만들어야 하므로, `v1` 경로는 한 연산도 달라지면 안 된다.
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

    if not count_abstentions:
        return {code: value / counted for code, value in totals.items()}

    # 리포트가 요청 수보다 많으면(중복 등) 기권은 없다. 음수로 내려가지 않게 자른다.
    abstained = max(0, agent_count - counted)
    uniform = 1.0 / len(codes)
    divisor = counted + abstained
    return {
        code: (value + uniform * abstained) / divisor for code, value in totals.items()
    }


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
