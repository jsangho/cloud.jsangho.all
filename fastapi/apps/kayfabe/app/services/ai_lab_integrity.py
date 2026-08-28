"""AI LAB 평가 신뢰성 계산 — Phase 3-0. **순수 함수다** (DB·LLM을 모른다).

이 모듈이 하는 일은 적중률을 자랑하는 것이 아니라 **그 숫자를 믿어도 되는지 재는 것**이다.
현재 운영값은 12전 12승 100%인데, 그 숫자를 일반화 지표로 내보내면 거짓말이 된다.
여기서 계산하는 것은 셋이다.

1. **표본이 얼마나 작은가** — 적중률에 윌슨 95% 신뢰구간을 붙인다. 12/12는 점추정
   100%지만 구간은 [75.8%, 100%]다. 임의의 "최소 표본 30건" 같은 문턱보다 이쪽이
   정직하다 — 문턱은 우리가 고른 숫자지만 구간은 표본이 스스로 말하는 값이다.
2. **예측이 제 대회 문서를 인용했는가** — 에이전트가 인용한 출처 URL 중 그 대회
   자체를 다룬 문서가 있으면 센다. 위키의 대회 문서에는 경기 결과가 적혀 있으므로,
   그것을 읽고 낸 예측은 예측이 아니라 **열람**이다.
3. **시간 검증이 가능한가** — 청크에 발행일이 있어야 "예측보다 먼저 쓰인 글"인지
   가릴 수 있다. 발행일이 하나도 없으면 누수가 없다는 것을 **증명할 수 없다**.
   없음을 과거로 간주하지 않는다(사용자 결정 §7).

`generalizable`은 위 셋에서 파생된 결론이고, 왜 그렇게 판정했는지 `reasons`로 함께
내보낸다 — 화면이 근거 없이 "신뢰할 수 없음"만 적지 않게 하기 위해서다.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

#: 윌슨 구간의 z (95%). 바꾸면 화면 문구의 "95%"도 함께 바꾼다.
Z_95 = 1.959963984540054

#: 일반화 판정에 쓰는 최소 대회 수. 한 대회만으로는 그 대회의 특성과
#: 모델의 실력을 가를 수 없다.
MIN_EVENTS_FOR_GENERALIZATION = 2

#: 북메이커 폴백 예측의 `source` 값. 적중률 집계에서 빠진다
#: (`ple_events_pg_repository.get_ai_stats`와 같은 규칙).
BOOKMAKER_FALLBACK = "bookmaker_fallback"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def is_scorable(row: PredictionRow) -> bool:
    """**이 예측으로 점수를 매겨도 되는가.**

    집계 함수 넷이 공유하는 단 하나의 정의다. 네 곳에 같은 조건을 따로 적으면
    언젠가 한 곳만 바뀌고, 그때 화면들이 서로 다른 분모로 같은 이름의 비율을
    말하게 된다.

    거르는 것은 둘이다.

    1. **북메이커 폴백** — 에이전트가 아무도 답하지 못해 배당으로 대체한 예측이라
       에이전트의 판단이 아니다.
    2. **사후 재현 표본**(Phase 3-7) — 생성 시점에 결과가 시스템 밖에서 이미
       알려져 있었다고 **선언된** 예측이다.

    **`is not True`여야 한다.** `not row.outcome_known_externally`로 쓰면 `None`이
    함께 걸려, 아무도 선언한 적 없는 정상 표본까지 채점에서 빠진다. `None`은
    "모른다"가 아니라 "선언되지 않았다"이고, 그 표본은 채점 대상으로 남는다
    (`ai_lab_evaluation._judge()`의 `is True`와 정확히 대칭이다).

    **이 함수는 "무엇으로 점수를 매기는가"만 정한다.** "무엇을 했는가"(리포트 수·
    응답률·재고 수치)는 여기를 지나지 않는다 — 사후 재현 표본에도 에이전트는
    실제로 일을 했고, 그 사실까지 지우면 활동량이 거짓이 된다.
    """
    return row.source != BOOKMAKER_FALLBACK and row.outcome_known_externally is not True


@dataclass(frozen=True)
class PredictionRow:
    """저장된 예측 한 건 + 그 경기의 실제 결과."""

    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    pick: str
    pick_name: str
    win_probability: float
    confidence: float
    #: 합성이 엮어 낸 근거 문장. 리포트 요약을 규칙으로 이은 값이라 LLM을 다시 부르지 않는다.
    rationale: str
    source: str
    generated_at: datetime
    #: 아직 안 끝난 경기면 `None`이다 — 채점 대상이 아니다.
    winner_pick: str | None
    winner_name: str | None
    #: 결과가 **시스템에 기록된** 시각 (Phase 3-6). 경기가 끝난 시각이 아니다 —
    #: 운영 데이터에서는 결과 56건이 3분 안에 몰려 있어 일괄 적재의 흔적이 남아 있다.
    #: 평가 자격 판정에는 오히려 이쪽이 맞는 기준이다: 예측을 만들 때 정답이 이미
    #: 시스템 안에 있었는가.
    #:
    #: **기본값이 `None`인 이유**는 이 필드를 모르는 기존 호출자(3-0·3-3·3-5의 집계와
    #: 그 테스트)를 그대로 두기 위해서다. 모르면 시간 판정을 보류할 뿐 통과시키지 않는다.
    finished_at: datetime | None = None
    #: 생성 시점에 결과가 **시스템 밖에서** 이미 알려져 있었는가 (Phase 3-7).
    #:
    #: `finished_at`이 답할 수 없는 것을 답한다. 그 컬럼은 결과가 DB에 들어온 시각이라
    #: "사람이 이미 알고 있었다"·"모델이 학습으로 알고 있었다"를 담지 못한다.
    #:
    #: **`None`은 모른다가 아니라 아무도 선언하지 않았다는 뜻이다.** 그래서 옛 예측은
    #: 기존 판정 경로를 그대로 지난다 — 여기서 `None`을 보류로 접으면 이미 확정된
    #: 판정이 통째로 흔들린다. "모른다"를 말하려면 `False`로 명시한다.
    outcome_known_externally: bool | None = None
    #: 위 선언의 근거 문장. 서버가 그대로 화면에 내보내므로 **사실만 담는다.**
    provenance_note: str | None = None
    #: 그 대회가 열린 날 (Phase 3-12). 인용 문서의 개정본이 이 날보다 앞서야
    #: "결과가 적혀 있을 수 없다"고 말할 수 있다.
    #:
    #: **`None`은 통과가 아니다.** 날짜를 모르면 비교 자체가 불가능하므로 보류로 간다.
    #: 기본값을 둔 이유는 이 필드를 모르는 기존 호출자를 그대로 두기 위해서다.
    event_start_date: date | None = None


@dataclass(frozen=True)
class ReportRow:
    """에이전트 한 명의 의견. `pick`이 `None`이면 **의견 없음**이다."""

    event_slug: str
    match_key: str
    agent: str
    pick: str | None
    weight: float
    #: 에이전트가 쓴 판단 요약. 의견이 없어도 이유가 적혀 있어 근거로 쓸 만하다.
    summary: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class CorpusFacts:
    """RAG 코퍼스 실측. 세는 일은 DB가 하고 해석만 여기서 한다."""

    chunks_total: int
    chunks_embedded: int
    chunks_with_published_at: int
    documents: int
    domains: int
    last_collected_at: datetime | None


@dataclass(frozen=True)
class PredictionTotals:
    total: int
    graded: int
    correct: int
    incorrect: int
    #: 채점된 예측이 없으면 `None`이다 — 0%가 아니다.
    hit_rate: float | None
    hit_rate_low: float | None
    hit_rate_high: float | None
    avg_confidence: float | None
    avg_win_probability: float | None
    bookmaker_fallback: int


@dataclass(frozen=True)
class IntegrityFacts:
    sample_size: int
    events_covered: int
    events_total: int
    self_referencing_predictions: int
    predictions_with_sources: int
    chunks_total: int
    chunks_with_published_at: int
    temporal_verifiable: bool
    generalizable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AgentActivity:
    agent: str
    reports: int
    with_pick: int
    #: 리포트를 낸 것 중 실제로 pick을 고른 비율. 리포트가 0이면 `None`.
    opinion_rate: float | None
    avg_weight: float | None


@dataclass(frozen=True)
class AgentAnalysis:
    """에이전트 한 명의 성적 (Phase 3-3).

    `AgentActivity`(개요용)와 **별도 타입이다.** 개요는 활동량만 보여 주고 정확도를
    말하지 않으므로, 거기에 필드를 끼워 넣으면 개요 계약이 커지고 쓰지 않는 값을 매번
    계산하게 된다.

    분모가 셋 다 다르다 — 그래서 비율만 들고 다니지 않고 **분자·분모를 함께** 낸다.
    화면이 "90%"만 세우면 그 뒤의 9/10이 사라진다.
    """

    agent: str
    #: 이 에이전트가 낸 리포트 수. 분모는 `total_predictions`(응답률).
    reports: int
    with_pick: int
    no_opinion: int
    #: 리포트 수 / 전체 예측 수. 예측이 0건이면 `None`.
    response_rate: float | None
    #: pick을 고른 리포트 / 이 에이전트의 리포트. 리포트가 0건이면 `None`.
    opinion_rate: float | None
    #: 의견을 냈고 결과도 나온 리포트 — **정확도의 분모다.**
    gradable: int
    correct: int
    incorrect: int
    #: 채점 대상이 없으면 `None`이다 — 0.0이 아니다.
    accuracy: float | None
    accuracy_low: float | None
    accuracy_high: float | None
    #: 전체 리포트 평균. 의견 없음(0.0)이 끌어내린 값이다.
    avg_weight: float | None
    #: 의견을 낸 리포트만의 평균. 위와 함께 봐야 뜻이 통한다.
    avg_weight_opinionated: float | None
    matches_covered: int
    events_covered: int
    #: 그 대회 자체를 다룬 문서를 인용한 리포트 수.
    self_referencing_reports: int
    #: 출처를 한 번이라도 낸 적이 있는가. **실측이다** — 코드를 읽어 정하지 않는다.
    uses_knowledge: bool


@dataclass(frozen=True)
class AgentAnalysisTotals:
    agent_count: int
    total_reports: int
    opinionated: int
    no_opinion: int
    overall_opinion_rate: float | None
    gradable_reports: int
    #: 응답률의 분모 — 폴백을 뺀 예측 수.
    total_predictions: int


def summarize_agent_analysis(
    predictions: Sequence[PredictionRow], reports: Sequence[ReportRow]
) -> tuple[AgentAnalysisTotals, list[AgentAnalysis]]:
    """에이전트별 성적. **새 SQL 없이** 이미 읽어 온 두 목록을 메모리에서 잇는다.

    조인 키는 `(event_slug, match_key)`다.

    규칙 셋을 지킨다.

    1. **북메이커 폴백 예측은 통째로 뺀다** — 에이전트가 답하지 못해 배당으로
       대체한 예측이라, 그 경기의 리포트로 에이전트를 평가할 수 없다.
    2. **미채점(`winner_pick is None`)은 정확도 분모에서 뺀다.** 아직 결과가 없는 것을
       오답으로 세면 안 된다.
    3. **의견 없음(`pick is None`)은 오답이 아니다.** 근거가 없어 판단하지 않은 것은
       설계된 동작이고(하네스 §13-Q1), 정확도 분모에도 들어가지 않는다.

    **활동량과 정확도의 분모가 다르다.** 리포트 수·응답률·의견율은 아래
    `activity_source` 전체를 보고, 정확도만 `is_scorable`을 한 번 더 지난다.
    사후 재현 표본에서도 에이전트는 실제로 답했으므로 그 일한 기록까지 지우면
    화면이 "이 에이전트는 그만큼 일하지 않았다"고 거짓말을 하게 된다.
    """
    # 활동량 모집단이다 — **채점 모집단이 아니다.** 정확도용 필터는 `_analyze_agent`가
    # 예측 단위로 한 번 더 건다.
    activity_source = {
        (p.event_slug, p.match_key): p
        for p in predictions
        if p.source != BOOKMAKER_FALLBACK
    }
    scoped = [r for r in reports if (r.event_slug, r.match_key) in activity_source]

    by_agent: dict[str, list[ReportRow]] = {}
    for report in scoped:
        by_agent.setdefault(report.agent, []).append(report)

    total_predictions = len(activity_source)
    agents = [
        _analyze_agent(agent, rows, activity_source, total_predictions)
        for agent, rows in sorted(by_agent.items())
    ]

    opinionated = sum(a.with_pick for a in agents)
    total_reports = sum(a.reports for a in agents)
    totals = AgentAnalysisTotals(
        agent_count=len(agents),
        total_reports=total_reports,
        opinionated=opinionated,
        no_opinion=total_reports - opinionated,
        overall_opinion_rate=(opinionated / total_reports) if total_reports else None,
        gradable_reports=sum(a.gradable for a in agents),
        total_predictions=total_predictions,
    )
    return totals, agents


def _analyze_agent(
    agent: str,
    rows: Sequence[ReportRow],
    predictions: dict[tuple[str, str], PredictionRow],
    total_predictions: int,
) -> AgentAnalysis:
    opinionated = [r for r in rows if r.pick is not None]
    # **정확도 분모만 `is_scorable`을 지난다.** 위 `opinionated`(활동량)는 그대로 둔다 —
    # 사후 재현 표본에 답한 것도 답한 것이다.
    gradable = [
        r
        for r in opinionated
        if is_scorable(predictions[(r.event_slug, r.match_key)])
        and predictions[(r.event_slug, r.match_key)].winner_pick is not None
    ]
    correct = sum(
        1
        for r in gradable
        if r.pick == predictions[(r.event_slug, r.match_key)].winner_pick
    )
    interval = wilson_interval(correct, len(gradable))

    self_referencing = sum(
        1
        for r in rows
        if r.sources
        and cites_own_event(
            r.sources, predictions[(r.event_slug, r.match_key)].event_label
        )
    )

    return AgentAnalysis(
        agent=agent,
        reports=len(rows),
        with_pick=len(opinionated),
        no_opinion=len(rows) - len(opinionated),
        response_rate=(len(rows) / total_predictions) if total_predictions else None,
        opinion_rate=(len(opinionated) / len(rows)) if rows else None,
        gradable=len(gradable),
        correct=correct,
        incorrect=len(gradable) - correct,
        accuracy=(correct / len(gradable)) if gradable else None,
        accuracy_low=interval[0] if interval else None,
        accuracy_high=interval[1] if interval else None,
        avg_weight=_mean(r.weight for r in rows),
        avg_weight_opinionated=_mean(r.weight for r in opinionated),
        matches_covered=len({(r.event_slug, r.match_key) for r in rows}),
        events_covered=len({r.event_slug for r in rows}),
        self_referencing_reports=self_referencing,
        # 출처를 한 번도 낸 적이 없으면 이 에이전트는 코퍼스를 읽지 않는다는 뜻이다.
        # `BookmakerOddsScout`가 그렇다 — 판단 근거가 카드의 배당 숫자뿐이다.
        uses_knowledge=any(r.sources for r in rows),
    )


def wilson_interval(correct: int, total: int) -> tuple[float, float] | None:
    """비율의 윌슨 95% 신뢰구간. 표본이 없으면 `None`.

    정규 근사(Wald)를 쓰지 않는 이유는 **12/12에서 구간이 [100%, 100%]로 붕괴하기
    때문**이다. 표본이 작고 비율이 끝에 붙은 지금 상황이 정확히 Wald가 망가지는
    자리라, 이 화면에서는 윌슨이 아니면 의미가 없다.
    """
    if total <= 0:
        return None
    p = correct / total
    z2 = Z_95 * Z_95
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    half = (Z_95 / denominator) * math.sqrt(
        p * (1 - p) / total + z2 / (4 * total * total)
    )
    return max(0.0, center - half), min(1.0, center + half)


def _normalize(text: str) -> str:
    """비교용 정규화 — 소문자 영숫자만 남긴다."""
    return _NON_ALNUM.sub("", text.lower())


def _last_segment(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def cites_own_event(sources: Iterable[str], event_label: str) -> bool:
    """인용 출처 중 **그 대회 자체를 다룬 문서**가 있는가.

    URL 마지막 조각의 정규화 값이 대회 이름으로 **시작**할 때만 참이다. 단순 포함으로
    하면 "Champions"가 "Night of Champions" 문서에도 걸려 없는 누수를 만든다 —
    이 함수의 값이 화면에 "누수 의심"으로 나가므로 과탐이 과소탐보다 나쁘다.
    """
    label = _normalize(event_label)
    if not label:
        return False
    return any(_normalize(_last_segment(url)).startswith(label) for url in sources)


def summarize_predictions(rows: Sequence[PredictionRow]) -> PredictionTotals:
    """저장된 예측을 센다. **채점은 북메이커 폴백과 사후 재현 표본을 뺀다.**

    폴백은 에이전트가 아무도 답하지 못해 배당으로 대체한 예측이라, 그것까지 세면
    "무엇의 적중률인가"를 말할 수 없게 된다(하네스 §13-Q4와 같은 규칙).

    **모집단이 둘이다.** `agent_rows`는 폴백만 뺀 재고 수치용이고, `scorable_rows`는
    거기서 사후 재현 표본까지 뺀 채점용이다. 둘을 하나로 합치면 `bookmaker_fallback`
    잔차식이 깨진다 — 폴백이 아닌 이유로 빠진 예측이 폴백으로 집계된다.
    """
    agent_rows = [r for r in rows if r.source != BOOKMAKER_FALLBACK]
    scorable_rows = [r for r in rows if is_scorable(r)]
    graded_rows = [r for r in scorable_rows if r.winner_pick is not None]
    correct = sum(1 for r in graded_rows if r.pick == r.winner_pick)
    graded = len(graded_rows)
    interval = wilson_interval(correct, graded)

    return PredictionTotals(
        total=len(rows),
        graded=graded,
        correct=correct,
        incorrect=graded - correct,
        hit_rate=(correct / graded) if graded else None,
        hit_rate_low=interval[0] if interval else None,
        hit_rate_high=interval[1] if interval else None,
        # 평균 둘도 채점 모집단을 쓴다. 사후 재현 표본은 근거 문서가 없어 확신도가
        # 낮게 깔리는데, 그것이 채점 대상 예측의 평균 확신도인 척하면 안 된다.
        avg_confidence=_mean(r.confidence for r in scorable_rows),
        avg_win_probability=_mean(r.win_probability for r in scorable_rows),
        # **잔차식은 `agent_rows`를 그대로 쓴다.** 여기에 채점 모집단을 넣으면
        # 사후 재현 표본이 폴백으로 둔갑한다.
        bookmaker_fallback=len(rows) - len(agent_rows),
    )


def summarize_integrity(
    rows: Sequence[PredictionRow],
    reports: Sequence[ReportRow],
    corpus: CorpusFacts,
    *,
    events_total: int,
) -> IntegrityFacts:
    """적중률을 믿어도 되는지 판정하고 **그 이유를 함께 낸다.**

    **여기서 재는 것은 적중률 하나다.** 그러므로 이 함수의 모든 수치는 그 적중률을
    만든 표본, 곧 `graded_rows` 하나만 본다. 재고 수치는 이 함수의 일이 아니다.
    """
    graded_rows = [r for r in rows if is_scorable(r) and r.winner_pick is not None]
    sample_size = len(graded_rows)
    # **`graded_rows` 기준이어야 한다.** 예전에는 미채점 예측까지 포함한 목록으로
    # 셌는데, 그러면 "채점된 12건이 대회 3개에 걸쳐 있다"는 말이 된다 — 실제로 그
    # 12건은 한 대회에서만 나왔다. 아래 일반화 검사가 보는 값이 바로 이것이라,
    # 모집단이 어긋나면 나와야 할 경고가 통째로 사라진다.
    events_covered = len({r.event_slug for r in graded_rows})

    labels = {(r.event_slug, r.match_key): r.event_label for r in graded_rows}
    sources_by_match: dict[tuple[str, str], list[str]] = {}
    for report in reports:
        key = (report.event_slug, report.match_key)
        if key in labels:
            sources_by_match.setdefault(key, []).extend(report.sources)

    self_referencing = sum(
        1
        for key, urls in sources_by_match.items()
        if urls and cites_own_event(urls, labels[key])
    )
    temporal_verifiable = corpus.chunks_with_published_at > 0

    reasons: list[str] = []
    if sample_size == 0:
        reasons.append("채점된 예측이 없습니다.")
    if 0 < sample_size < 30:
        reasons.append(f"표본이 {sample_size}건으로 작습니다.")
    if events_covered < MIN_EVENTS_FOR_GENERALIZATION:
        reasons.append(f"예측이 대회 {events_covered}개에만 걸쳐 있습니다.")
    if self_referencing > 0:
        reasons.append(
            f"{self_referencing}건이 해당 대회 자체를 다룬 문서를 근거로 인용했습니다 "
            "— 결과가 적힌 글을 읽고 낸 예측일 수 있습니다."
        )
    if not temporal_verifiable:
        reasons.append(
            f"지식 청크 {corpus.chunks_total}건 중 발행일이 있는 것이 0건이라 "
            "예측보다 먼저 쓰인 글인지 검증할 수 없습니다."
        )

    return IntegrityFacts(
        sample_size=sample_size,
        events_covered=events_covered,
        events_total=events_total,
        self_referencing_predictions=self_referencing,
        predictions_with_sources=sum(1 for urls in sources_by_match.values() if urls),
        chunks_total=corpus.chunks_total,
        chunks_with_published_at=corpus.chunks_with_published_at,
        temporal_verifiable=temporal_verifiable,
        generalizable=not reasons,
        reasons=tuple(reasons),
    )


def summarize_agents(reports: Sequence[ReportRow]) -> list[AgentActivity]:
    """에이전트별 활동. **이름은 코드의 이름을 그대로 쓴다** (storyline·odds·rumor)."""
    by_agent: dict[str, list[ReportRow]] = {}
    for report in reports:
        by_agent.setdefault(report.agent, []).append(report)

    activities = [
        AgentActivity(
            agent=agent,
            reports=len(rows),
            with_pick=sum(1 for r in rows if r.pick is not None),
            opinion_rate=(sum(1 for r in rows if r.pick is not None) / len(rows))
            if rows
            else None,
            avg_weight=_mean(r.weight for r in rows),
        )
        for agent, rows in by_agent.items()
    ]
    return sorted(activities, key=lambda a: a.agent)


def _mean(values: Iterable[float]) -> float | None:
    collected = list(values)
    if not collected:
        return None
    return sum(collected) / len(collected)
