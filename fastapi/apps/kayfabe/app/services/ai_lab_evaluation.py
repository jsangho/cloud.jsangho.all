"""AI LAB 평가 자격 판정 — Phase 3-6. **순수 함수다** (DB·LLM을 모른다).

**이 모듈은 성능을 재지 않는다. 무엇을 재도 되는지를 정한다.**

3-0은 "이 적중률을 믿어도 되는가"를 표본 수준에서 물었다. 여기서는 한 칸 앞으로 가서
**예측 하나하나가 애초에 채점 대상이 될 자격이 있는가**를 묻는다. 둘은 다르다 — 표본
경고는 숫자를 붙여 놓고 주의를 주지만, 자격 판정은 **자격 없는 예측을 분모에서 아예
빼낸다.**

그렇게 해야 하는 이유가 운영 데이터에 있다. 저장된 예측은 전부 결과가 기록된 **뒤에**
생성됐다. 그것은 예측이 아니라 사후 재현이고, 어떤 통계 처리로도 예측 능력을 복원할
수 없다. 신뢰구간을 넓히는 문제가 아니라 **분모에 들어가면 안 되는 문제**다.

판정 규칙은 다섯이고 무게가 셋으로 갈린다.

* **제외**(`exclude`) — 애초에 평가 대상이 아니다. 실격이 아니다.
  `not_applicable`(북메이커 폴백) · `pending`(결과 없음)
* **실격**(`disqualify`) — 누수가 확정됐다.
  `temporal_inversion`(결과 기록 이후 생성) · `self_reference`(자기 대회 문서 인용)
* **보류**(`hold`) — 누수를 **증명도 반증도 못 한다.**
  `unverifiable_corpus`(인용 문서의 발행일 미상)

**보류를 통과로 세지 않는다.** 모르는 것을 괜찮은 것으로 접으면 이 판정이 하는 일이
사라진다. 그렇다고 실격으로도 세지 않는다 — 확정된 누수와 모르는 것은 다른 사실이다.

**추정하지 않는다.** `ple_prediction_retrievals`가 없으므로 어떤 청크가 실제로
검색됐는지는 기록이 없고, 이 모듈은 그것을 사후에 지어내지 않는다. 판정에 쓰는 것은
저장된 출처 URL까지다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from kayfabe.app.services.ai_lab_integrity import (
    BOOKMAKER_FALLBACK,
    PredictionRow,
    ReportRow,
    cites_own_event,
    wilson_interval,
)

# 3-4가 문서 대조에 쓰는 것과 **같은 정규화**를 쓴다. 여기서 따로 만들면 두 화면이
# 서로 다른 문서를 같은 문서라고 말하게 된다.
from kayfabe.app.services.ai_lab_knowledge import DocumentRow, _canonical

#: 자격 상태. 다섯은 **서로 겹치지 않고 전체를 덮는다** — 합이 예측 수와 같아야 한다.
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_PENDING = "pending"
STATUS_DISQUALIFIED = "disqualified"
STATUS_HELD = "held"
STATUS_ELIGIBLE = "eligible"

SEVERITY_EXCLUDE = "exclude"
SEVERITY_DISQUALIFY = "disqualify"
SEVERITY_HOLD = "hold"


@dataclass(frozen=True)
class Rule:
    """판정 규칙 하나. **화면이 문구를 지어내지 않도록 설명까지 서버가 낸다.**"""

    code: str
    label: str
    severity: str
    description: str


#: 적용 순서다. 앞의 규칙이 막으면 뒤는 판정하지 않는다 — 폴백 예측에 "결과 기록보다
#: 먼저였나"를 묻는 것은 뜻이 없기 때문이다.
RULES: tuple[Rule, ...] = (
    Rule(
        code=STATUS_NOT_APPLICABLE,
        label="평가 대상 아님",
        severity=SEVERITY_EXCLUDE,
        description=(
            "에이전트가 아무도 답하지 못해 북메이커 배당으로 대체한 예측입니다. "
            "에이전트의 판단이 아니므로 채점 대상이 아닙니다."
        ),
    ),
    Rule(
        code=STATUS_PENDING,
        label="결과 없음",
        severity=SEVERITY_EXCLUDE,
        description="아직 결과가 나오지 않았습니다. 오답도 실격도 아닙니다.",
    ),
    Rule(
        code="temporal_inversion",
        label="결과 기록 이후 생성",
        severity=SEVERITY_DISQUALIFY,
        description=(
            "결과가 시스템에 기록된 뒤에 만들어진 예측입니다. 정답을 알 수 있는 "
            "상태에서 생성됐으므로 예측 능력의 근거가 되지 못합니다. 같은 시각도 "
            "먼저였다고 말할 수 없으므로 실격입니다."
        ),
    ),
    Rule(
        code="self_reference",
        label="자기 대회 문서 인용",
        severity=SEVERITY_DISQUALIFY,
        description=(
            "그 대회 자체를 다룬 문서를 근거로 실었습니다. 대회 문서에는 경기 결과가 "
            "적혀 있으므로 예측이 아니라 열람일 수 있습니다."
        ),
    ),
    Rule(
        code="unverifiable_corpus",
        label="인용 문서의 발행일 미상",
        severity=SEVERITY_HOLD,
        description=(
            "인용한 문서가 예측보다 먼저 쓰인 글인지 확인할 수 없습니다. 발행일이 "
            "없는 문서를 과거 문서로 간주하지 않으므로, 통과도 실격도 아닌 보류입니다."
        ),
    ),
)

_RULE_BY_CODE = {rule.code: rule for rule in RULES}


@dataclass(frozen=True)
class RuleVerdict:
    """규칙 하나에 대한 판정.

    `applicable=False`는 **통과가 아니다** — 잴 수 없었다는 뜻이고, 잴 수 없으면
    그 예측은 자격을 얻지 못한다.
    """

    code: str
    failed: bool
    applicable: bool
    #: 왜 그렇게 판정했는지. 사실만 적는다.
    detail: str


@dataclass(frozen=True)
class EvaluationItem:
    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    generated_at: datetime
    #: 결과가 시스템에 기록된 시각. **경기가 끝난 시각이 아니다.**
    result_recorded_at: datetime | None
    status: str
    eligible: bool
    verdicts: tuple[RuleVerdict, ...]


@dataclass(frozen=True)
class RuleTally:
    """규칙별로 몇 건을 막았는가. `severity`가 실격과 보류를 가른다."""

    code: str
    label: str
    severity: str
    description: str
    blocked: int


@dataclass(frozen=True)
class EvaluationTotals:
    """다섯 칸의 합이 `predictions`와 같다 — 어디로도 새지 않는다."""

    predictions: int
    fallback: int
    pending: int
    disqualified: int
    held: int
    eligible: int


@dataclass(frozen=True)
class EligiblePerformance:
    """**자격 있는 표본이 있을 때만 만들어진다.** 0건이면 이 값 자체가 `None`이다."""

    sample: int
    correct: int
    incorrect: int
    accuracy: float
    accuracy_low: float
    accuracy_high: float
    events_covered: int


def summarize_evaluation(
    predictions: Sequence[PredictionRow],
    reports: Sequence[ReportRow],
    documents: Sequence[DocumentRow],
) -> tuple[
    EvaluationTotals,
    list[RuleTally],
    list[EvaluationItem],
    EligiblePerformance | None,
]:
    """예측마다 자격을 판정하고, **자격이 있을 때만** 성능을 계산한다.

    새 쿼리를 쓰지 않는다 — 3-0·3-3·3-4가 이미 읽는 세 목록을 잇는다. 조인 키는
    3-3·3-5와 같은 `(event_slug, match_key)`다.
    """
    sources_by_match = _sources_by_match(reports)
    published_by_url = {
        _canonical(doc.source_url): doc.chunks_with_published_at > 0
        for doc in documents
    }

    items = [
        _judge(
            row,
            sources_by_match.get((row.event_slug, row.match_key), ()),
            published_by_url,
        )
        for row in predictions
    ]
    # 자격 있는 것이 위로, 그다음 실격·보류 순. 같으면 경기 키 순으로 고정한다.
    items.sort(key=lambda i: (_STATUS_ORDER[i.status], i.match_key))

    totals = EvaluationTotals(
        predictions=len(items),
        fallback=_count(items, STATUS_NOT_APPLICABLE),
        pending=_count(items, STATUS_PENDING),
        disqualified=_count(items, STATUS_DISQUALIFIED),
        held=_count(items, STATUS_HELD),
        eligible=_count(items, STATUS_ELIGIBLE),
    )

    eligible_keys = {
        (i.event_slug, i.match_key) for i in items if i.status == STATUS_ELIGIBLE
    }
    performance = None
    if eligible_keys:
        # **자격이 0건이면 이 줄에 오지 않는다.** 0건짜리 비율을 만들지 않기 위해
        # 집계 함수를 호출조차 하지 않는다.
        performance = summarize_eligible_performance(
            [r for r in predictions if (r.event_slug, r.match_key) in eligible_keys]
        )

    return totals, _tally(items), items, performance


def summarize_eligible_performance(
    rows: Sequence[PredictionRow],
) -> EligiblePerformance:
    """자격 있는 표본의 적중률 + 윌슨 95% 신뢰구간.

    **빈 목록으로 부르지 않는다.** 0건에서 나올 수 있는 정직한 값이 없기 때문이다 —
    호출자가 자격을 먼저 세고, 없으면 `None`을 그대로 내보낸다.
    """
    if not rows:
        raise ValueError(
            "자격 있는 표본이 없습니다. 0건에서는 성능을 계산하지 않습니다."
        )

    correct = sum(1 for r in rows if r.pick == r.winner_pick)
    interval = wilson_interval(correct, len(rows))
    assert interval is not None  # rows가 비어 있지 않으므로 항상 나온다.

    return EligiblePerformance(
        sample=len(rows),
        correct=correct,
        incorrect=len(rows) - correct,
        accuracy=correct / len(rows),
        accuracy_low=interval[0],
        accuracy_high=interval[1],
        events_covered=len({r.event_slug for r in rows}),
    )


_STATUS_ORDER = {
    STATUS_ELIGIBLE: 0,
    STATUS_HELD: 1,
    STATUS_DISQUALIFIED: 2,
    STATUS_PENDING: 3,
    STATUS_NOT_APPLICABLE: 4,
}


def _sources_by_match(
    reports: Sequence[ReportRow],
) -> dict[tuple[str, str], tuple[str, ...]]:
    """경기별로 인용 출처를 모은다. 순서를 지키고 중복만 지운다."""
    grouped: dict[tuple[str, str], list[str]] = {}
    for report in reports:
        grouped.setdefault((report.event_slug, report.match_key), []).extend(
            report.sources
        )
    return {key: tuple(dict.fromkeys(urls)) for key, urls in grouped.items()}


def _judge(
    row: PredictionRow,
    sources: tuple[str, ...],
    published_by_url: dict[str, bool],
) -> EvaluationItem:
    """규칙을 **적용 순서대로** 본다. 앞이 막으면 뒤는 판정하지 않는다."""
    if row.source == BOOKMAKER_FALLBACK:
        return _item(
            row,
            STATUS_NOT_APPLICABLE,
            (
                _verdict(
                    STATUS_NOT_APPLICABLE,
                    failed=True,
                    applicable=True,
                    detail="북메이커 배당으로 대체된 예측입니다.",
                ),
            ),
        )

    if row.winner_pick is None:
        return _item(
            row,
            STATUS_PENDING,
            (
                _verdict(
                    STATUS_PENDING,
                    failed=True,
                    applicable=True,
                    detail="아직 결과가 나오지 않았습니다.",
                ),
            ),
        )

    verdicts = (
        _temporal(row),
        _self_reference(row, sources),
        _corpus(sources, published_by_url),
    )
    return _item(row, _status_of(verdicts), verdicts)


def _temporal(row: PredictionRow) -> RuleVerdict:
    """결과가 기록되기 **전에** 만들어졌는가. 같은 시각도 실격이다."""
    if row.finished_at is None:
        return _verdict(
            "temporal_inversion",
            failed=False,
            applicable=False,
            detail=(
                "결과가 시스템에 기록된 시각이 없어 예측이 먼저였는지 판정할 수 "
                "없습니다."
            ),
        )
    if row.generated_at >= row.finished_at:
        return _verdict(
            "temporal_inversion",
            failed=True,
            applicable=True,
            detail=(
                f"결과 기록 {row.finished_at.isoformat()} 이후인 "
                f"{row.generated_at.isoformat()}에 생성됐습니다."
            ),
        )
    return _verdict(
        "temporal_inversion",
        failed=False,
        applicable=True,
        detail=f"결과 기록 {row.finished_at.isoformat()}보다 먼저 생성됐습니다.",
    )


def _self_reference(row: PredictionRow, sources: tuple[str, ...]) -> RuleVerdict:
    """**출처가 없으면 자기참조라고 추정하지 않는다.**

    없음은 무죄도 유죄도 아니지만, 이 규칙이 잡는 것은 "인용했다"는 사실이다.
    인용이 없으면 이 규칙으로 막을 근거가 없다 — 다른 경로의 누수는 코퍼스 규칙과
    시간 규칙이 본다.
    """
    if not sources:
        return _verdict(
            "self_reference",
            failed=False,
            applicable=True,
            detail="저장된 인용 출처가 없습니다.",
        )
    if cites_own_event(sources, row.event_label):
        return _verdict(
            "self_reference",
            failed=True,
            applicable=True,
            detail=f"'{row.event_label}' 대회 자체를 다룬 문서를 인용했습니다.",
        )
    return _verdict(
        "self_reference",
        failed=False,
        applicable=True,
        detail=f"인용 출처 {len(sources)}건에 그 대회 문서가 없습니다.",
    )


def _corpus(sources: tuple[str, ...], published_by_url: dict[str, bool]) -> RuleVerdict:
    """인용 문서가 예측보다 먼저 쓰인 글인지 확인할 수 있는가.

    **어떤 청크가 검색됐는지는 보지 않는다** — 그 기록이 없다. 저장된 출처 URL의
    문서에 발행일이 있는지까지가 지금 확인 가능한 전부다.
    """
    if not sources:
        return _verdict(
            "unverifiable_corpus",
            failed=False,
            applicable=True,
            detail="인용 출처가 없어 확인할 문서가 없습니다.",
        )

    unknown = [url for url in sources if not published_by_url.get(_canonical(url))]
    if unknown:
        return _verdict(
            "unverifiable_corpus",
            failed=True,
            applicable=True,
            detail=(
                f"인용 문서 {len(unknown)}/{len(sources)}건의 발행일을 확인할 수 "
                "없습니다."
            ),
        )
    return _verdict(
        "unverifiable_corpus",
        failed=False,
        applicable=True,
        detail=f"인용 문서 {len(sources)}건 모두 발행일이 있습니다.",
    )


def _status_of(verdicts: tuple[RuleVerdict, ...]) -> str:
    """실격이 하나라도 있으면 실격. 없으면 보류 여부를 본다.

    **잴 수 없었던 규칙(`applicable=False`)은 통과가 아니다.** 모르는 것을 괜찮은
    것으로 접으면 자격 판정이 하는 일이 없어진다.
    """
    for verdict in verdicts:
        if verdict.failed and _RULE_BY_CODE[verdict.code].severity == (
            SEVERITY_DISQUALIFY
        ):
            return STATUS_DISQUALIFIED
    for verdict in verdicts:
        if verdict.failed or not verdict.applicable:
            return STATUS_HELD
    return STATUS_ELIGIBLE


def _tally(items: Sequence[EvaluationItem]) -> list[RuleTally]:
    """규칙별로 몇 건을 막았는가. **규칙 목록은 고정이다** — 0건이어도 자리를 지운다."""
    blocked: dict[str, int] = {rule.code: 0 for rule in RULES}
    for item in items:
        if item.eligible:
            continue
        for verdict in item.verdicts:
            if verdict.failed or not verdict.applicable:
                blocked[verdict.code] += 1
    return [
        RuleTally(
            code=rule.code,
            label=rule.label,
            severity=rule.severity,
            description=rule.description,
            blocked=blocked[rule.code],
        )
        for rule in RULES
    ]


def _count(items: Sequence[EvaluationItem], status: str) -> int:
    return sum(1 for item in items if item.status == status)


def _item(
    row: PredictionRow, status: str, verdicts: tuple[RuleVerdict, ...]
) -> EvaluationItem:
    return EvaluationItem(
        event_slug=row.event_slug,
        event_label=row.event_label,
        match_key=row.match_key,
        match_title=row.match_title,
        generated_at=row.generated_at,
        result_recorded_at=row.finished_at,
        status=status,
        eligible=status == STATUS_ELIGIBLE,
        verdicts=verdicts,
    )


def _verdict(code: str, *, failed: bool, applicable: bool, detail: str) -> RuleVerdict:
    return RuleVerdict(code=code, failed=failed, applicable=applicable, detail=detail)
