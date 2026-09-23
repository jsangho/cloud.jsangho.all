"""자격 판정 골든 세트 (Phase 11) — **회귀 방어선이다.**

기존 `test_ai_lab_evaluation.py`와 목적이 다르다. 그쪽은 규칙 하나하나가 **왜 그렇게
동작하는지**를 설명하며 검증한다. 여기서는 설명하지 않는다. **입력 → 규칙 → 무게 →
최종 상태**를 한 표에 못 박아 두고, 판정 엔진을 고칠 때 그 표가 먼저 깨지게 한다.

그래서 이 파일이 지키는 규율 셋:

1. **운영 데이터를 읽지 않는다.** 모든 입력이 이 파일 안에 있다. 코퍼스를 재수집하든
   예측을 다시 만들든 이 표의 의미는 움직이지 않는다 — 움직이면 회귀 테스트가 아니라
   현황 보고서다.
2. **기대값을 문자열 리터럴로 적는다.** `STATUS_HELD` 같은 상수를 쓰면 상수의 *값*이
   바뀔 때 기대값도 같이 따라가 아무것도 못 잡는다. 골든은 코드를 **독립적으로 다시
   진술**해야 한다.
3. **깨지면 기대값을 고치지 않는다.** 무엇이 왜 바뀌었는지 먼저 적고, 판정의 의미가
   바뀐 것이 의도인지 확인한다. 숫자를 좋게 만들려고 표를 고치는 순간 이 파일은
   존재 이유를 잃는다.

**규칙을 추가하면 이 파일이 먼저 실패한다** (`test_every_rule_has_a_golden_case`).
여덟 번째 규칙을 들이면서 골든 케이스를 안 만드는 길을 막아 둔 것이다.

실행:

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps uv run pytest \
        apps/kayfabe/tests/app/services/test_eligibility_golden_set.py -q
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from kayfabe.app.services.ai_lab_evaluation import (
    RULES,
    RetrievalRow,
    summarize_evaluation,
)
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow
from kayfabe.app.services.ai_lab_knowledge import DocumentRow

# ---------------------------------------------------------------------------
# 고정 시각. **전부 이 파일 안에서만 뜻을 갖는다.**
# ---------------------------------------------------------------------------

#: 대회가 열린 날. 코퍼스 규칙이 개정본 시각과 비교하는 기준이다.
EVENT_DAY = date(2026, 8, 10)

#: 결과가 시스템에 기록된 시각.
RESULT_RECORDED_AT = datetime(2026, 8, 11, 7, tzinfo=UTC)

#: 결과 기록보다 **앞선** 생성 시각. 시간 규칙을 지난다.
BEFORE_RESULT = datetime(2026, 8, 9, 7, tzinfo=UTC)

#: 결과 기록보다 **뒤인** 생성 시각. 시간 규칙에 걸린다.
AFTER_RESULT = datetime(2026, 8, 12, 7, tzinfo=UTC)

#: 대회보다 앞선 개정본 — 결과가 적혀 있을 수 없다(충분조건).
REVISED_BEFORE_EVENT = datetime(2026, 8, 1, 7, tzinfo=UTC)

#: **대회 당일** 개정본. 경계값이다 — 같은 날은 통과가 아니다.
REVISED_ON_EVENT_DAY = datetime(2026, 8, 10, 3, tzinfo=UTC)

#: 대회 뒤 개정본. 결과가 실려 있을 수 있다.
REVISED_AFTER_EVENT = datetime(2026, 8, 14, 3, tzinfo=UTC)

COLLECTED_AT = datetime(2026, 8, 15, 7, tzinfo=UTC)

EVENT_SLUG = "summerslam"
EVENT_LABEL = "SummerSlam"

#: **그 대회 자체**를 다룬 문서. 결과가 적혀 있으므로 인용하면 실격이다.
OWN_EVENT_DOC = "https://en.wikipedia.org/wiki/SummerSlam_(2026)"


def _doc_url(match_key: str) -> str:
    """**케이스마다 다른 문서를 준다.** 공유하면 표가 거짓이 된다.

    문서 계보는 예측마다가 아니라 **URL마다 하나**다(`provenance_by_url`). 케이스
    여럿이 같은 URL을 쓰면 마지막에 들어간 문서가 나머지의 판정까지 결정한다 —
    실제로 이 파일을 처음 돌렸을 때 계보가 더러운 케이스 넷이 다른 케이스의 깨끗한
    문서를 얻어 통과해 버렸다. 판정 엔진이 틀린 게 아니라 코퍼스가 전역이라 그렇다.

    케이스별 판정만 재면 드러나지 않고 **한꺼번에 돌릴 때만** 드러나는 종류의
    간섭이라, 아예 겹칠 수 없게 키에서 URL을 만든다.
    """
    return f"https://en.wikipedia.org/wiki/Doc_{match_key}"


# ---------------------------------------------------------------------------
# 입력 조립기 — 기본값은 "아무 규칙에도 안 걸리는 깨끗한 예측"이다.
# 각 케이스는 **한 군데만** 어긋나게 해서 그 규칙만 재게 한다.
# ---------------------------------------------------------------------------


def _prediction(
    match_key: str,
    *,
    generated_at: datetime = BEFORE_RESULT,
    finished_at: datetime | None = RESULT_RECORDED_AT,
    winner_pick: str | None = "left",
    source: str = "agents",
    outcome_known_externally: bool | None = None,
    event_start_date: date | None = EVENT_DAY,
    match_exists: bool = True,
) -> PredictionRow:
    return PredictionRow(
        event_slug=EVENT_SLUG,
        event_label=EVENT_LABEL,
        match_key=match_key,
        match_title="World Heavyweight Championship",
        pick="left",
        pick_name="Cody Rhodes",
        win_probability=0.7,
        confidence=0.6,
        rationale="…",
        source=source,
        generated_at=generated_at,
        winner_pick=winner_pick,
        winner_name="Cody Rhodes",
        finished_at=finished_at,
        outcome_known_externally=outcome_known_externally,
        provenance_note=None,
        event_start_date=event_start_date,
        match_exists=match_exists,
    )


def _report(match_key: str, *, sources: tuple[str, ...] | None = None) -> ReportRow:
    return ReportRow(
        event_slug=EVENT_SLUG,
        match_key=match_key,
        agent="storyline",
        pick="left",
        weight=1.0,
        summary="…",
        sources=sources if sources is not None else (_doc_url(match_key),),
    )


def _document(
    url: str,
    *,
    chunks: int = 3,
    chunks_with_revision: int = 3,
    latest_revised_at: datetime | None = REVISED_BEFORE_EVENT,
) -> DocumentRow:
    """기본값은 **계보가 완전하고 경기보다 앞선** 문서다.

    `chunks_with_revision < chunks`면 계보가 불완전해진다 — 검색이 하필 개정본 시각이
    없는 청크를 골랐을 수 있으므로 부분 계보는 통과로 세지 않는다.
    """
    return DocumentRow(
        source_url=url,
        source_domain="en.wikipedia.org",
        title=None,
        chunks=chunks,
        chunks_embedded=chunks,
        chunks_with_published_at=0,
        first_published_at=None,
        last_collected_at=COLLECTED_AT,
        chunks_with_revision=chunks_with_revision,
        latest_revised_at=latest_revised_at,
    )


def _retrieval(
    match_key: str,
    *,
    source_revised_at: datetime | None = REVISED_BEFORE_EVENT,
) -> RetrievalRow:
    return RetrievalRow(
        event_slug=EVENT_SLUG,
        match_key=match_key,
        source_url=_doc_url(match_key),
        source_revised_at=source_revised_at,
    )


# ---------------------------------------------------------------------------
# 골든 테이블
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenCase:
    """케이스 하나. **입력과 기대값이 한자리에 있다.**"""

    name: str
    #: 이 케이스가 막는 회귀. 깨졌을 때 무엇을 잃는지 읽는 사람이 알아야 한다.
    guards: str
    prediction: PredictionRow
    #: 최종 상태. `ai_lab_evaluation`의 일곱 중 하나.
    expected_status: str
    #: 이 예측을 막은 규칙. 통과한 예측은 `None`이다.
    expected_rule: str | None
    #: 그 규칙의 무게. **실격과 보류는 다른 사실이다.**
    expected_severity: str | None
    reports: tuple[ReportRow, ...] = ()
    #: 비우면 **이 케이스 전용의 깨끗한 문서** 하나가 들어간다. 코퍼스 규칙을 재는
    #: 케이스만 여기를 채운다 — 나머지는 다른 규칙을 재고 있어서, 계보가 비면 재려던
    #: 것과 무관하게 전부 보류로 떨어진다.
    documents: tuple[DocumentRow, ...] | None = None
    retrievals: tuple[RetrievalRow, ...] = field(default_factory=tuple)

    @property
    def corpus(self) -> tuple[DocumentRow, ...]:
        if self.documents is not None:
            return self.documents
        return (_document(_doc_url(self.prediction.match_key)),)


GOLDEN_SET: tuple[GoldenCase, ...] = (
    # ---- 1. 통과 -----------------------------------------------------------
    GoldenCase(
        name="valid_ex_ante",
        guards=(
            "자격 판정이 **아무것도 통과시키지 못하게** 되는 회귀. 셋 다 지나는 "
            "입력이 하나는 있어야, 나머지 케이스의 '막혔다'가 뜻을 갖는다."
        ),
        prediction=_prediction("g01"),
        reports=(_report("g01"),),
        expected_status="eligible",
        expected_rule=None,
        expected_severity=None,
    ),
    GoldenCase(
        name="explicitly_declared_unknown_outcome_still_passes",
        guards=(
            "`outcome_known_externally`를 **값의 유무**로 보게 되는 회귀. "
            "`is True` 대신 `is not None`으로 쓰면 '몰랐다'를 `False`로 **명시한** "
            "표본까지 사후 재현으로 빨려 들어간다 — 정직하게 선언할수록 손해를 보는 "
            "판정이 되어 버린다. `None`(선언 없음)과 `False`(몰랐다고 선언)는 둘 다 "
            "정상 경로를 지나야 한다."
        ),
        prediction=_prediction("g02", outcome_known_externally=False),
        reports=(_report("g02"),),
        expected_status="eligible",
        expected_rule=None,
        expected_severity=None,
    ),
    # ---- 2. 실격 -----------------------------------------------------------
    GoldenCase(
        name="temporal_inversion",
        guards=(
            "결과가 기록된 **뒤에** 만들어진 예측이 분모에 남는 회귀. 정답을 볼 수 "
            "있는 상태에서 나온 값이라 예측 능력의 근거가 되지 못한다."
        ),
        prediction=_prediction("g03", generated_at=AFTER_RESULT),
        reports=(_report("g03"),),
        expected_status="disqualified",
        expected_rule="temporal_inversion",
        expected_severity="disqualify",
    ),
    GoldenCase(
        name="temporal_inversion_at_the_same_instant",
        guards=(
            "**같은 시각을 통과시키는** 회귀. `>=`를 `>`로 바꾸면 여기가 먼저 샌다 — "
            "같은 시각은 '먼저였다'고 말할 수 없다."
        ),
        prediction=_prediction("g04", generated_at=RESULT_RECORDED_AT),
        reports=(_report("g04"),),
        expected_status="disqualified",
        expected_rule="temporal_inversion",
        expected_severity="disqualify",
    ),
    GoldenCase(
        name="unmeasurable_rule_holds_it_does_not_disqualify",
        guards=(
            "**`applicable=False`를 통과로 접는** 회귀 — `_status_of`에서 "
            "`or not verdict.applicable`을 빼면 여기가 샌다. 결과는 기록됐는데 그 "
            "시각이 없는 행(옛 데이터)이라 '예측이 먼저였는가'를 **잴 수 없다.**\n"
            "\n"
            "그리고 반대쪽도 함께 못 박는다: 못 쟀다고 **실격은 아니다.** 규칙의 "
            "무게는 `disqualify`지만 최종 상태는 `held`다 — 확정된 누수와 못 잰 것은 "
            "다른 사실이고, 그 구분이 이 엔진의 핵심이다."
        ),
        prediction=_prediction("g18", finished_at=None, winner_pick="left"),
        reports=(_report("g18"),),
        expected_status="held",
        expected_rule="temporal_inversion",
        expected_severity="disqualify",
    ),
    GoldenCase(
        name="self_reference",
        guards=(
            "그 대회 자체를 다룬 문서를 인용하고도 통과하는 회귀. 대회 문서에는 "
            "경기 결과가 적혀 있으므로 예측이 아니라 **열람**일 수 있다."
        ),
        prediction=_prediction("g05"),
        reports=(_report("g05", sources=(OWN_EVENT_DOC,)),),
        # 인용 문서의 계보는 깨끗하게 둔다 — 여기서 재는 것은 자기참조뿐이다.
        documents=(_document(OWN_EVENT_DOC),),
        expected_status="disqualified",
        expected_rule="self_reference",
        expected_severity="disqualify",
    ),
    # ---- 3. 보류 (모르는 것을 통과로 접지 않는다) ---------------------------
    GoldenCase(
        name="unverifiable_corpus_unknown_revision",
        guards=(
            "개정본 시각을 **모르는** 문서를 통과시키는 회귀. 모르는 것을 과거로 "
            "간주하면 이 규칙이 하는 일이 없어진다. 실격도 아니다 — 확정된 누수와 "
            "모르는 것은 다른 사실이라 무게가 `hold`여야 한다."
        ),
        prediction=_prediction("g06"),
        reports=(_report("g06"),),
        documents=(
            _document(_doc_url("g06"), chunks_with_revision=0, latest_revised_at=None),
        ),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    GoldenCase(
        name="unverifiable_corpus_partial_lineage",
        guards=(
            "**부분 계보**를 통과시키는 회귀. 청크 셋 중 둘만 개정본 시각을 갖고 "
            "있으면, 검색이 하필 나머지 하나를 골랐을 수 있다. 판정이 운에 기대게 "
            "두지 않는다."
        ),
        prediction=_prediction("g07"),
        reports=(_report("g07"),),
        documents=(_document(_doc_url("g07"), chunks=3, chunks_with_revision=2),),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    GoldenCase(
        name="corpus_revision_on_the_event_day_is_a_boundary",
        guards=(
            "**경계값.** 대회 당일 개정본을 통과시키는 회귀 — `>=`를 `>`로 바꾸면 "
            "여기가 샌다. 경기 당일 개정본에 결과가 없다는 보장이 없다."
        ),
        prediction=_prediction("g08"),
        reports=(_report("g08"),),
        documents=(_document(_doc_url("g08"), latest_revised_at=REVISED_ON_EVENT_DAY),),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    GoldenCase(
        name="future_corpus_revision",
        guards=(
            "대회 **이후** 개정본을 인용하고도 통과하는 회귀. 그 글에는 결과가 "
            "실려 있을 수 있고, 없다는 것을 우리가 증명하지 못한다."
        ),
        prediction=_prediction("g09"),
        reports=(_report("g09"),),
        documents=(_document(_doc_url("g09"), latest_revised_at=REVISED_AFTER_EVENT),),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    GoldenCase(
        name="unknown_event_date_cannot_be_compared",
        guards=(
            "대회 날짜가 없을 때 비교를 **건너뛰고 통과**시키는 회귀. 비교 자체가 "
            "불가능하면 보류다."
        ),
        prediction=_prediction("g10", event_start_date=None),
        reports=(_report("g10"),),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    GoldenCase(
        name="retrieval_snapshot_outranks_the_document",
        guards=(
            "**그때 읽은 기록이 있는데 지금 코퍼스로 판정하는** 회귀 (Stage 4-B). "
            "문서 쪽은 깨끗한데 스냅샷은 경기 뒤 개정본을 읽었다고 말한다 — 기록이 "
            "이겨야 한다. 문서 단위 판정은 코퍼스의 *지금* 상태라 재수집이 과거 "
            "판정을 바꿔 버린다."
        ),
        prediction=_prediction("g11"),
        reports=(_report("g11"),),
        documents=(_document(_doc_url("g11"), latest_revised_at=REVISED_BEFORE_EVENT),),
        retrievals=(_retrieval("g11", source_revised_at=REVISED_AFTER_EVENT),),
        expected_status="held",
        expected_rule="unverifiable_corpus",
        expected_severity="hold",
    ),
    # ---- 4. 제외 (실격이 아니다) -------------------------------------------
    GoldenCase(
        name="pending",
        guards="결과가 없는 예측을 오답으로 세는 회귀. 오답도 실격도 아니다.",
        prediction=_prediction("g12", winner_pick=None, finished_at=None),
        reports=(_report("g12"),),
        expected_status="pending",
        expected_rule="pending",
        expected_severity="exclude",
    ),
    GoldenCase(
        name="withdrawn_match",
        guards=(
            "카드에서 사라진 경기를 **결과 대기**로 부르는 회귀. 결과를 기다리는 "
            "것이 아니라 물음 자체가 회수된 것이다."
        ),
        prediction=_prediction("g13", match_exists=False),
        reports=(_report("g13"),),
        expected_status="withdrawn_match",
        expected_rule="withdrawn_match",
        expected_severity="exclude",
    ),
    GoldenCase(
        name="withdrawn_outranks_pending",
        guards=(
            "**적용 순서.** 경기 행이 없으면 `winner_pick`도 없으므로, 순서를 "
            "뒤집으면 회수된 경기가 통째로 '결과 없음'으로 빨려 들어간다."
        ),
        prediction=_prediction(
            "g14", match_exists=False, winner_pick=None, finished_at=None
        ),
        reports=(_report("g14"),),
        expected_status="withdrawn_match",
        expected_rule="withdrawn_match",
        expected_severity="exclude",
    ),
    GoldenCase(
        name="external_outcome_known",
        guards=(
            "생성 전에 결과가 시스템 **밖에서** 알려져 있던 표본을 채점하는 회귀. "
            "`finished_at`은 이것을 못 본다 — 끝난 경기를 나중에 예측하고 결과를 "
            "그 뒤에 넣으면 시간 규칙을 그냥 지난다. 실격이 아니라 제외인 이유는 "
            "표본의 성격이 처음부터 다르기 때문이다."
        ),
        prediction=_prediction("g15", outcome_known_externally=True),
        reports=(_report("g15"),),
        expected_status="ex_post",
        expected_rule="external_outcome_known",
        expected_severity="exclude",
    ),
    GoldenCase(
        name="external_outcome_known_outranks_pending",
        guards=(
            "**적용 순서.** 결과가 아직 기록되지 않았어도 이 표본은 채점 대상이 "
            "되지 못한다. 그 사실을 나중이 아니라 지금 말한다."
        ),
        prediction=_prediction(
            "g16",
            outcome_known_externally=True,
            winner_pick=None,
            finished_at=None,
        ),
        reports=(_report("g16"),),
        expected_status="ex_post",
        expected_rule="external_outcome_known",
        expected_severity="exclude",
    ),
    GoldenCase(
        name="not_applicable_bookmaker_fallback",
        guards=(
            "북메이커 배당으로 대체된 예측이 에이전트 성적에 섞이는 회귀. "
            "**가장 먼저 본다** — 폴백 예측에 '결과 기록보다 먼저였나'를 묻는 것은 "
            "뜻이 없다."
        ),
        prediction=_prediction("g17", source="bookmaker_fallback"),
        reports=(_report("g17"),),
        expected_status="not_applicable",
        expected_rule="not_applicable",
        expected_severity="exclude",
    ),
)


def _judge(case: GoldenCase):
    _, _, items, _ = summarize_evaluation(
        [case.prediction], list(case.reports), list(case.corpus), case.retrievals
    )
    return items[0]


def _blocking(item) -> set[str]:
    """이 예측을 막은 규칙들.

    **`applicable=False`도 막은 것으로 센다.** 잴 수 없었던 규칙은 통과가 아니다 —
    모르는 것을 괜찮은 것으로 접으면 자격 판정이 하는 일이 없어진다.
    """
    return {v.code for v in item.verdicts if v.failed or not v.applicable}


@pytest.mark.parametrize("case", GOLDEN_SET, ids=lambda c: c.name)
def test_golden_status(case: GoldenCase) -> None:
    assert _judge(case).status == case.expected_status, case.guards


@pytest.mark.parametrize("case", GOLDEN_SET, ids=lambda c: c.name)
def test_golden_blocking_rule(case: GoldenCase) -> None:
    """**정확히 그 규칙만** 막았는가.

    집합으로 비교하는 이유는 과잉 차단도 회귀이기 때문이다 — 자기참조를 고치다가
    코퍼스 규칙까지 걸리게 만들면, 화면이 "왜 실격인지"를 틀리게 설명한다.
    """
    blocking = _blocking(_judge(case))
    expected = set() if case.expected_rule is None else {case.expected_rule}

    assert blocking == expected, case.guards


@pytest.mark.parametrize("case", GOLDEN_SET, ids=lambda c: c.name)
def test_golden_severity(case: GoldenCase) -> None:
    """**무게가 셋으로 갈린 채로 있는가.** 제외·실격·보류는 서로 다른 사실이다.

    `RULES` 표의 규칙 → 무게 대응을 못 박는다. `unverifiable_corpus`가 언젠가
    `hold`에서 `disqualify`로 슬쩍 옮겨 가면 여기가 잡는다.

    **무게는 최종 상태가 아니다.** 무게가 `disqualify`인 규칙이라도 잴 수 없었으면
    (`applicable=False`) 그 예측은 `held`로 간다 —
    `unmeasurable_rule_holds_it_does_not_disqualify`가 그 경우다.
    """
    if case.expected_rule is None:
        assert case.expected_severity is None
        return

    rule = next(r for r in RULES if r.code == case.expected_rule)
    assert rule.severity == case.expected_severity, case.guards


@pytest.mark.parametrize("case", GOLDEN_SET, ids=lambda c: c.name)
def test_eligible_flag_agrees_with_status(case: GoldenCase) -> None:
    """`eligible`은 상태에서 파생된다. 둘이 엇갈리면 화면과 집계가 갈라진다."""
    item = _judge(case)

    assert item.eligible is (item.status == "eligible")


# ---------------------------------------------------------------------------
# 메타 — 골든 세트 자신을 지킨다
# ---------------------------------------------------------------------------


def test_every_rule_has_a_golden_case() -> None:
    """**규칙을 추가하면 여기가 먼저 실패한다.**

    여덟 번째 규칙을 들이면서 골든 케이스를 안 만드는 길을 막는다. 규칙만 늘고
    방어선이 안 늘면, 그 규칙은 아무도 모르는 사이에 의미가 바뀔 수 있다.
    """
    covered = {case.expected_rule for case in GOLDEN_SET if case.expected_rule}

    assert covered == {rule.code for rule in RULES}


def test_every_status_has_a_golden_case() -> None:
    """일곱 상태가 **전부** 표에 있는가. 안 나오는 상태는 아무도 안 지키고 있다."""
    covered = {case.expected_status for case in GOLDEN_SET}

    assert covered == {
        "eligible",
        "held",
        "disqualified",
        "pending",
        "withdrawn_match",
        "ex_post",
        "not_applicable",
    }


def test_the_seven_buckets_cover_the_whole_set() -> None:
    """**합이 예측 수와 같다** — 어디로도 새지 않는다.

    골든 세트를 통째로 한 번에 넣어 집계까지 돌린다. 케이스별 판정이 다 맞아도
    집계가 한 칸을 빠뜨리면 화면의 숫자가 틀어지므로, 그 이음매를 따로 잰다.
    """
    totals, _, items, performance = summarize_evaluation(
        [case.prediction for case in GOLDEN_SET],
        [report for case in GOLDEN_SET for report in case.reports],
        [document for case in GOLDEN_SET for document in case.corpus],
        tuple(item for case in GOLDEN_SET for item in case.retrievals),
    )

    assert len(items) == len(GOLDEN_SET)
    assert totals.predictions == len(GOLDEN_SET)
    assert (
        totals.fallback
        + totals.ex_post
        + totals.withdrawn
        + totals.pending
        + totals.disqualified
        + totals.held
        + totals.eligible
    ) == totals.predictions

    expected = _expected_counts()
    assert totals.eligible == expected["eligible"]
    assert totals.held == expected["held"]
    assert totals.disqualified == expected["disqualified"]
    assert totals.pending == expected["pending"]
    assert totals.withdrawn == expected["withdrawn_match"]
    assert totals.ex_post == expected["ex_post"]
    assert totals.fallback == expected["not_applicable"]

    # 자격 있는 표본이 있으므로 성능이 계산된다. **0건이면 `None`이어야 한다**는
    # 반대쪽 계약은 `test_ai_lab_evaluation.py`가 본다.
    assert performance is not None
    assert performance.sample == expected["eligible"]


def _expected_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in GOLDEN_SET:
        counts[case.expected_status] = counts.get(case.expected_status, 0) + 1
    return counts


def test_golden_cases_have_unique_names_and_match_keys() -> None:
    """이름과 경기 키가 겹치면 집계 테스트가 **조용히** 케이스를 잃는다.

    판정은 `(event_slug, match_key)`로 리포트·검색 기록을 잇는다. 키가 겹치면 한
    케이스의 근거가 다른 케이스로 새어 들어가 표 전체가 거짓이 된다.
    """
    names = [case.name for case in GOLDEN_SET]
    keys = [case.prediction.match_key for case in GOLDEN_SET]

    assert len(set(names)) == len(names)
    assert len(set(keys)) == len(keys)


def test_every_case_explains_what_it_guards() -> None:
    """**설명 없는 골든 케이스는 없다.**

    깨졌을 때 무엇을 잃는지 모르면, 다음 사람은 기대값을 고쳐서 초록으로 만든다.
    그것이 이 파일이 가장 막고 싶은 일이다.
    """
    for case in GOLDEN_SET:
        assert case.guards.strip(), case.name
