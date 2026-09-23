"""예측 단건 감사 (Phase 9).

**이 화면이 지키는 것은 일관성이다.** 목록이 "실격"이라고 한 예측을 감사 화면이
"보류"라고 하면, 그 순간 이 시스템은 감사 도구가 아니라 두 개의 의견이 된다.
그래서 여기서 붙드는 계약은 다섯이다.

1. **판정을 다시 하지 않는다** — 목록(`get_evaluation`)과 같은 계산에서 뽑는다.
2. **증거의 역할은 규칙 엔진이 낸다** — LLM에게 설명시키지 않는다. `temporal`과
   `self_reference`는 판정이 쓴 것과 같은 함수를 지난다.
3. **읽은 순서를 지킨다** — 순서가 곧 "무엇을 먼저 읽었는가"다.
4. **없는 것을 만들지 않는다** — 기록 없는 옛 예측은 증거가 빈 채로 나가고,
   Phase 4 이전 리포트는 판 식별자가 `None`으로 나간다.
5. **모델 이름은 나가지 않는다**(하네스 §11-6).

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \\
        apps/kayfabe/tests/app/use_cases/test_prediction_audit.py -q
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime

import pytest

from kayfabe.app.dtos.agent_prediction_dto import MatchOption
from kayfabe.app.dtos.ai_lab_dto import AuditReport
from kayfabe.app.ports.output.ai_lab_repository import AiLabRepository
from kayfabe.app.services.ai_lab_evaluation import (
    EVIDENCE_BEFORE_EVENT,
    EVIDENCE_NOT_BEFORE_EVENT,
    EVIDENCE_UNKNOWN_EVENT_DATE,
    EVIDENCE_UNKNOWN_REVISION,
    RetrievalRow,
    explain_evidence,
)
from kayfabe.app.services.ai_lab_integrity import (
    CorpusFacts,
    PredictionRow,
    ReportRow,
)
from kayfabe.app.services.ai_lab_knowledge import DocumentRow
from kayfabe.app.services.ai_lab_replay import REPLAY_STAGES, ReplayStatus
from kayfabe.app.use_cases.ai_lab_interactor import AiLabInteractor

_SLUG = "summerslam"
_LABEL = "SummerSlam"
_MATCH = "ss26-n1-undisputed"

_EVENT_DAY = date(2026, 8, 10)
_GENERATED_AT = datetime(2026, 8, 9, 7, tzinfo=UTC)
_RESULT_AT = datetime(2026, 8, 11, 7, tzinfo=UTC)
_BEFORE = datetime(2026, 8, 1, 7, tzinfo=UTC)
_AFTER = datetime(2026, 8, 14, 7, tzinfo=UTC)

_DOC = "https://en.wikipedia.org/wiki/Cody_Rhodes"
_OWN = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"

#: 그 경기의 **지금 카드** 선택지 (Phase 5). 재현이 여기서 선택지를 읽는다.
_OPTIONS = (
    MatchOption(pick="left", name="Cody Rhodes"),
    MatchOption(pick="right", name="Gunther"),
)


def _prediction(**overrides) -> PredictionRow:
    base = PredictionRow(
        event_slug=_SLUG,
        event_label=_LABEL,
        match_key=_MATCH,
        match_title="Undisputed Championship",
        pick="left",
        pick_name="Cody Rhodes",
        win_probability=0.7,
        confidence=0.6,
        rationale="2/3 분석이 Cody Rhodes을(를) 골랐습니다.",
        source="agents",
        generated_at=_GENERATED_AT,
        winner_pick="left",
        winner_name="Cody Rhodes",
        finished_at=_RESULT_AT,
        event_start_date=_EVENT_DAY,
    )
    return dataclasses.replace(base, **overrides)


def _report(**overrides) -> ReportRow:
    base = ReportRow(
        event_slug=_SLUG,
        match_key=_MATCH,
        agent="storyline",
        pick="left",
        weight=0.8,
        summary="명분이 도전자 쪽에 있다.",
        sources=(_DOC,),
        agent_version="storyline@1",
        prompt_version="f9b754e8b82ddb96",
    )
    return dataclasses.replace(base, **overrides)


def _document(url: str = _DOC, *, revised_at: datetime | None = _BEFORE) -> DocumentRow:
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title=None,
        chunks=3,
        chunks_embedded=3,
        chunks_with_published_at=0,
        first_published_at=None,
        last_collected_at=_AFTER,
        chunks_with_revision=3 if revised_at else 0,
        latest_revised_at=revised_at,
    )


def _retrieval(rank: int, *, url: str = _DOC, revised_at=_BEFORE) -> RetrievalRow:
    return RetrievalRow(
        event_slug=_SLUG,
        match_key=_MATCH,
        source_url=url,
        source_revised_at=revised_at,
        rank=rank,
        source_revision_id=f"136777{rank}",
        published_at=None,
        distance=0.1 * rank,
    )


class FakeRepository(AiLabRepository):
    def __init__(
        self,
        *,
        predictions=None,
        reports=None,
        documents=None,
        retrievals=None,
        options=None,
    ) -> None:
        self._predictions = predictions if predictions is not None else [_prediction()]
        self._reports = reports if reports is not None else [_report()]
        self._documents = documents if documents is not None else [_document()]
        self._retrievals = retrievals or []
        self._options = _OPTIONS if options is None else options

    async def list_predictions(self) -> list[PredictionRow]:
        return self._predictions

    async def list_reports(self) -> list[ReportRow]:
        return self._reports

    async def corpus_facts(self) -> CorpusFacts:
        return CorpusFacts(0, 0, 0, 0, 0, 0, None)

    async def list_documents(self) -> list[DocumentRow]:
        return self._documents

    async def list_retrievals(self) -> list[RetrievalRow]:
        return self._retrievals

    async def count_events(self) -> int:
        return 11

    async def list_events(self):
        # 감사 화면은 대회 목록을 읽지 않는다 (Phase 8은 준비도 화면만 쓴다).
        return []

    async def load_match_options(self, *, event_slug: str, match_key: str):
        return self._options


async def _audit(repository: FakeRepository):
    return await AiLabInteractor(repository).get_audit(
        event_slug=_SLUG, match_key=_MATCH
    )


# ---------------------------------------------------------------------------
# 1. 판정을 다시 하지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_and_list_agree_on_the_verdict() -> None:
    """**같은 예측을 두고 두 화면이 다른 말을 할 수 없다.**

    감사 화면이 한 건만 따로 판정하면, 코퍼스가 전역이라는 사실을 놓치기 쉽다 —
    인용 문서의 계보는 URL 단위라 한 예측만 떼어 내면 알 수 없는 값이 생긴다.
    """
    repository = FakeRepository()
    interactor = AiLabInteractor(repository)

    audit = await interactor.get_audit(event_slug=_SLUG, match_key=_MATCH)
    listing = await interactor.get_evaluation()

    assert audit is not None
    expected = next(
        i for i in listing.items if (i.event_slug, i.match_key) == (_SLUG, _MATCH)
    )
    assert audit.evaluation == expected


@pytest.mark.asyncio
async def test_missing_prediction_is_none_not_an_exception() -> None:
    """없음은 예외가 아니다 — HTTP 상태로 옮기는 것은 라우터의 일이다(§4-6)."""
    result = await AiLabInteractor(FakeRepository()).get_audit(
        event_slug=_SLUG, match_key="없는-경기"
    )

    assert result is None


@pytest.mark.asyncio
async def test_rules_carry_their_definitions() -> None:
    """화면이 문구를 지어내지 않도록 규칙 정의를 서버가 낸다."""
    audit = await _audit(FakeRepository())

    assert audit is not None
    codes = {rule.code for rule in audit.rules}
    assert "self_reference" in codes
    assert all(rule.description for rule in audit.rules)
    # 무게가 셋으로 갈린 채로 나간다 — 화면이 실격과 보류를 같은 색으로 칠하지 않게.
    assert {rule.severity for rule in audit.rules} == {
        "exclude",
        "disqualify",
        "hold",
    }


# ---------------------------------------------------------------------------
# 2·3. 증거의 역할은 규칙 엔진이 내고, 읽은 순서를 지킨다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_keeps_the_reading_order() -> None:
    repository = FakeRepository(
        # 일부러 뒤섞어 넣는다 — 저장 순서가 아니라 `rank`가 순서를 정해야 한다.
        retrievals=[_retrieval(3), _retrieval(1), _retrieval(2)],
    )

    audit = await _audit(repository)

    assert audit is not None
    assert [e.rank for e in audit.evidence] == [1, 2, 3]
    assert [e.source_revision_id for e in audit.evidence] == [
        "1367771",
        "1367772",
        "1367773",
    ]


@pytest.mark.asyncio
async def test_evidence_is_empty_for_predictions_without_a_record() -> None:
    """**빈 것이 정직한 상태다.**

    Stage 4 이전 예측에는 검색 기록이 없다. 지금 코퍼스에서 다시 검색해 채우면
    "그때 읽은 것"이 아니라 "지금 검색되는 것"을 적는 것이 된다.
    """
    audit = await _audit(FakeRepository(retrievals=[]))

    assert audit is not None
    assert audit.evidence == ()


@pytest.mark.asyncio
async def test_self_referencing_evidence_is_marked() -> None:
    """실격의 **근거가 어느 조각인지** 짚을 수 있어야 한다 (Phase 6)."""
    repository = FakeRepository(
        reports=[_report(sources=(_DOC, _OWN))],
        documents=[_document(), _document(_OWN)],
        retrievals=[_retrieval(1), _retrieval(2, url=_OWN)],
    )

    audit = await _audit(repository)

    assert audit is not None
    assert audit.evaluation.status == "disqualified"
    assert [e.self_reference for e in audit.evidence] == [False, True]
    # 규칙 엔진이 낸 판정과 증거 표시가 같은 이야기를 한다.
    self_ref = next(v for v in audit.evaluation.verdicts if v.code == "self_reference")
    assert self_ref.failed is True


def test_evidence_temporal_positions_cover_the_four_cases() -> None:
    """`explain_evidence`는 **판정과 같은 함수**를 지난다. 넷을 한자리에서 고정한다."""
    rows = (
        _retrieval(1, revised_at=_BEFORE),
        _retrieval(2, revised_at=_AFTER),
        _retrieval(3, revised_at=None),
    )

    verdicts = explain_evidence(
        rows,
        event_label=_LABEL,
        event_start_date=_EVENT_DAY,
        generated_at=_GENERATED_AT,
    )
    assert [v.temporal for v in verdicts] == [
        EVIDENCE_BEFORE_EVENT,
        EVIDENCE_NOT_BEFORE_EVENT,
        EVIDENCE_UNKNOWN_REVISION,
    ]

    # 대회 날짜를 모르면 비교 자체가 불가능하다 — 개정본 시각이 있어도 그렇다.
    blind = explain_evidence(
        rows,
        event_label=_LABEL,
        event_start_date=None,
        generated_at=_GENERATED_AT,
    )
    assert {v.temporal for v in blind} == {EVIDENCE_UNKNOWN_EVENT_DATE}


def test_event_day_revision_is_not_before_the_event() -> None:
    """**경계값.** 같은 날은 앞선 것이 아니다 — 판정과 화면이 함께 지켜야 한다."""
    [verdict] = explain_evidence(
        (_retrieval(1, revised_at=datetime(2026, 8, 10, 3, tzinfo=UTC)),),
        event_label=_LABEL,
        event_start_date=_EVENT_DAY,
        generated_at=_GENERATED_AT,
    )

    assert verdict.temporal == EVIDENCE_NOT_BEFORE_EVENT


def test_evidence_without_a_url_is_not_called_self_reference() -> None:
    """출처가 없으면 대조할 것이 없다. **모름을 자기참조라고 하지 않는다.**"""
    [verdict] = explain_evidence(
        (
            RetrievalRow(
                event_slug=_SLUG,
                match_key=_MATCH,
                source_url=None,
                source_revised_at=_BEFORE,
                rank=1,
            ),
        ),
        event_label=_LABEL,
        event_start_date=_EVENT_DAY,
        generated_at=_GENERATED_AT,
    )

    assert verdict.self_reference is False


# ---------------------------------------------------------------------------
# 4·5. 없는 것을 만들지 않고, 모델 이름을 내보내지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_versions_ride_along() -> None:
    """Phase 4가 남긴 판 식별자가 화면까지 온다."""
    audit = await _audit(FakeRepository())

    assert audit is not None
    [report] = audit.reports
    assert report.agent_version == "storyline@1"
    assert report.prompt_version == "f9b754e8b82ddb96"


@pytest.mark.asyncio
async def test_legacy_reports_show_no_version() -> None:
    """**백필하지 않았다.** 기록이 없는 리포트는 빈 채로 나간다."""
    audit = await _audit(
        FakeRepository(reports=[_report(agent_version=None, prompt_version=None)])
    )

    assert audit is not None
    [report] = audit.reports
    assert report.agent_version is None
    assert report.prompt_version is None


def test_audit_report_carries_no_model_name() -> None:
    """**경계가 §11-6을 지킨다.**

    모델 이름은 `ple_agent_reports.model_version`에 남아 있지만 이 타입에 자리가
    없어서 응답으로 나갈 수 없다. 규율이 아니라 타입이 막는다.
    """
    fields = {field.name for field in dataclasses.fields(AuditReport)}

    assert "model" not in fields
    assert "model_version" not in fields
    assert fields == {
        "agent",
        "pick",
        "weight",
        "summary",
        "sources",
        "agent_version",
        "prompt_version",
    }


@pytest.mark.asyncio
async def test_only_this_matchs_reports_and_evidence_are_included() -> None:
    """옆 경기의 근거가 섞이면 감사 기록이 통째로 거짓이 된다."""
    other = "ss26-n2-whc"
    repository = FakeRepository(
        predictions=[_prediction(), _prediction(match_key=other)],
        reports=[_report(), _report(match_key=other, agent="rumor")],
        retrievals=[
            _retrieval(1),
            dataclasses.replace(_retrieval(1), match_key=other),
        ],
    )

    audit = await _audit(repository)

    assert audit is not None
    assert [r.agent for r in audit.reports] == ["storyline"]
    assert len(audit.evidence) == 1


# ---------------------------------------------------------------------------
# 6. 재현은 계보 옆에 붙지만 판정을 건드리지 않는다 (Phase 5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_audit_carries_a_replay_of_the_synthesis() -> None:
    """감사 응답에 **저장된 재료로 다시 돌린 결과**가 함께 실린다."""
    audit = await _audit(FakeRepository())

    assert audit is not None
    assert audit.replay.status in {
        ReplayStatus.REPRODUCED,
        ReplayStatus.DIVERGED,
        ReplayStatus.UNREPLAYABLE,
    }
    assert audit.replay.stages == REPLAY_STAGES


@pytest.mark.asyncio
async def test_a_vanished_card_leaves_the_replay_empty_but_the_verdict_intact() -> None:
    """**재현이 판정을 인질로 잡지 않는다.**

    카드가 사라지면 다시 돌릴 재료가 없지만, 그 예측의 자격 판정은 코퍼스와 시각이
    정하는 것이라 한 칸도 움직이지 않는다.
    """
    with_card = await _audit(FakeRepository(retrievals=[_retrieval(1)]))
    without = await _audit(FakeRepository(retrievals=[_retrieval(1)], options=()))

    assert with_card is not None and without is not None
    assert without.replay.status is ReplayStatus.UNREPLAYABLE
    assert without.evaluation == with_card.evaluation


@pytest.mark.asyncio
async def test_the_replay_reads_the_same_reports_the_screen_shows() -> None:
    """화면에 세운 리포트와 **다른 목록**으로 재현하면 그 결과는 설명이 되지 않는다."""
    other = "ss26-n2-whc"
    repository = FakeRepository(
        predictions=[_prediction(), _prediction(match_key=other)],
        reports=[
            _report(),
            _report(match_key=other, agent="rumor", pick="right", weight=0.9),
        ],
    )

    audit = await _audit(repository)

    assert audit is not None
    # 옆 경기의 의견이 섞였다면 pick이 뒤집혀 다른 재현 결과가 나온다.
    assert [r.agent for r in audit.reports] == ["storyline"]
    assert all(item.field != "pick" for item in audit.replay.mismatches)
