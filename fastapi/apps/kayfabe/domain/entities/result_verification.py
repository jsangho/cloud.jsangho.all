"""결과 확정 에이전트의 도메인 모델.

## 이 에이전트가 기존 세 에이전트와 다른 점

승부예측 세 에이전트(`storyline`·`odds`·`rumor`)는 **예측이 잠기기 전**에 돌고, 그래서
자율성을 줄 수 없다 — 모델이 매번 다른 경로를 타면 `synthesis_version`으로 산식을
골라 재현하는 일이 불가능해지고, AI LAB의 감사·재현이 근거를 잃는다.

이 에이전트는 **예측이 잠긴 뒤**에 돈다. 끝난 대회의 결과를 찾는 일이라 예측을
건드리지 않고, 누수 판정(`ai_lab_leakage`)이 막는 것은 예측 *전*에 대회 문서를 읽는
것이므로 여기에는 걸리지 않는다. 자율성이 안전한 유일한 구간이다.

## 모델에게 쓰기 권한이 없다

**`record_result` 같은 도구는 존재하지 않는다.** 모델이 하는 일은 읽고 주장하는
것뿐이고(`ResultClaim`), 그 주장을 쓸지 보류할지는 `result_adjudication.adjudicate`가
정한다 — 순수 함수이고, 프레임워크도 모델도 모른다. 그래서 "모델이 헛것을 써 넣는"
경로가 구조적으로 없다.

## 보류는 실패가 아니다

`close_past_events.py`가 "`start_date`가 `NULL`이면 통과가 아니라 **보류**"라고 정한
것과 같은 태도다. 승자를 못 찾은 것은 정상 종료이고, 틀린 승자를 쓰는 것만 사고다.
`winner_pick`은 채점·적중률·포인트 집계의 입력이라(`point_aggregation`), 한 번
잘못 쓰면 사용자 점수가 조용히 틀어진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class ReviewOption:
    """카드에 실린 선택지 하나.

    `app.dtos.agent_prediction_dto.MatchOption`과 모양이 닮았지만 그것을 쓰지 않는다 —
    도메인은 app을 import할 수 없다(클린 아키텍처 계약). 옮기는 일은 app이 한다.
    """

    #: `ple_matches.winner_pick`과 같은 형식. `"left"`·`"right"` 또는 다인전 인덱스.
    pick: str
    name: str


@dataclass(frozen=True)
class MatchUnderReview:
    """결과를 찾아야 하는 경기 하나."""

    event_slug: str
    event_label: str
    match_key: str
    title: str
    options: tuple[ReviewOption, ...]


@dataclass(frozen=True)
class Evidence:
    """모델에게 **실제로 건넨** 본문 한 덩어리.

    인용 대조의 기준이고, 계보의 출처다. `source_title`·`revision_id`를 모델이 아니라
    이 기록에서 얻는 이유는 하나다 — **계보는 우리 것이어야 한다.** 모델에게 출처를
    적어 달라고 하면 그럴듯한 다른 문서를 지어낼 수 있고(`describe_knowledge`가 URL을
    프롬프트에 넣지 않는 것과 같은 이유다), 그 계보는 검증할 수 없다.
    """

    text: str
    source_title: str
    revision_id: str | None = None


@dataclass(frozen=True)
class ResultClaim:
    """모델이 마지막에 내놓은 주장. **두 칸뿐이다.**

    출처를 묻지 않는다(`Evidence`가 갖고 있다). 확신도도 묻지 않는다 — 이 일에
    확신도는 없다. 인용이 본문에 있고 이름이 카드에 있으면 쓰고, 아니면 보류다.
    """

    #: 승자 이름. `None`은 **"승자가 없다"** 는 주장이다(무승부·노컨테스트).
    winner_name: str | None
    #: 받아 온 본문에서 **한 글자도 바꾸지 않고** 옮겨 왔다고 주장하는 구절.
    quote: str


class HoldReason(StrEnum):
    """쓰지 않은 이유. 화면·보고에 그대로 나가는 값이다."""

    NO_CLAIM = "no_claim"
    """모델이 주장을 내놓지 못했다 — 걸음 상한 초과·JSON 파손."""

    ENGINE_UNAVAILABLE = "engine_unavailable"
    """**아예 물어보지 못했다.** 벤더의 일시 장애를 다 견딘 뒤에도 답이 없었다.

    `NO_CLAIM`과 섞지 않는다. 저쪽은 "물어봤는데 못 골랐다"이고 이쪽은 "묻지
    못했다"다 — 보고에서 합치면 "위키에 결과가 없다"와 "우리 쪽이 막혔다"를
    구분할 수 없고, 다시 돌리면 되는 것과 사람이 봐야 하는 것이 뒤섞인다.
    """

    NO_WINNER = "no_winner"
    """모델이 "승자 없음"이라고 답했다. 무승부·노컨테스트면 이것이 정답이다."""

    QUOTE_MISSING = "quote_missing"
    """인용이 비었다. 근거 없는 주장은 받지 않는다."""

    QUOTE_NOT_FOUND = "quote_not_found"
    """인용이 우리가 건넨 본문에 없다 — **지어낸 것이다.**"""

    NAME_NOT_ON_CARD = "name_not_on_card"
    """카드에 없는 이름을 골랐다. `_pick`이 카드 밖 pick을 버리는 것과 같은 판단이다."""

    AMBIGUOUS_NAME = "ambiguous_name"
    """두 선택지에 다 걸린다(`Uso`가 형제 둘에 걸리는 경우). 어느 쪽인지 모른다."""

    NAME_NOT_IN_QUOTE = "name_not_in_quote"
    """카드가 적은 이름의 어느 조각도 인용에 없다 — 인용이 이 승자를 말하지 않는다."""

    CONTRADICTED_BY_QUOTE = "contradicted_by_quote"
    """**인용이 이 사람을 패자로 적고 있다.** 모델이 문장을 거꾸로 읽은 것이다.

    2026-09-28 실측에서 이 관문이 없었을 때 뚫렸다. `SummerSlam (2026)` 본문의
    `Liv Morgan (c) defeated Iyo Sky by pinfall`을 인용한 채 승자를 `Iyo Sky`라고
    주장하면 앞의 관문 넷을 **전부 통과한다** — 인용은 진짜고, 이름은 카드에 있고,
    그 이름은 인용 안에 보인다. 출처를 검증하는 관문들은 문장의 방향을 읽지 않는다.
    """


@dataclass(frozen=True)
class Verdict:
    """한 경기에 대한 판정. **쓸 수 있는 것은 `writable`이 참인 것뿐이다.**"""

    match_key: str
    pick: str | None = None
    winner_name: str | None = None
    hold: HoldReason | None = None
    quote: str = ""
    source_title: str = ""
    source_revision_id: str | None = None

    @property
    def writable(self) -> bool:
        return self.hold is None and self.pick is not None
