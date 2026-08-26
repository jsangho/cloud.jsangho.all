"""AI LAB 합성 해부 — Phase 3-5. **순수 함수다** (DB·LLM을 모른다).

**이 모듈은 정확도를 재지 않는다.** 최종 승률 숫자 하나가 세 에이전트의 의견에서
어떻게 접혔는지를 편다. 정확도는 이미 두 곳이 답했다 — 전체는 3-1, 에이전트별은
3-3이다. 여기서 또 세면 같은 숫자가 세 번 나온다.

편는 축은 셋이다.

1. **합의 분해** — 저장된 `confidence`는 `agreement × coverage`인데, 그 둘을 곱해
   놓으면 "3명이 답하고 2명이 동의"와 "2명이 답하고 둘 다 동의"가 같은 0.667로
   보인다. 두 인수를 갈라 놓으면 갈린다.
2. **기여 변동성** — 에이전트가 낸 `weight`가 실제로 변하는가. 한 값만 내는
   에이전트는 그 축에서 아무 정보도 주지 않는다. **판단이 아니라 실측이다** —
   서로 다른 값이 몇 개인지 세면 나온다.
3. **예측별 구성** — 최종 승률과 그것을 만든 리포트를 나란히 둔다. 승률이 높은 것과
   근거가 두꺼운 것이 같지 않을 수 있고, 그 어긋남은 이 둘을 붙여 놔야 보인다.

집계 규칙은 3-0·3-3과 **같다**: 북메이커 폴백은 통째로 빠지고, 미채점은 오답이
아니며, 의견 없음은 분모에 안 들어간다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kayfabe.app.services.ai_lab_integrity import (
    BOOKMAKER_FALLBACK,
    PredictionRow,
    ReportRow,
)
from kayfabe.domain.entities.agent_prediction import AgentKind

#: 합의도의 분모 — 코디네이터가 물어보는 에이전트 수.
#:
#: **도메인 열거형에서 센다.** `ai_prediction_interactor.AGENT_COUNT`가 같은 값을
#: 들고 있지만 그 모듈을 여기서 import하면 읽기 전용 화면이 예측 생성 경로를 통째로
#: 끌고 온다. 대신 둘이 어긋나면 테스트가 잡는다
#: (`test_ai_lab_performance.py::test_the_coverage_denominator_matches_the_generator`).
AGENT_COUNT = len(AgentKind)

#: 2파전(singles) 카드의 `pick` 값.
#:
#: 형식을 알려면 `ple_matches.card_json`을 읽어야 할 것 같지만 그럴 필요가 없다 —
#: `agent_prediction_pg_repository._options_from_card`가 singles에는 `left`/`right`를,
#: 다파전에는 선택지 색인(`"0"`, `"1"` …)을 준다. 저장된 `pick` 자체가 형식을 담고
#: 있으므로 **새 쿼리 없이** 갈린다. 이건 추정이 아니라 그 인코딩의 해독이다.
_SINGLES_PICKS = frozenset({"left", "right"})


@dataclass(frozen=True)
class ReportContribution:
    """예측 하나에 실린 에이전트 한 명의 몫."""

    agent: str
    weight: float
    #: `pick`이 있었는가. **의견 없음은 오답이 아니다** — 동의도 분모에도 안 들어간다.
    opinionated: bool


@dataclass(frozen=True)
class PerformanceItem:
    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    win_probability: float
    #: 저장된 값 그대로. 아래 `agreement × coverage`가 이 값을 재현한다.
    confidence: float
    #: 최종 pick에 동의한 의견 / 전체 의견. **의견이 하나도 없으면 `None`** (0.0 아니다).
    agreement: float | None
    #: 의견 낸 에이전트 / 물어본 에이전트. 리포트가 없으면 0.0이다.
    coverage: float
    #: 미채점이면 `None` — 실패(False)와 다른 상태다.
    correct: bool | None
    reports: tuple[ReportContribution, ...]


@dataclass(frozen=True)
class ConsensusLevel:
    """`(answered, agreed)` 한 짝.

    **`confidence`로 묶지 않는다.** 곱이 같으면 서로 다른 상황이 한 줄로 접히기
    때문이다 — 실제로 `0.667`에는 "2명이 답해 둘 다 동의"와 "3명이 답해 2명 동의"가
    함께 들어 있다. 그 둘은 근거의 두께가 다르다.
    """

    #: `agreement × coverage`. 저장된 값을 재현한다 (약분하면 `agreed / AGENT_COUNT`다).
    confidence: float
    answered: int
    agreed: int
    predictions: int
    #: 결과가 나온 예측 수 — **정답률의 분모다.**
    graded: int
    correct: int


@dataclass(frozen=True)
class AgentContribution:
    """에이전트 한 명의 `weight`가 실제로 변하는가.

    3-3의 `AgentAnalysis`와 **다른 것을 잰다.** 3-3은 그 의견이 맞았는지를 보고,
    여기서는 그 에이전트가 최종 숫자에 정보를 넣었는지를 본다. 한 값만 내는
    에이전트는 100% 맞혀도 승률의 변동에는 기여하지 않는다.
    """

    agent: str
    reports: int
    #: `pick`이 있는 리포트 수 — 아래 값들의 분모다.
    opinions: int
    #: 서로 다른 `weight` 값의 수. 의견이 없으면 0이다.
    distinct_weights: int
    min_weight: float | None
    max_weight: float | None
    #: 값이 하나뿐인가. **의견이 없으면 `None`** — 상수라고 말할 근거가 없다.
    constant: bool | None


@dataclass(frozen=True)
class PerformanceTotals:
    #: 저장된 예측 전체 (폴백 포함) — 재고 수치다.
    predictions: int
    graded: int
    correct: int
    incorrect: int
    bookmaker_fallback: int
    #: 아래 둘은 **폴백을 뺀** 예측을 센다. 이 화면이 해부하는 대상이 그것뿐이다.
    singles: int
    multi: int


def summarize_performance(
    predictions: Sequence[PredictionRow], reports: Sequence[ReportRow]
) -> tuple[
    PerformanceTotals,
    list[ConsensusLevel],
    list[AgentContribution],
    list[PerformanceItem],
]:
    """**새 SQL 없이** 이미 읽어 온 두 목록을 잇는다. 조인 키는 3-3과 같은
    `(event_slug, match_key)`다.

    규칙 셋을 3-0·3-3에서 그대로 가져온다.

    1. **북메이커 폴백은 통째로 뺀다** — 에이전트가 답하지 못해 배당으로 대체한
       예측이라 합성이라 부를 것이 없다.
    2. **미채점은 정확도 분모에서 뺀다.** 결과가 없는 것을 오답으로 세지 않는다.
    3. **의견 없음은 오답이 아니다.** 동의도 분모에도 들어가지 않는다.
    """
    scoped = [row for row in predictions if row.source != BOOKMAKER_FALLBACK]
    keys = {(row.event_slug, row.match_key) for row in scoped}
    scoped_reports = [r for r in reports if (r.event_slug, r.match_key) in keys]

    by_match: dict[tuple[str, str], list[ReportRow]] = {}
    for report in scoped_reports:
        by_match.setdefault((report.event_slug, report.match_key), []).append(report)

    items = [
        _item(row, by_match.get((row.event_slug, row.match_key), [])) for row in scoped
    ]
    # 승률이 높은 것이 위로. 같으면 경기 키 순 — 재조회에도 순서가 안 흔들린다.
    items.sort(key=lambda i: (-i.win_probability, i.match_key))

    graded = [row for row in scoped if row.winner_pick is not None]
    correct = sum(1 for row in graded if row.pick == row.winner_pick)
    totals = PerformanceTotals(
        predictions=len(predictions),
        graded=len(graded),
        correct=correct,
        incorrect=len(graded) - correct,
        bookmaker_fallback=len(predictions) - len(scoped),
        singles=sum(1 for row in scoped if row.pick in _SINGLES_PICKS),
        multi=sum(1 for row in scoped if row.pick not in _SINGLES_PICKS),
    )
    return totals, _consensus(scoped, by_match), _contributions(scoped_reports), items


def _item(row: PredictionRow, reports: Sequence[ReportRow]) -> PerformanceItem:
    opinionated = [r for r in reports if r.pick is not None]
    agreed = sum(1 for r in opinionated if r.pick == row.pick)

    return PerformanceItem(
        event_slug=row.event_slug,
        event_label=row.event_label,
        match_key=row.match_key,
        match_title=row.match_title,
        win_probability=row.win_probability,
        confidence=row.confidence,
        # 의견이 없으면 나눌 것이 없다 — 0.0으로 채우면 "아무도 동의 안 했다"가 된다.
        agreement=(agreed / len(opinionated)) if opinionated else None,
        coverage=coverage_of(len(opinionated)),
        correct=_correct(row),
        reports=tuple(
            ReportContribution(
                agent=r.agent, weight=r.weight, opinionated=r.pick is not None
            )
            for r in reports
        ),
    )


def coverage_of(opinionated: int) -> float:
    """의견 낸 에이전트 / 물어본 에이전트.

    `prediction_synthesis.synthesize()`와 **같은 식이다** — 상한 1.0도 그대로 둔다
    (중복 리포트로 분자가 커져도 100%를 넘지 않는다).
    """
    return min(1.0, opinionated / AGENT_COUNT)


def _correct(row: PredictionRow) -> bool | None:
    """채점 결과. **미채점은 `None`이다** — 실패(False)와 뭉치지 않는다."""
    if row.winner_pick is None:
        return None
    return row.pick == row.winner_pick


def _consensus(
    rows: Sequence[PredictionRow],
    by_match: dict[tuple[str, str], list[ReportRow]],
) -> list[ConsensusLevel]:
    """`(answered, agreed)` 짝으로 묶는다 — `confidence` 값으로 묶지 않는다.

    두 수를 리포트에서 **정수 그대로** 센다. 비율에서 역산하면 부동소수를 정수로
    되돌리는 왕복이 생기고, 그 왕복은 언젠가 한 칸 어긋난다.
    """
    grouped: dict[tuple[int, int], list[PredictionRow]] = {}
    for row in rows:
        reports = by_match.get((row.event_slug, row.match_key), [])
        opinionated = [r for r in reports if r.pick is not None]
        agreed = sum(1 for r in opinionated if r.pick == row.pick)
        grouped.setdefault((len(opinionated), agreed), []).append(row)

    levels = [
        ConsensusLevel(
            confidence=_confidence_of(answered, agreed),
            answered=answered,
            agreed=agreed,
            predictions=len(group),
            graded=sum(1 for row in group if row.winner_pick is not None),
            correct=sum(
                1
                for row in group
                if row.winner_pick is not None and row.pick == row.winner_pick
            ),
        )
        for (answered, agreed), group in grouped.items()
    ]
    levels.sort(key=lambda level: (level.confidence, level.answered))
    return levels


def _confidence_of(answered: int, agreed: int) -> float:
    """`agreement × coverage`를 그대로 계산한다 — 저장된 `confidence`를 재현한다.

    약분하면 `agreed / AGENT_COUNT`지만 그렇게 적지 않는다. 합성 규칙이 바뀌면
    여기도 같이 바뀌어야 한다는 것을 식의 모양으로 남겨 두기 위해서다.
    """
    if answered == 0:
        return 0.0
    return (agreed / answered) * coverage_of(answered)


def _contributions(reports: Sequence[ReportRow]) -> list[AgentContribution]:
    """에이전트별 `weight`의 변동성. **이름은 코드의 이름 그대로다.**"""
    grouped: dict[str, list[ReportRow]] = {}
    for report in reports:
        grouped.setdefault(report.agent, []).append(report)

    contributions = []
    for agent, rows in sorted(grouped.items()):
        weights = [r.weight for r in rows if r.pick is not None]
        distinct = len(set(weights))
        contributions.append(
            AgentContribution(
                agent=agent,
                reports=len(rows),
                opinions=len(weights),
                distinct_weights=distinct,
                min_weight=min(weights) if weights else None,
                max_weight=max(weights) if weights else None,
                # 의견이 없으면 상수인지 아닌지 말할 근거가 없다 — False가 아니라 None이다.
                constant=(distinct == 1) if weights else None,
            )
        )
    return contributions
