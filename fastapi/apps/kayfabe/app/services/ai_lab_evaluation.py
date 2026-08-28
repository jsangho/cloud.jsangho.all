"""AI LAB 평가 자격 판정 — Phase 3-6. **순수 함수다** (DB·LLM을 모른다).

**이 모듈은 성능을 재지 않는다. 무엇을 재도 되는지를 정한다.**

3-0은 "이 적중률을 믿어도 되는가"를 표본 수준에서 물었다. 여기서는 한 칸 앞으로 가서
**예측 하나하나가 애초에 채점 대상이 될 자격이 있는가**를 묻는다. 둘은 다르다 — 표본
경고는 숫자를 붙여 놓고 주의를 주지만, 자격 판정은 **자격 없는 예측을 분모에서 아예
빼낸다.**

그렇게 해야 하는 이유가 운영 데이터에 있다. 저장된 예측은 전부 결과가 기록된 **뒤에**
생성됐다. 그것은 예측이 아니라 사후 재현이고, 어떤 통계 처리로도 예측 능력을 복원할
수 없다. 신뢰구간을 넓히는 문제가 아니라 **분모에 들어가면 안 되는 문제**다.

판정 규칙은 여섯이고 무게가 셋으로 갈린다.

* **제외**(`exclude`) — 애초에 평가 대상이 아니다. 실격이 아니다.
  `not_applicable`(북메이커 폴백) · `external_outcome_known`(사후 재현 표본) ·
  `pending`(결과 없음)
* **실격**(`disqualify`) — 누수가 확정됐다.
  `temporal_inversion`(결과 기록 이후 생성) · `self_reference`(자기 대회 문서 인용)
* **보류**(`hold`) — 누수를 **증명도 반증도 못 한다.**
  `unverifiable_corpus`(인용 문서가 경기보다 앞선 개정본임을 확인 못 함)

**보류를 통과로 세지 않는다.** 모르는 것을 괜찮은 것으로 접으면 이 판정이 하는 일이
사라진다. 그렇다고 실격으로도 세지 않는다 — 확정된 누수와 모르는 것은 다른 사실이다.

**추정하지 않는다.** `ple_prediction_retrievals`가 없으므로 어떤 청크가 실제로
검색됐는지는 기록이 없고, 이 모듈은 그것을 사후에 지어내지 않는다. 판정에 쓰는 것은
저장된 출처 URL까지다.

**Phase 3-12가 코퍼스 규칙의 기준을 바꿨다.** 예전에는 인용 문서에 `published_at`이
있는지만 봤는데, 그 검사는 위키에서 아무것도 증명하지 못했다 — 위키는 그 값을
내보내지 않아 늘 비어 있었고, 채운다 해도 같은 URL이 경기 전후로 계속 고쳐지므로
"그때 결과가 적혀 있었는가"에 답하지 않는다. 이제는 **우리가 읽은 개정본의 시각이
대회 시작일보다 앞서는지**를 본다. 앞서면 결과가 있을 수 없다(충분조건). 나머지 다섯
규칙과 적용 순서는 그대로다.

**Phase 3-7이 축을 하나 더했다.** 시간 규칙이 보는 것은 `ple_matches.finished_at`,
곧 결과가 **DB에 들어온** 시각이다. 그래서 이미 끝난 경기를 나중에 예측하고 결과를
그 뒤에 입력하면 시간 규칙을 통과해 버린다 — 규칙이 틀린 게 아니라 시스템 밖의 앎을
볼 수 없을 뿐이다. `external_outcome_known`이 그 자리를 맡는다. **기존 다섯 규칙은
한 줄도 바뀌지 않았다.**
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

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

#: 자격 상태. 여섯은 **서로 겹치지 않고 전체를 덮는다** — 합이 예측 수와 같아야 한다.
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_EX_POST = "ex_post"
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
        code="external_outcome_known",
        label="생성 전 결과가 외부에 알려짐",
        severity=SEVERITY_EXCLUDE,
        description=(
            "예측을 만들 때 결과가 이 시스템 밖에서 이미 알려져 있었다고 기록된 "
            "표본입니다. 사후 재현이므로 채점 대상이 아닙니다 — 누수가 확정된 "
            "실격과 달리, 표본의 성격이 처음부터 다릅니다."
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
        label="인용 문서가 경기보다 앞선 개정본이 아님",
        severity=SEVERITY_HOLD,
        description=(
            "인용한 문서를 우리가 읽은 개정본이 경기 시작일보다 앞선다는 것을 "
            "확인할 수 없습니다. 개정본 시각이나 대회 날짜를 모르는 경우, 그리고 "
            "경기 당일 이후 개정본인 경우가 모두 여기에 들어갑니다. 모르는 것을 "
            "과거로 간주하지 않으므로 통과도 실격도 아닌 보류입니다."
        ),
    ),
)

_RULE_BY_CODE = {rule.code: rule for rule in RULES}


@dataclass(frozen=True)
class DocumentProvenance:
    """문서 하나의 개정본 계보 (Phase 3-12).

    `_corpus`가 판정에 쓰는 값만 담는다. 문서 전체 통계인 `DocumentRow`를 그대로
    넘기지 않는 이유는, 판정이 무엇을 보는지가 타입에 드러나야 하기 때문이다.
    """

    chunks: int
    chunks_with_revision: int
    #: 이 문서 청크 중 **가장 늦은** 개정본 시각. 최악을 기준으로 판정한다.
    latest_revised_at: datetime | None
    last_collected_at: datetime | None

    @property
    def is_complete(self) -> bool:
        """청크 **전부**가 개정본 시각을 갖고 있고, 그 시각이 앞뒤가 맞는가.

        하나라도 비면 그 문서의 계보는 불완전하다 — 검색이 하필 그 청크를 골랐을 수
        있고, 어느 청크가 뽑혔는지는 기록이 없다. 부분 계보를 통과로 접으면 판정이
        운에 기대게 된다.

        **개정본이 수집보다 나중일 수는 없다.** 그런 값이 나왔다면 시계가 틀렸거나
        계보가 엉뚱한 문서 것이다. 어느 쪽이든 그 계보로는 아무것도 증명할 수 없으므로
        불완전으로 본다 — 시각을 고쳐 쓰지 않는다.
        """
        if self.chunks <= 0 or self.chunks_with_revision != self.chunks:
            return False
        if self.latest_revised_at is None:
            return False
        if (
            self.last_collected_at is not None
            and self.latest_revised_at > self.last_collected_at
        ):
            return False
        return True


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
    """여섯 칸의 합이 `predictions`와 같다 — 어디로도 새지 않는다."""

    predictions: int
    fallback: int
    #: 생성 전에 결과가 시스템 밖에서 알려져 있던 표본 (Phase 3-7). **실격이 아니다.**
    ex_post: int
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
    provenance_by_url = {
        _canonical(doc.source_url): DocumentProvenance(
            chunks=doc.chunks,
            chunks_with_revision=doc.chunks_with_revision,
            latest_revised_at=doc.latest_revised_at,
            last_collected_at=doc.last_collected_at,
        )
        for doc in documents
    }

    items = [
        _judge(
            row,
            sources_by_match.get((row.event_slug, row.match_key), ()),
            provenance_by_url,
        )
        for row in predictions
    ]
    # 자격 있는 것이 위로, 그다음 실격·보류 순. 같으면 경기 키 순으로 고정한다.
    items.sort(key=lambda i: (_STATUS_ORDER[i.status], i.match_key))

    totals = EvaluationTotals(
        predictions=len(items),
        fallback=_count(items, STATUS_NOT_APPLICABLE),
        ex_post=_count(items, STATUS_EX_POST),
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
    STATUS_EX_POST: 4,
    STATUS_NOT_APPLICABLE: 5,
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
    provenance_by_url: dict[str, DocumentProvenance],
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

    if row.outcome_known_externally is True:
        # **`is True`여야 한다.** `if row.outcome_known_externally:`로 쓰면 `None`이
        # 함께 걸려 선언한 적 없는 옛 예측까지 여기로 빨려 들어온다.
        #
        # 결과가 기록되기 전이어도(그래서 `pending`으로 보일 수 있어도) 이 표본은
        # 채점 대상이 되지 못한다. 그 사실을 나중이 아니라 지금 말한다.
        return _item(
            row,
            STATUS_EX_POST,
            (
                _verdict(
                    "external_outcome_known",
                    failed=True,
                    applicable=True,
                    # 선언의 근거는 사람이 쓴 문장이다. 여기서 지어내지 않는다.
                    detail=row.provenance_note
                    or "생성 시점에 결과가 시스템 밖에서 이미 알려져 있었습니다.",
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
        _corpus(sources, provenance_by_url, row.event_start_date),
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


def _corpus(
    sources: tuple[str, ...],
    provenance_by_url: dict[str, DocumentProvenance],
    event_start_date: date | None,
) -> RuleVerdict:
    """인용 문서가 **경기보다 앞선 개정본**인지 확인할 수 있는가 (Phase 3-12).

    예전에는 `published_at`이 있는지만 봤다. 그 검사는 위키에서 아무것도 증명하지
    못한다 — 위키는 그 값을 내보내지 않아 늘 비어 있었고, 채운다 해도 문서 최초
    생성일에 가까워 "그때 결과가 적혀 있었는가"에 답하지 않는다. 같은 URL이 경기
    전후로 계속 고쳐지기 때문이다.

    그래서 재는 것을 바꿨다. **개정본 시각이 대회 시작일보다 앞서면** 그 글에 결과가
    적혀 있을 수 없다 — 충분조건이다. 뒤면 없다는 것을 증명할 수 없으므로 인정하지
    않는다. 실측이 이 구분을 뒷받침한다: SummerSlam 문서는 우리가 읽은 개정본이
    경기 3일 뒤(`2026-08-05`)라 결과가 통째로 실려 있었고, MITB 문서는 경기 두 달
    전(`2026-08-01`) 개정본이라 경기 목록조차 없었다.

    **모르는 것은 통과가 아니다.** 개정본 시각이 없거나(레거시 청크) 대회 날짜가
    없으면 비교 자체가 불가능하므로 보류로 간다. `severity=hold`라 실격도 아니다 —
    확정된 누수와 모르는 것은 다른 사실이다.

    **어떤 청크가 검색됐는지는 여전히 보지 않는다** — 그 기록이 없다(`ple_prediction_
    retrievals` 미도입). 그래서 문서 단위로, 그 문서의 **가장 늦은** 개정본을 기준으로
    판정한다. 최악을 기준으로 잡아야 "하나는 경기 전, 하나는 경기 후"인 문서가
    통과하지 않는다.
    """
    if not sources:
        return _verdict(
            "unverifiable_corpus",
            failed=False,
            applicable=True,
            detail="인용 출처가 없어 확인할 문서가 없습니다.",
        )

    if event_start_date is None:
        return _verdict(
            "unverifiable_corpus",
            failed=True,
            applicable=True,
            detail=(
                "대회 날짜를 몰라 인용 문서가 경기보다 앞선 글인지 비교할 수 없습니다."
            ),
        )

    unknown: list[str] = []
    too_late: list[str] = []
    for url in sources:
        provenance = provenance_by_url.get(_canonical(url))
        if provenance is None or not provenance.is_complete:
            unknown.append(url)
            continue
        revised_at = provenance.latest_revised_at
        if revised_at is None:
            unknown.append(url)
            continue
        # **날짜끼리 비교한다.** 대회 날짜는 `DATE`라 시각이 없고, 없는 정밀도를
        # 지어내지 않는다. 같은 날이면 통과시키지 않는다 — 경기 당일 개정본에
        # 결과가 없다는 보장이 없다.
        if revised_at.date() >= event_start_date:
            too_late.append(url)

    if too_late:
        return _verdict(
            "unverifiable_corpus",
            failed=True,
            applicable=True,
            detail=(
                f"인용 문서 {len(too_late)}/{len(sources)}건이 경기 당일 이후 "
                "개정본입니다. 결과가 적혀 있지 않다고 증명할 수 없습니다."
            ),
        )
    if unknown:
        return _verdict(
            "unverifiable_corpus",
            failed=True,
            applicable=True,
            detail=(
                f"인용 문서 {len(unknown)}/{len(sources)}건의 개정본 시각을 확인할 "
                "수 없습니다."
            ),
        )
    return _verdict(
        "unverifiable_corpus",
        failed=False,
        applicable=True,
        detail=(f"인용 문서 {len(sources)}건 모두 경기 시작일보다 앞선 개정본입니다."),
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
