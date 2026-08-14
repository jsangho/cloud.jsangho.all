"""커리어 진행 입력 포트 (하네스 §6·§7).

**로그인과 체험판이 같은 유스케이스를 쓴다**(§3-D8·§11-25). 판정 규칙이 두 벌이 되면
어느 한쪽만 고쳐지는 날이 오고, 그때 두 화면의 결과가 갈린다. 갈리는 것은 세이브를
어디서 읽고 어디에 쓰는가뿐이라, 그 차이는 `CareerRepository` 구현이 흡수한다.

그래서 `advance`·`choose`가 로그인용과 체험판용으로 나뉘어 있다 — 인자만 다르고
(하나는 `run_id`, 하나는 세이브 전체) 내부에서 같은 진행 루프를 부른다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from wwe_game.app.dtos.career_dto import (
    AdvanceCommand,
    AdvanceResult,
    AnswerOfferCommand,
    CallOutCommand,
    CareerLogPage,
    CashInCommand,
    ChooseCommand,
    GuestAdvanceCommand,
    GuestAnswerOfferCommand,
    GuestCallOutCommand,
    GuestCashInCommand,
    GuestChooseCommand,
    GuestReportCommand,
    GuestResumeCommand,
    GuestSetGoalCommand,
    GuestStartCommand,
    ModeView,
    NewsFeedPage,
    PresetView,
    SetGoalCommand,
    StartRunCommand,
)
from wwe_game.domain.services.show_report import ShowReport


class RunAlreadyActiveError(Exception):
    """진행 중인 세이브가 있는데 새로 시작하려 할 때 (하네스 §8 → 409).

    세이브는 하나뿐이다(§13-Q4). 덮어쓰지 않고 막는 이유: 30년짜리 진행이 클릭 한 번에
    사라지면 안 된다. 지우려면 `retire()`를 먼저 부른다.
    """


class ChoiceRequiredError(Exception):
    """대기 이벤트가 있는데 진행을 시도했을 때 (하네스 §8 → 409 · §11-2)."""


class NoPendingEventError(Exception):
    """대기 이벤트가 없는데 선택을 냈을 때 (하네스 §8 → 409).

    "없는 선택지 코드"(`InvalidChoiceError`, 400)와 다르다 — 이건 이벤트 자체가 없다.
    """


class ReportNotFoundError(Exception):
    """대회 주차가 아니거나 아직 지나지 않은 주차 (§3-D45).

    "없는 주차"와 "리포트를 만들지 않는 주차"를 나누지 않는다 — 화면 입장에서 둘 다
    "그 밤은 없다"이고, 나누면 라우터가 상태 코드를 둘로 갈라야 한다.
    """


class GuestModeNotAllowedError(Exception):
    """체험판이 `monthly`·`weekly`를 요청했을 때 (하네스 §8 → 400 · §11-24).

    두 모드는 틱이 390·1560개라 상태가 브라우저에 안 들어간다(§3-D8).
    """


class CareerUseCase(ABC):
    """'다음' 중심의 진행 코디네이터.

    **판정은 하나도 하지 않는다.** 주차 시뮬·이벤트 추첨·은퇴 판정은 전부 도메인 서비스의
    순수 함수이고(§3-D1), 여기는 그것들을 순서대로 부르고 저장하는 자리다.
    """

    # ── 로그인 플레이 ─────────────────────────────────────────

    @abstractmethod
    async def start(self, command: StartRunCommand) -> AdvanceResult:
        """새 커리어. 이미 진행 중이면 `RunAlreadyActiveError`."""

    @abstractmethod
    async def current(self, user_id: int) -> AdvanceResult | None:
        """진행 중인 세이브와 대기 이벤트. 없으면 None."""

    @abstractmethod
    async def advance(self, command: AdvanceCommand) -> AdvanceResult:
        """'다음'. 대기 이벤트가 있으면 `ChoiceRequiredError`."""

    @abstractmethod
    async def choose(self, command: ChooseCommand) -> AdvanceResult:
        """대기 이벤트에 답한다. 없으면 `NoPendingEventError`."""

    @abstractmethod
    async def set_goal(self, command: SetGoalCommand) -> AdvanceResult:
        """이번 분기에 걸 것을 정한다 (§3-D80). 진행시키지는 않는다."""
        ...

    @abstractmethod
    async def answer_offer(self, command: AnswerOfferCommand) -> AdvanceResult:
        """재계약 협상에 답한다 (§3-D84). 협상 중이 아니면 `NoOfferOpenError`.

        `set_goal`과 나란히 둔다 — `choose`에 합치지 않는 이유도 같다(반응 대 선언).
        """
        ...

    @abstractmethod
    async def cash_in(self, command: CashInCommand) -> AdvanceResult:
        """가방을 쓰기로 한다 (§3-D85). 쓸 수 없으면 `CannotCashInError`.

        **진행시키지 않는다.** 표식만 서고, 다음 '다음'부터 규칙이 타이틀전을 건다 —
        `set_goal`·`answer_offer`와 같은 자리다. 다만 저 둘과 달리 **막고 있던 것을
        푸는 것이 아니라** 안 해도 그만인 행동이다.
        """
        ...

    @abstractmethod
    async def call_out(self, command: CallOutCommand) -> AdvanceResult:
        """그 사람에게 시비를 건다 (§3-D86). 걸 수 없으면 `CannotCallOutError`.

        **진행시키지 않는다.** `cash_in`과 같은 상시 행동이라, 안 불러도 그만이다.
        """
        ...

    @abstractmethod
    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> CareerLogPage:
        """커리어 로그 한 페이지. 30년이면 1560줄이라 전부 내려보내지 않는다."""

    @abstractmethod
    async def read_report(self, run_id: int, user_id: int, week: int) -> ShowReport:
        """그 주차의 리포트 (§3-D45). 대회 주차가 아니면 `ReportNotFoundError`."""
        ...

    @abstractmethod
    async def read_news(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> NewsFeedPage:
        """내 세계선의 뉴스 한 페이지 (§3-D31).

        로그와 따로 두는 이유는 담는 것이 달라서다 — 로그는 모든 주차이고 뉴스는 남을
        만한 사건만이다. **팀 세계의 소식이 함께 들어온다**(§3-D30).
        """

    @abstractmethod
    async def retire(self, run_id: int, user_id: int) -> AdvanceResult:
        """스스로 커리어를 닫는다 — 은퇴 5조건 중 하나다(§3-D16)."""

    # ── 체험판 (§3-D8) ────────────────────────────────────────

    @abstractmethod
    def start_guest(self, command: GuestStartCommand) -> AdvanceResult:
        """체험판 시작. 잠긴 모드면 `GuestModeNotAllowedError`.

        **동기다** — 읽고 쓸 저장소가 없어 `await`할 대상이 없다(fastapi/CLAUDE.md §9).
        """

    @abstractmethod
    def advance_guest(self, command: GuestAdvanceCommand) -> AdvanceResult:
        """받은 세이브를 진행시켜 **다음 상태를 통째로** 돌려준다. 저장하지 않는다.

        상태는 클라이언트가 들고 있으므로 조작될 수 있다. 값 객체가 입구에서 검증하고
        (범위 밖 스탯·1560 초과 주차는 `InvalidCareerRunError`), 규칙에 맞는 값이면
        그대로 받는다 — **신뢰하지 않되 막지도 않는다**(§3-D8, 순위표와 무관하므로).
        """

    @abstractmethod
    def resume_guest(self, command: GuestResumeCommand) -> AdvanceResult:
        """받은 세이브를 **진행 없이** 화면 상태로 되돌린다 — `current()`의 체험판 짝이다.

        `advance_guest`로 대신할 수 없다. 저쪽은 한 틱을 실제로 태우고, 대기 이벤트가
        있으면 `ChoiceRequiredError`로 막는다 — 다시 열었을 뿐인데 진행되거나 막히면
        안 된다. 여기서는 **대기 이벤트가 있는 채로 돌아오는 것이 정상**이다.
        """

    @abstractmethod
    def choose_guest(self, command: GuestChooseCommand) -> AdvanceResult:
        """체험판의 이벤트 선택 판정. 대기 이벤트가 없으면 `NoPendingEventError`."""

    @abstractmethod
    def set_guest_goal(self, command: GuestSetGoalCommand) -> AdvanceResult:
        """체험판의 분기 목표 (§3-D80)."""
        ...

    @abstractmethod
    def answer_guest_offer(self, command: GuestAnswerOfferCommand) -> AdvanceResult:
        """체험판의 재계약 협상 (§3-D84). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        ...

    @abstractmethod
    def cash_in_guest(self, command: GuestCashInCommand) -> AdvanceResult:
        """체험판의 가방 현금화 (§3-D85). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        ...

    @abstractmethod
    def call_out_guest(self, command: GuestCallOutCommand) -> AdvanceResult:
        """체험판의 시비 걸기 (§3-D86). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        ...

    @abstractmethod
    def read_guest_news(self, command: GuestResumeCommand) -> NewsFeedPage:
        """체험판 인박스 — **배경 소식만** (§3-D67).

        내 뉴스(대관·부상·턴)는 주차 로그에서 나오는데 체험판 로그는 서버에 없다
        (§3-D8). 배경(벨트·대립·팀·명부)은 시드와 주차만으로 되짚으므로 그쪽은 낼 수
        있다 — **없는 것을 지어내지 않고, 낼 수 있는 것을 안 내지도 않는다.**
        """

    @abstractmethod
    def read_guest_report(self, command: GuestReportCommand) -> ShowReport:
        """그 밤의 리포트, 체험판 (§3-D51). 대회 주차가 아니면 `ReportNotFoundError`.

        `read_report`로 대신할 수 없다. 저쪽은 DB 로그에서 그 주차 줄을 되읽는데
        체험판에는 로그가 없다(§3-D8) — **내 경기 기록은 이미 화면의 그 줄에 있고,
        서버가 더할 것은 배경뿐이다.**
        """

    # ── 메타 ──────────────────────────────────────────────────

    @abstractmethod
    def modes(self) -> tuple[ModeView, ...]:
        """모드 4종. 상수를 읽을 뿐이라 동기다 (§3-D15)."""

    @abstractmethod
    def presets(self) -> tuple[PresetView, ...]:
        """캐릭터 생성의 바탕이 될 선수 목록 (§3-D10-1). 상수를 읽을 뿐이라 동기다."""
