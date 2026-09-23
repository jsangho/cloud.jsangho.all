"""예측 한 건을 **다시 돌려 본다** (Phase 5).

로드맵이 "replay"라고 부른 것을 그대로 받으면 거짓말이 된다 — 예측을 통째로
재현하려면 그때 검색된 청크와 그때 모델이 뱉은 문장이 다시 나와야 하는데, 둘 다
이 저장 구조 위에서는 불가능하다. 그래서 여기서 하는 일은 **재현 가능한 단계만
실제로 다시 돌리고, 나머지는 왜 못 돌리는지 같이 내보내는 것**이다.

다섯 단계 중 실제로 다시 돌아가는 것은 둘이다.

1. **질의 조립** — 저장된 질의와, 지금 카드로 다시 만든 질의를 견준다.
   이 대조가 통과하면 경기 제목과 **모든 선택지 이름**이 그때와 같다는 뜻이다.
   2번이 지금 카드의 선택지를 쓰므로, 이 값이 곧 2번의 신뢰도다.
2. **리포트 합성** — 저장된 리포트를 `synthesize`에 그대로 다시 넣어
   pick·승률·합의도가 저장된 값과 같은지 본다. 다르면 **그 사이 합성 규칙이
   바뀌었다**는 뜻이다(또는 카드가 바뀌었다 — 그래서 1번이 먼저다).

나머지 셋은 원리상 못 돌린다. 감추지 않고 `REPLAY_STAGES`로 함께 내보낸다 —
Phase 9가 빈 replay 칸을 만들지 않은 이유가 그것이다. 빈칸은 "재현 가능한데 안
했다"로 읽히고, 못 한다는 사실은 칸이 아니라 문장으로 적혀야 한다.

**여기서 쓰는 것은 생성 경로와 같은 함수·같은 상수다.** 베껴 오면 그것은 재현이
아니라 두 번째 구현이고, 규칙이 바뀌어도 둘이 나란히 틀린 답을 내놓는다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from kayfabe.app.dtos.agent_prediction_dto import MatchOption
from kayfabe.app.services.ai_lab_integrity import PredictionRow, ReportRow

# **같은 상수여야 한다.** `agent_count`는 합의도(coverage)의 분모라 값이 다르면
# 합성이 다른 답을 낸다. 여기에 3을 다시 적으면 생성 쪽이 넷으로 늘어난 날
# 재현이 조용히 거짓을 말한다.
from kayfabe.app.use_cases.ai_prediction_interactor import (
    AGENT_COUNT,
    build_knowledge_query,
)
from kayfabe.domain.entities.agent_prediction import (
    AgentKind,
    AgentReport,
    PredictionSource,
)
from kayfabe.domain.services.prediction_synthesis import (
    PredictionSynthesis,
    ReportsUnavailableError,
    synthesize,
)


class ReplayStatus(StrEnum):
    """합성을 다시 돌린 결과.

    **"틀렸다"를 말하는 값이 아니다.** 예측이 맞았는지는 채점이 보고, 여기서 묻는
    것은 "저장된 재료로 저장된 결론이 다시 나오는가"다.
    """

    #: 같은 값이 나왔다 — 합성 규칙이 그때와 같다.
    REPRODUCED = "reproduced"
    #: 다시 돌렸는데 값이 다르다 — 규칙이 바뀌었거나 카드가 바뀌었다.
    DIVERGED = "diverged"
    #: 다시 돌릴 수 없다. **실패가 아니라 재료가 없는 상태다.**
    UNREPLAYABLE = "unreplayable"


@dataclass(frozen=True)
class ReplayMismatch:
    """어긋난 칸 하나. **두 값을 다 싣는다** — "다르다"만으로는 아무것도 못 한다."""

    field: str
    stored: str
    replayed: str


@dataclass(frozen=True)
class ReplayStage:
    """생성 파이프라인의 한 단계와 그것을 다시 돌릴 수 있는지.

    화면이 문구를 지어내지 않도록 서버가 낸다 — `RULES`와 같은 이유다.
    """

    stage: str
    label: str
    replayable: bool
    note: str


#: 생성 순서 그대로다. **못 돌리는 단계를 목록에서 빼지 않는다** — 빠지면 화면이
#: "전부 재현됐다"로 읽힌다.
REPLAY_STAGES: tuple[ReplayStage, ...] = (
    ReplayStage(
        stage="knowledge_query",
        label="검색 질의 조립",
        replayable=True,
        note=(
            "경기 제목과 선택지 이름으로 만든다. 저장된 질의와 지금 카드로 다시 "
            "만든 질의를 견주면 카드가 그때와 같은지 알 수 있다."
        ),
    ),
    ReplayStage(
        stage="knowledge_retrieval",
        label="지식 검색",
        replayable=False,
        note=(
            "재수집이 같은 URL의 옛 청크를 지우므로 코퍼스에는 판본이 하나뿐이고, "
            "어떤 시점으로도 그때의 검색을 다시 할 수 없다. 그때 읽은 본문은 "
            "검색 기록에 스냅샷으로 남아 있다(Phase 3)."
        ),
    ),
    ReplayStage(
        stage="prompt",
        label="프롬프트 조립",
        replayable=False,
        note=(
            "프롬프트 원문은 어디에도 저장하지 않는다(§11-6). 남는 것은 되돌릴 수 "
            "없는 지시문 해시뿐이라, 같은 판인지 대조만 되고 복원은 되지 않는다."
        ),
    ),
    ReplayStage(
        stage="model_call",
        label="모델 호출",
        replayable=False,
        note=(
            "같은 프롬프트라도 모델은 같은 문장을 다시 내놓지 않는다. 그때 무엇이 "
            "답했는지는 기록(모델·지시문 판)으로만 남는다."
        ),
    ),
    ReplayStage(
        stage="synthesis",
        label="리포트 합성",
        replayable=True,
        note=(
            "저장된 리포트를 생성 때와 같은 함수에 그대로 다시 넣는다. 선택지는 "
            "지금 카드에서 읽으므로, 카드가 바뀌었으면 결과가 달라질 수 있다."
        ),
    ),
)


@dataclass(frozen=True)
class PredictionReplay:
    """예측 한 건을 다시 돌려 본 결과 (Phase 5)."""

    status: ReplayStatus
    #: `unreplayable`의 사유. 돌아갔으면 `None`이다.
    reason: str | None = None
    #: 어긋난 칸들. `reproduced`면 비어 있다.
    mismatches: tuple[ReplayMismatch, ...] = ()
    #: 카드가 그때와 같은가 — 저장된 질의와 다시 만든 질의의 대조 결과.
    #:
    #: **`None`은 "같다"가 아니라 "판단할 수 없다"는 뜻이다.** 질의 기록이 없거나
    #: (Phase 3 이전) 경기 행이 사라졌으면 견줄 상대가 없다.
    card_unchanged: bool | None = None
    stages: tuple[ReplayStage, ...] = REPLAY_STAGES


_QUERY_FIELD = "knowledge_query"


def replay_prediction(
    prediction: PredictionRow,
    reports: Sequence[ReportRow],
    options: Sequence[MatchOption],
) -> PredictionReplay:
    """저장된 재료로 합성을 다시 돌린다. **DB도 모델도 부르지 않는다.**

    `options`는 **지금 카드**의 선택지다 — 그때 카드의 스냅샷은 없다. 그래서 질의
    대조를 먼저 하고 그 결과를 함께 내보낸다: 카드가 바뀐 채로 나온 불일치를
    "합성 규칙이 바뀌었다"로 읽으면 안 된다.
    """
    card_unchanged, query_mismatch = _compare_query(prediction, options)

    blocked = _why_not_replayable(prediction, options)
    if blocked is not None:
        return PredictionReplay(
            status=ReplayStatus.UNREPLAYABLE,
            reason=blocked,
            mismatches=query_mismatch,
            card_unchanged=card_unchanged,
        )

    try:
        entities = [_to_entity(report) for report in reports]
    except ValueError as exc:
        # 저장된 값이 엔티티 규약을 벗어났다. 재현이 아니라 데이터의 문제이므로
        # 조용히 통과시키지 않고 사유로 남긴다.
        return PredictionReplay(
            status=ReplayStatus.UNREPLAYABLE,
            reason=f"저장된 리포트를 다시 읽지 못했습니다: {exc}",
            mismatches=query_mismatch,
            card_unchanged=card_unchanged,
        )

    try:
        synthesis = synthesize(
            entities,
            agent_count=AGENT_COUNT,
            options=[option.pick for option in options],
        )
    except ReportsUnavailableError:
        return PredictionReplay(
            status=ReplayStatus.UNREPLAYABLE,
            reason="의견을 낸 리포트가 없어 합성이 성립하지 않습니다.",
            mismatches=query_mismatch,
            card_unchanged=card_unchanged,
        )

    mismatches = query_mismatch + _compare_synthesis(prediction, synthesis)
    diverged = any(item.field != _QUERY_FIELD for item in mismatches)
    return PredictionReplay(
        status=ReplayStatus.DIVERGED if diverged else ReplayStatus.REPRODUCED,
        mismatches=mismatches,
        card_unchanged=card_unchanged,
    )


def _why_not_replayable(
    prediction: PredictionRow, options: Sequence[MatchOption]
) -> str | None:
    if prediction.source != str(PredictionSource.AGENTS):
        # 배당 폴백은 합성을 지나지 않았다. 그 경로를 여기서 다시 돌리면 그때
        # 배당이 필요한데, 배당도 카드에 있어 지금 값은 그때 값이 아니다.
        return "에이전트 합성이 아니라 배당 폴백으로 만들어진 예측입니다."
    if not options:
        return "경기 카드가 남아 있지 않아 그때의 선택지를 알 수 없습니다."
    return None


def _compare_query(
    prediction: PredictionRow, options: Sequence[MatchOption]
) -> tuple[bool | None, tuple[ReplayMismatch, ...]]:
    """저장된 질의 vs 지금 카드로 다시 만든 질의.

    **이 대조가 카드 드리프트의 증인이다.** 질의는 경기 제목과 모든 선택지 이름을
    이어 붙인 값이라, 한 글자라도 바뀌면 여기서 드러난다. `pick_name`만 견주면
    고르지 않은 쪽이 바뀐 것을 놓친다.
    """
    if prediction.knowledge_query is None or not options:
        return None, ()

    rebuilt = build_knowledge_query(prediction.match_title, options)
    if rebuilt == prediction.knowledge_query:
        return True, ()
    return False, (
        ReplayMismatch(
            field=_QUERY_FIELD,
            stored=prediction.knowledge_query,
            replayed=rebuilt,
        ),
    )


def _compare_synthesis(
    prediction: PredictionRow, synthesis: PredictionSynthesis
) -> tuple[ReplayMismatch, ...]:
    """세 칸을 **정확히** 견준다.

    허용 오차를 두지 않는다. 같은 입력이 같은 순서로 같은 연산을 지나므로 오차가
    낄 자리가 없고, 여유를 두면 진짜 드리프트를 그 여유 안에 숨기게 된다.
    """
    pairs = (
        ("pick", prediction.pick, synthesis.pick),
        ("win_probability", prediction.win_probability, synthesis.win_probability),
        ("confidence", prediction.confidence, synthesis.confidence),
    )
    return tuple(
        ReplayMismatch(field=field, stored=_text(stored), replayed=_text(replayed))
        for field, stored, replayed in pairs
        if stored != replayed
    )


def _text(value: object) -> str:
    return repr(value) if isinstance(value, float) else str(value)


def _to_entity(report: ReportRow) -> AgentReport:
    """저장된 행을 합성이 받는 엔티티로 되돌린다.

    `summary`·`sources`는 합성이 보지 않지만 그대로 싣는다 — 엔티티를 절반만
    채우면 나중에 합성이 그 칸을 보게 됐을 때 재현이 조용히 달라진다.
    """
    return AgentReport(
        agent=AgentKind(report.agent),
        pick=report.pick,
        weight=report.weight,
        summary=report.summary,
        sources=report.sources,
    )
