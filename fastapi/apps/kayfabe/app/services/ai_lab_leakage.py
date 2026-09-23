"""누수 그래프 — 어느 문서가 어느 예측을 막았는가 (Phase 10). **순수 함수다.**

축이 둘 있는데 잇는 간선이 없었다. 3-4(`ai_lab_knowledge`)는 **문서가 쓰였는가**를
세고, 3-6(`ai_lab_evaluation`)은 **예측이 자격을 얻었는가**를 판정한다. 그래서
"실격 12건"은 보이는데 **무엇 때문에** 12건인지가 문서 단위로는 어디에도 없었다.
이 모듈이 그 간선을 만든다.

**새 판정을 하지 않는다.** 예측의 상태는 `summarize_evaluation`이 낸 것을 그대로
받고, 여기서는 그 결론의 원인을 문서로 나눌 뿐이다. 두 값이 어긋나는 일이 구조적으로
없어야 한다.

나누는 방법이 둘이고, **묻는 것이 다르므로 섞지 않는다.**

1. **기여**(`codes`) — 규칙이 쓰는 것과 **같은 프리미티브**를 문서마다 그대로 적용해
   읽는다(`_temporal_position`·`_revision_position`·`cites_own_event`). 반사실로
   재지 않는 이유는 **원인이 여럿일 때 아무도 원인이 아니게 되기 때문**이다 —
   대회 문서를 둘 인용했으면 어느 쪽을 빼도 자기참조는 남고, 반사실만 쓰면 둘 다
   무죄가 된다.
2. **단독 원인**(`sole_cause`) — 이쪽은 반사실이다. 그 문서를 뺀 입력으로
   `summarize_evaluation`을 **다시 돌려** 자격을 얻는지 본다. 같은 규칙에 다른
   입력이지 다른 규칙이 아니다.

**규칙이 무엇을 보는지를 그대로 따른다.** 자기참조는 언제나 인용 출처를 보고
(`_self_reference`), 코퍼스 규칙은 검색 기록이 있으면 그쪽만 본다
(`_corpus_from_retrievals`가 `_corpus`를 이긴다). 그래서 기록이 있는 예측에서는
출처에만 있는 문서에 시간 책임을 묻지 않는다 — 판정이 그 문서를 보지 않았기 때문이다.

**문서로 돌릴 수 없는 규칙이 다섯이다.** `not_applicable`·`external_outcome_known`·
`withdrawn_match`·`pending`·`temporal_inversion`은 예측 자체의 사실이지 근거의
성질이 아니다. 그래서 막힌 예측 전부가 이 그래프에 오지 않고, 오지 않은 수를
`unattributed`로 **따로 센다** — 합이 안 맞는 것을 감추면 그래프가 거짓말을 한다.

**문서를 지워도 이미 만들어진 예측의 자격은 되살아나지 않는다.** 그 예측은 그 글을
실제로 읽었고, 코퍼스에서 지우는 것이 그 사실을 바꾸지 않는다. `sole_cause`가 말하는
것은 "지금 판정을 뒤집을 수 있다"가 아니라 **"이 문서 하나가 그 판정을 혼자
결정했다"**이고, 쓰임새는 앞으로 무엇을 수집하지 않을지를 정하는 데 있다.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from kayfabe.app.services.ai_lab_evaluation import (
    EVIDENCE_BEFORE_EVENT,
    REVISION_AFTER_PREDICTION,
    STATUS_DISQUALIFIED,
    STATUS_ELIGIBLE,
    STATUS_HELD,
    DocumentProvenance,
    EvaluationItem,
    RetrievalRow,
    _revision_position,
    _temporal_position,
    _to_utc,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import (
    PredictionRow,
    ReportRow,
    cites_own_event,
)

# 3-4·3-6이 문서 대조에 쓰는 것과 **같은 정규화**를 쓴다. 여기서 따로 만들면 세
# 화면이 서로 다른 문서를 같은 문서라고 말하게 된다.
from kayfabe.app.services.ai_lab_knowledge import DocumentRow, _canonical

#: 그래프가 다루는 규칙 셋. **나머지 다섯은 문서의 성질이 아니다.**
DOCUMENT_RULES = ("self_reference", "unverifiable_corpus", "revision_after_prediction")

#: 막혔다고 보는 상태 둘. 제외(`exclude`)는 막힌 것이 아니라 **묻지 않은 것**이다.
BLOCKED_STATUSES = (STATUS_DISQUALIFIED, STATUS_HELD)


@dataclass(frozen=True)
class LeakageEdge:
    """문서 하나가 예측 하나를 막은 간선."""

    event_slug: str
    event_label: str
    match_key: str
    match_title: str
    #: 판정이 낸 그 예측의 상태. **여기서 다시 정하지 않는다.**
    status: str
    #: 이 문서가 실패시킨 규칙 코드. `DOCUMENT_RULES`의 부분집합이고 비어 있지 않다.
    codes: tuple[str, ...]
    #: 이 문서만 없었다면 자격을 얻었는가 (반사실).
    sole_cause: bool
    #: 이 문서가 그 예측의 **유일한 근거**였는가.
    #:
    #: 유일했다면 빼는 순간 근거가 0건이 되고, 코퍼스 규칙은 "확인할 문서가 없다"며
    #: 통과시킨다. 그 통과를 `sole_cause`로 세면 **근거가 사라져서 자격을 얻었다**는
    #: 말이 되므로 세지 않고, 대신 그 사실을 이 칸으로 내보낸다.
    sole_evidence: bool


@dataclass(frozen=True)
class LeakageDocument:
    """문서 하나와 그것이 막은 예측들."""

    source_url: str
    source_domain: str
    #: 이 문서가 막은 예측 수.
    blocked: int
    #: 그중 이 문서가 혼자 결정한 수.
    sole_cause: int
    #: 이 문서가 실패시킨 규칙 코드 전부(간선들의 합집합).
    codes: tuple[str, ...]
    predictions: tuple[LeakageEdge, ...]


@dataclass(frozen=True)
class LeakageTotals:
    """**합이 맞아야 한다**: `blocked_predictions == attributed + unattributed`."""

    #: 실격·보류 예측 수. 제외(폴백·사후재현·회수·결과없음)는 세지 않는다.
    blocked_predictions: int
    #: 그중 문서로 설명되는 수.
    attributed: int
    #: 문서로 돌릴 수 없는 수. **0이 아니면 그 자체가 사실이다** — 시간 역전처럼
    #: 근거의 성질이 아닌 이유로 막힌 예측이 그만큼 있다는 뜻이다.
    unattributed: int
    #: 간선을 가진 문서 수.
    documents: int
    #: 단독 원인이 있는 예측 수 (문서 하나가 혼자 결정한 판정).
    sole_cause_predictions: int


def summarize_leakage(
    predictions: Sequence[PredictionRow],
    reports: Sequence[ReportRow],
    documents: Sequence[DocumentRow],
    retrievals: Sequence[RetrievalRow] = (),
) -> tuple[LeakageTotals, list[LeakageDocument]]:
    """막힌 예측을 문서로 나눈다. **새 쿼리도 새 판정도 없다.**

    평가 화면이 이미 읽는 네 목록을 그대로 받고, 상태는 `summarize_evaluation`이
    낸 것을 쓴다.
    """
    _, _, items, _ = summarize_evaluation(predictions, reports, documents, retrievals)
    blocked = [item for item in items if item.status in BLOCKED_STATUSES]
    if not blocked:
        return LeakageTotals(0, 0, 0, 0, 0), []

    by_key = {(row.event_slug, row.match_key): row for row in predictions}
    domain_by_url = {_canonical(doc.source_url): doc.source_domain for doc in documents}
    grounds = _grounds(blocked, reports, documents, retrievals)

    # 1단계: 같은 프리미티브로 문서마다 기여를 읽는다 (반사실 아님).
    contributions: dict[str, list[tuple[EvaluationItem, tuple[str, ...]]]] = {}
    for item in blocked:
        row = by_key[_key(item)]
        for url, codes in _contributions(row, grounds[_key(item)]).items():
            contributions.setdefault(url, []).append((item, codes))

    # 2단계: 간선을 가진 문서만 반사실로 단독 원인을 가린다.
    results = []
    for url, entries in contributions.items():
        recovered = _recovered_without(
            url,
            [by_key[_key(item)] for item, _ in entries],
            reports,
            documents,
            retrievals,
        )
        edges = tuple(
            _edge(item, codes, grounds[_key(item)], recovered)
            for item, codes in entries
        )
        results.append(
            LeakageDocument(
                source_url=url,
                source_domain=domain_by_url.get(url, _domain_of(url)),
                blocked=len(edges),
                sole_cause=sum(1 for edge in edges if edge.sole_cause),
                codes=_ordered_codes({c for edge in edges for c in edge.codes}),
                predictions=tuple(
                    sorted(edges, key=lambda e: (e.event_slug, e.match_key))
                ),
            )
        )

    # 많이 막은 문서가 위로. 같으면 단독 원인이 많은 쪽, 그다음 URL 순 — 재조회에도
    # 순서가 안 흔들린다.
    results.sort(key=lambda d: (-d.blocked, -d.sole_cause, d.source_url))

    attributed = {
        _key(item) for entries in contributions.values() for item, _ in entries
    }
    return (
        LeakageTotals(
            blocked_predictions=len(blocked),
            attributed=len(attributed),
            unattributed=len(blocked) - len(attributed),
            documents=len(results),
            sole_cause_predictions=len(
                {
                    (edge.event_slug, edge.match_key)
                    for doc in results
                    for edge in doc.predictions
                    if edge.sole_cause
                }
            ),
        ),
        results,
    )


@dataclass(frozen=True)
class _Ground:
    """예측 하나가 **딛고 선** 문서 하나. 판정이 실제로 본 값만 담는다.

    두 칸을 나눠 두는 이유는 규칙마다 보는 자리가 다르기 때문이다 — 자기참조는
    인용 출처를, 코퍼스·개정본 규칙은 검색 기록을 본다. 한 칸으로 접으면 판정이
    보지도 않은 문서에 책임을 묻게 된다.
    """

    url: str
    #: 판정이 이 문서에 대해 아는 개정본 시각. 계보가 불완전하면 `None`이다 —
    #: `_corpus`가 그렇게 읽으므로 여기서도 그렇게 읽는다.
    revised_at: datetime | None
    in_sources: bool
    in_retrievals: bool


def _grounds(
    blocked: Sequence[EvaluationItem],
    reports: Sequence[ReportRow],
    documents: Sequence[DocumentRow],
    retrievals: Sequence[RetrievalRow],
) -> dict[tuple[str, str], tuple[_Ground, ...]]:
    """예측마다 근거 문서를 모은다."""
    revised_by_url = {
        _canonical(doc.source_url): _known_revision(doc) for doc in documents
    }
    retrievals_by_key: dict[tuple[str, str], list[RetrievalRow]] = {}
    for record in retrievals:
        retrievals_by_key.setdefault((record.event_slug, record.match_key), []).append(
            record
        )

    sources_by_key: dict[tuple[str, str], list[str]] = {}
    for report in reports:
        sources_by_key.setdefault((report.event_slug, report.match_key), []).extend(
            report.sources
        )

    grounds: dict[tuple[str, str], tuple[_Ground, ...]] = {}
    for item in blocked:
        key = _key(item)
        found: dict[str, _Ground] = {}
        for record in retrievals_by_key.get(key, []):
            if not record.source_url:
                continue
            url = _canonical(record.source_url)
            previous = found.get(url)
            # 같은 문서의 청크가 여럿이면 **가장 늦은** 개정본을 남긴다 — 판정이
            # 최악을 기준으로 잡는 것과 같은 선택이다.
            if previous is None or _later(
                record.source_revised_at, previous.revised_at
            ):
                found[url] = _Ground(url, record.source_revised_at, False, True)
        for raw in sources_by_key.get(key, []):
            url = _canonical(raw)
            previous = found.get(url)
            if previous is not None:
                found[url] = dataclasses.replace(previous, in_sources=True)
                continue
            found[url] = _Ground(url, revised_by_url.get(url), True, False)
        grounds[key] = tuple(found.values())
    return grounds


def _known_revision(doc: DocumentRow) -> datetime | None:
    """`_corpus`가 그 문서에 대해 아는 개정본 시각.

    **계보가 불완전하면 모르는 것으로 읽는다.** 판정이 그렇게 하기 때문이다 —
    청크 하나라도 시각이 비면 검색이 하필 그 청크를 골랐을 수 있다.
    """
    provenance = DocumentProvenance(
        chunks=doc.chunks,
        chunks_with_revision=doc.chunks_with_revision,
        latest_revised_at=doc.latest_revised_at,
        last_collected_at=doc.last_collected_at,
    )
    return provenance.latest_revised_at if provenance.is_complete else None


def _contributions(
    row: PredictionRow, grounds: Sequence[_Ground]
) -> dict[str, tuple[str, ...]]:
    """문서마다 **어떤 규칙을 실패시켰는지** 읽는다. 재판정이 아니다.

    규칙이 쓰는 함수를 그대로 부른다 — 여기서 비교를 따로 적으면 언젠가 한쪽만
    바뀌어 그래프가 판정과 다른 이야기를 한다.
    """
    # 코퍼스 규칙이 어느 쪽을 보는가. 기록이 하나라도 있으면 기록이 이긴다.
    uses_retrievals = any(ground.in_retrievals for ground in grounds)

    result: dict[str, tuple[str, ...]] = {}
    for ground in grounds:
        codes: list[str] = []
        # 자기참조는 **언제나 인용 출처**를 본다(`_self_reference`).
        if ground.in_sources and cites_own_event((ground.url,), row.event_label):
            codes.append("self_reference")
        if (ground.in_retrievals if uses_retrievals else ground.in_sources) and (
            _temporal_position(ground.revised_at, row.event_start_date)
            != EVIDENCE_BEFORE_EVENT
        ):
            codes.append("unverifiable_corpus")
        # 이 규칙은 **기록이 있을 때만** 묻는다. 없는 예측에 붙이면 판정에 없는
        # 말을 만드는 것이 된다.
        if (
            ground.in_retrievals
            and _revision_position(ground.revised_at, row.generated_at)
            == REVISION_AFTER_PREDICTION
        ):
            codes.append("revision_after_prediction")
        if codes:
            result[ground.url] = _ordered_codes(set(codes))
    return result


def _edge(
    item: EvaluationItem,
    codes: tuple[str, ...],
    grounds: Sequence[_Ground],
    recovered: set[tuple[str, str]],
) -> LeakageEdge:
    sole_evidence = len(grounds) == 1
    return LeakageEdge(
        event_slug=item.event_slug,
        event_label=item.event_label,
        match_key=item.match_key,
        match_title=item.match_title,
        status=item.status,
        codes=codes,
        # 근거가 그 문서 하나뿐이었으면 통과를 단독 원인으로 세지 않는다 —
        # 그것은 "근거가 사라져서 통과"이지 "이 문서가 혼자 막았다"가 아니다.
        sole_cause=_key(item) in recovered and not sole_evidence,
        sole_evidence=sole_evidence,
    )


def _recovered_without(
    url: str,
    rows: Sequence[PredictionRow],
    reports: Sequence[ReportRow],
    documents: Sequence[DocumentRow],
    retrievals: Sequence[RetrievalRow],
) -> set[tuple[str, str]]:
    """그 문서를 뺀 입력으로 **같은 판정**을 다시 돌려 자격을 얻는 예측을 고른다.

    다른 규칙이 아니라 다른 입력이다. 그래서 여기서 나온 답은 "규칙을 느슨하게 하면
    통과한다"가 아니라 "이 문서가 없었다면 통과했다"다.
    """
    kept_reports = [
        dataclasses.replace(
            report,
            sources=tuple(s for s in report.sources if _canonical(s) != url),
        )
        for report in reports
    ]
    kept_retrievals = [
        record for record in retrievals if _canonical(record.source_url or "") != url
    ]
    kept_documents = [doc for doc in documents if _canonical(doc.source_url) != url]

    _, _, items, _ = summarize_evaluation(
        rows, kept_reports, kept_documents, kept_retrievals
    )
    return {_key(item) for item in items if item.status == STATUS_ELIGIBLE}


def _ordered_codes(codes: set[str]) -> tuple[str, ...]:
    """규칙 순서를 지킨다 — 집합의 순서에 화면이 흔들리지 않게."""
    return tuple(code for code in DOCUMENT_RULES if code in codes)


def _key(item: EvaluationItem) -> tuple[str, str]:
    return (item.event_slug, item.match_key)


def _later(candidate: datetime | None, current: datetime | None) -> bool:
    """`None`은 "모른다"이므로 비교에서 이기지 못한다 — 아는 값을 지우지 않는다.

    표시대(tz)를 맞춰 비교한다. PG는 aware를, SQLite는 naive를 돌려주므로 섞이면
    `TypeError`로 죽는다 — 판정 쪽이 `_to_utc`로 막은 것과 같은 자리다.
    """
    if candidate is None:
        return False
    return current is None or _to_utc(candidate) > _to_utc(current)


def _domain_of(url: str) -> str:
    """코퍼스에 없는 출처의 도메인. 문서 행이 없으면 URL에서 읽는다."""
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]
