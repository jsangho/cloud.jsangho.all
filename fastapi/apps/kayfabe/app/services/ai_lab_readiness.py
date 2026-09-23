"""코퍼스 준비도 — 다음 예측이 자격을 얻을 수 있는가 (Phase 8). **순수 함수다.**

AI LAB의 화면 여섯은 전부 **뒤를 본다**. 무엇을 예측했고(3-2), 누가 맞혔고(3-3),
무엇을 읽었고(3-4), 무엇이 막혔고(3-6), 어느 문서가 막았는가(10). 그런데 그 화면들이
모두 같은 결론에 닿는다 — **예측을 만들기 전에 코퍼스를 손봤어야 했다.** 누수는
판정에서 생기지 않고 수집에서 생긴다.

그 손보는 일이 지금까지 **화면 없이** 돌아갔다. 2026-09-22에 MITB 대회 문서 7청크를
손으로 찾아 걷어낸 것이 그 일이고, 아무도 그것을 다시 확인할 수 없다. 이 모듈이
그 작업을 화면으로 만든다 — **아직 열리지 않은 대회마다, 지금 코퍼스에 그 대회를
막을 문서가 있는가.**

**앞서 볼 수 있는 규칙은 둘뿐이다.**

* `self_reference` — 코퍼스에 **그 대회 자체를 다룬 문서**가 있으면, 그것이 검색에
  걸리는 순간 예측이 아니라 열람이 된다. 대회마다 다른 문제다.
* `unverifiable_corpus` — 계보가 불완전한 문서는 "경기보다 앞선 글"임을 증명할 수
  없어 보류를 만든다. **대회와 무관한 문서의 성질이다**(아래).

`revision_after_prediction`은 앞서 물을 수 없다. 그 규칙은 개정본과 **예측 생성
시각**을 견주는데 예측이 아직 없으므로 견줄 상대가 없다. 없는 것을 있는 척 세우지
않는다.

**지뢰는 "검색되면 막는다"이지 "반드시 검색된다"가 아니다.** 여기서 검색을 돌리지
않으므로(다른 AI LAB 화면과 같은 규칙, §3-D1) 어떤 청크가 실제로 뽑힐지는 모른다.
그래서 이 화면은 **과대평가 쪽으로 틀린다** — 지뢰를 세워 놓고 안 밟을 수 있다.
반대 방향으로 틀리는 것보다 낫다: 못 본 지뢰는 자격을 앗아가고, 헛본 지뢰는
문서 하나를 덜 수집하게 할 뿐이다.

**판정하지 않는다.** 여기 나오는 것은 상태가 아니라 **위험**이다. 자격 판정은 예측이
생긴 뒤에 `summarize_evaluation`이 한다 — 그 자리를 이 화면이 미리 차지하면, 아직
존재하지도 않는 예측에 대해 두 곳이 서로 다른 말을 하게 된다. 값 이름에 `_risk`가
붙어 있는 이유다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from kayfabe.app.services.ai_lab_evaluation import (
    EVIDENCE_BEFORE_EVENT,
    DocumentProvenance,
    _temporal_position,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, cites_own_event

# 3-4·3-6·10이 문서 대조에 쓰는 것과 **같은 정규화**를 쓴다. 여기서 따로 만들면
# 네 화면이 서로 다른 문서를 같은 문서라고 말하게 된다.
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

#: 이 화면이 앞서 볼 수 있는 규칙 둘. **`revision_after_prediction`은 못 본다**
#: (견줄 예측 시각이 아직 없다).
FORESEEABLE_RULES = ("self_reference", "unverifiable_corpus")

#: 대회 하나의 위험도. **판정이 아니라 위험이다** — 아직 예측이 없다.
RISK_CLEAR = "clear"
RISK_HOLD = "hold_risk"
RISK_DISQUALIFY = "disqualify_risk"


@dataclass(frozen=True)
class EventRow:
    """대회 하나. 리포지토리가 읽어 주는 값 그대로 담는다.

    `status`를 싣되 **판정에 쓰지 않는다**. 지난 대회를 닫는 일은 사람이
    `close_past_events.py`를 돌려서 하므로 그 칸은 드리프트한다 — 날짜가 사실이고
    상태는 사람의 기록이다. 화면에 함께 세워 어긋남이 보이게만 한다.
    """

    slug: str
    label: str
    start_date: date | None
    status: str
    #: 지금 카드에 있는 경기 수. 예측 커버리지의 분모다.
    matches: int


@dataclass(frozen=True)
class ReadinessMine:
    """그 대회를 막을 문서 하나. **`self_reference` 지뢰만 여기 온다.**"""

    source_url: str
    source_domain: str
    title: str | None
    chunks: int
    #: 계보를 아는 청크 수. `chunks`보다 작으면 시간 확인도 함께 막힌다.
    chunks_with_revision: int


@dataclass(frozen=True)
class ReadinessEvent:
    """아직 열리지 않은 대회 하나와 그 앞에 놓인 위험."""

    slug: str
    label: str
    start_date: date
    #: 대회 행에 적힌 상태. **위험도와 무관하다** (`EventRow.status` 주석 참조).
    status: str
    days_until: int
    matches: int
    #: 이미 예측이 만들어진 경기 수. **자격은 보지 않는다** — 그건 평가 화면 몫이다.
    predicted: int
    #: 이 대회 자체를 다룬 문서들. 비어 있으면 자기참조 위험이 없다.
    mines: tuple[ReadinessMine, ...]
    #: 이 대회 날짜 기준으로 **시간을 확인할 수 없는** 문서 수. 규칙이 쓰는 같은
    #: 비교(`_temporal_position`)를 문서마다 돌려 센다.
    #:
    #: 목록이 아니라 수인 이유: 이 값은 대회가 아니라 **문서의 성질**이라 대회마다
    #: 같은 목록이 반복된다(아직 안 열린 대회라 개정본은 전부 그 날짜보다 앞선다 —
    #: 남는 실패 방식은 "개정본 시각을 모른다" 하나뿐이다). 목록으로 실으면 화면이
    #: 대회마다 다른 문제인 척하게 된다. 문서 목록은 코퍼스 칸에 한 번 선다.
    unverifiable_documents: int
    #: `RISK_*` 셋 중 하나.
    risk: str


@dataclass(frozen=True)
class ReadinessCorpus:
    """대회와 무관한 코퍼스 자체의 상태."""

    documents: int
    #: 계보가 불완전한 문서 수. **어느 대회를 예측하든** 인용되면 보류를 만든다.
    incomplete_lineage: int
    #: 청크가 하나도 임베딩되지 않은 문서 수.
    #:
    #: **지뢰가 아니라 없는 것이다** — 검색에 안 잡히므로 근거도 못 되고 누수도
    #: 못 만든다. 코퍼스가 보이는 것보다 작다는 사실로만 센다.
    unembedded_documents: int


@dataclass(frozen=True)
class ReadinessTotals:
    """**합이 맞아야 한다**: `events == clear + hold_risk + disqualify_risk`."""

    #: 날짜가 오늘 이후인 대회 수. 아래 셋의 합과 같다.
    events: int
    clear: int
    hold_risk: int
    disqualify_risk: int
    #: 날짜가 없어 앞에 있는지조차 모르는 대회 수. **0이 아니면 이 화면이 그만큼
    #: 못 보고 있다는 뜻이다** — 빼고 세면 목록이 전부인 척한다.
    undated_events: int
    matches: int
    predicted_matches: int
    #: 지뢰로 잡힌 문서 수(대회를 가로질러 중복 없이).
    mine_documents: int


def summarize_readiness(
    events: Sequence[EventRow],
    documents: Sequence[DocumentRow],
    predictions: Sequence[PredictionRow],
    *,
    as_of: date,
) -> tuple[ReadinessTotals, ReadinessCorpus, list[ReadinessEvent]]:
    """아직 열리지 않은 대회마다 지금 코퍼스가 무엇을 막을지 읽는다.

    `as_of`를 인자로 받는 이유는 "오늘"이 판정의 입력이기 때문이다. 함수 안에서
    시계를 읽으면 같은 데이터가 날짜에 따라 다른 답을 내는데 그것을 시험할 수 없다.
    """
    predicted_by_event = _predicted_by_event(predictions)
    upcoming = [
        row for row in events if row.start_date is not None and row.start_date >= as_of
    ]

    items = [
        _event(
            row,
            # 위에서 걸러 냈으므로 날짜가 있다. 값을 여기서 꺼내 넘기는 것은
            # `_event`가 "날짜를 아는 대회"만 다룬다는 것을 시그니처로 말하기 위해서다.
            start_date=row.start_date,
            documents=documents,
            predicted=predicted_by_event.get(row.slug, 0),
            as_of=as_of,
        )
        for row in upcoming
        if row.start_date is not None
    ]
    # 가까운 대회가 위로. 같은 날이면 슬러그 순 — 재조회에도 순서가 안 흔들린다.
    items.sort(key=lambda item: (item.start_date, item.slug))

    totals = ReadinessTotals(
        events=len(items),
        clear=sum(1 for item in items if item.risk == RISK_CLEAR),
        hold_risk=sum(1 for item in items if item.risk == RISK_HOLD),
        disqualify_risk=sum(1 for item in items if item.risk == RISK_DISQUALIFY),
        undated_events=sum(1 for row in events if row.start_date is None),
        matches=sum(item.matches for item in items),
        predicted_matches=sum(item.predicted for item in items),
        mine_documents=len(
            {mine.source_url for item in items for mine in item.mines},
        ),
    )
    return totals, _corpus(documents), items


def _event(
    row: EventRow,
    *,
    start_date: date,
    documents: Sequence[DocumentRow],
    predicted: int,
    as_of: date,
) -> ReadinessEvent:
    """대회 하나. **규칙이 쓰는 함수를 그대로 부른다.**

    비교를 여기서 따로 적으면 언젠가 한쪽만 바뀌어, 이 화면이 "괜찮다"고 한 대회를
    판정이 막게 된다.
    """
    mines = tuple(
        ReadinessMine(
            source_url=doc.source_url,
            source_domain=doc.source_domain,
            title=doc.title,
            chunks=doc.chunks,
            chunks_with_revision=doc.chunks_with_revision,
        )
        for doc in documents
        # **임베딩 유무를 보지 않는다.** 임베딩이 없는 문서는 지금 검색에 안 잡히지만
        # 임베딩은 나중에 채워지고 그때 그 문서는 되살아난다. 여기서 묻는 것은
        # "지금 뽑히는가"가 아니라 **"코퍼스에 있는가"** 다 — 조치도 그쪽이다(뺀다).
        if cites_own_event((doc.source_url,), row.label)
    )
    unverifiable = sum(
        1
        for doc in documents
        if _temporal_position(_known_revision(doc), start_date) != EVIDENCE_BEFORE_EVENT
    )

    return ReadinessEvent(
        slug=row.slug,
        label=row.label,
        start_date=start_date,
        status=row.status,
        days_until=(start_date - as_of).days,
        matches=row.matches,
        predicted=predicted,
        # 많은 청크를 가진 문서가 위로. 같으면 URL 순 — 목록 순서가 안 흔들린다.
        mines=tuple(sorted(mines, key=lambda m: (-m.chunks, m.source_url))),
        unverifiable_documents=unverifiable,
        # **자기참조가 이긴다.** 그쪽은 실격이고 이쪽은 보류라, 둘 다일 때 더 무거운
        # 쪽을 말하지 않으면 화면이 위험을 낮춰 보고한다(규칙의 적용 순서와 같다).
        risk=(
            RISK_DISQUALIFY if mines else (RISK_HOLD if unverifiable else RISK_CLEAR)
        ),
    )


def _corpus(documents: Sequence[DocumentRow]) -> ReadinessCorpus:
    return ReadinessCorpus(
        documents=len(documents),
        incomplete_lineage=sum(1 for doc in documents if _known_revision(doc) is None),
        unembedded_documents=sum(1 for doc in documents if doc.chunks_embedded <= 0),
    )


def _known_revision(doc: DocumentRow) -> datetime | None:
    """`_corpus`가 그 문서에 대해 아는 개정본 시각. 계보가 불완전하면 `None`이다.

    Phase 10과 **같은 읽기**다 — 판정이 부분 계보를 통과로 접지 않으므로 여기서도
    접지 않는다. 두 화면이 같은 문서를 두고 다른 말을 하면 안 된다.
    """
    provenance = DocumentProvenance(
        chunks=doc.chunks,
        chunks_with_revision=doc.chunks_with_revision,
        latest_revised_at=doc.latest_revised_at,
        last_collected_at=doc.last_collected_at,
    )
    return provenance.latest_revised_at if provenance.is_complete else None


def _predicted_by_event(predictions: Sequence[PredictionRow]) -> dict[str, int]:
    """대회마다 **예측이 있는 경기 수**. 같은 경기의 예측은 하나로 센다."""
    keys: dict[str, set[str]] = {}
    for row in predictions:
        keys.setdefault(row.event_slug, set()).add(row.match_key)
    return {slug: len(matches) for slug, matches in keys.items()}
