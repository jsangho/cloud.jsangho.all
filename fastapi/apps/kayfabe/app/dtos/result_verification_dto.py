from __future__ import annotations

from dataclasses import dataclass, field

from kayfabe.domain.entities.result_verification import HoldReason


@dataclass(frozen=True)
class VerifyResultsCommand:
    """무엇을 얼마나 볼지, 그리고 **쓸지 말지**.

    `apply`가 기본 거짓이다 — `close_past_events.py`와 같은 이유이고 더 강한 이유다.
    저쪽이 쓰는 값은 오늘 날짜에서 파생되지만, 이쪽은 **모델이 읽은 문서에서** 나온다.
    """

    #: 특정 대회만 볼 때 그 slug. 비우면 결과 미기록 대회 전부.
    event_slug: str | None = None
    #: 한 실행에서 볼 경기 수 상한. 비용이 경기 수에 비례하므로 기본을 낮게 둔다.
    limit: int = 20
    apply: bool = False


@dataclass(frozen=True)
class MatchVerification:
    """경기 하나의 결과. 쓴 것·보류한 것 모두 여기로 보고된다."""

    event_slug: str
    match_key: str
    title: str
    #: 쓸 수 있다고 판정된 값. 보류면 둘 다 `None`이다.
    pick: str | None = None
    winner_name: str | None = None
    hold: HoldReason | None = None
    #: 실제로 DB에 썼는가. 드라이런에서는 `pick`이 있어도 거짓이다.
    written: bool = False
    #: 근거. 보고에만 쓰고 DB에는 넣지 않는다(저장할 칸이 아직 없다).
    quote: str = ""
    source_title: str = ""
    source_revision_id: str | None = None
    #: 이 경기에 쓴 도구 호출 수. 비용을 사람이 눈으로 보는 자리다.
    tool_calls: int = 0
    #: **실제로 답한 모델.** 설정값이 아니라 응답이 말한 이름이다 — `AgentRuntime.model`이
    #: 같은 이유로 실제 모델을 담는다(예비 모델이 답한 날의 기록이 거짓이 되지 않게).
    model: str | None = None

    @property
    def held(self) -> bool:
        return self.hold is not None


@dataclass(frozen=True)
class VerificationRun:
    """한 실행 전체의 보고."""

    matches: tuple[MatchVerification, ...] = field(default_factory=tuple)
    applied: bool = False
    #: 결과 미기록으로 찾아낸 경기 수. `limit`에 잘리기 전 값이다 — 잘렸다는 사실이
    #: 보고에서 사라지면 "다 봤다"로 오해된다.
    found: int = 0

    @property
    def written(self) -> int:
        return sum(1 for match in self.matches if match.written)

    @property
    def writable(self) -> int:
        return sum(1 for match in self.matches if match.pick is not None)

    @property
    def held(self) -> int:
        return sum(1 for match in self.matches if match.held)

    @property
    def tool_calls(self) -> int:
        return sum(match.tool_calls for match in self.matches)
