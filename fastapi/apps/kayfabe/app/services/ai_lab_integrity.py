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
from datetime import datetime

#: 윌슨 구간의 z (95%). 바꾸면 화면 문구의 "95%"도 함께 바꾼다.
Z_95 = 1.959963984540054

#: 일반화 판정에 쓰는 최소 대회 수. 한 대회만으로는 그 대회의 특성과
#: 모델의 실력을 가를 수 없다.
MIN_EVENTS_FOR_GENERALIZATION = 2

#: 북메이커 폴백 예측의 `source` 값. 적중률 집계에서 빠진다
#: (`ple_events_pg_repository.get_ai_stats`와 같은 규칙).
BOOKMAKER_FALLBACK = "bookmaker_fallback"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


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
    """저장된 예측을 센다. **채점은 북메이커 폴백을 뺀다.**

    폴백은 에이전트가 아무도 답하지 못해 배당으로 대체한 예측이라, 그것까지 세면
    "무엇의 적중률인가"를 말할 수 없게 된다(하네스 §13-Q4와 같은 규칙).
    """
    agent_rows = [r for r in rows if r.source != BOOKMAKER_FALLBACK]
    graded_rows = [r for r in agent_rows if r.winner_pick is not None]
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
        avg_confidence=_mean(r.confidence for r in agent_rows),
        avg_win_probability=_mean(r.win_probability for r in agent_rows),
        bookmaker_fallback=len(rows) - len(agent_rows),
    )


def summarize_integrity(
    rows: Sequence[PredictionRow],
    reports: Sequence[ReportRow],
    corpus: CorpusFacts,
    *,
    events_total: int,
) -> IntegrityFacts:
    """적중률을 믿어도 되는지 판정하고 **그 이유를 함께 낸다.**"""
    agent_rows = [r for r in rows if r.source != BOOKMAKER_FALLBACK]
    graded_rows = [r for r in agent_rows if r.winner_pick is not None]
    sample_size = len(graded_rows)
    events_covered = len({r.event_slug for r in agent_rows})

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
