"""유스케이스 경계의 자료형 (하네스 §6·§7).

**Pydantic이 아니다.** 이 레이어는 프레임워크를 모른다 — HTTP 스키마는
`adapter/inbound/api/schemas/career_schema.py`가 따로 갖고, 라우터가 그 사이를 옮긴다.
저장소의 다른 앱들도 같은 규약이다(`kayfabe/app/dtos/*`).

**도메인 객체를 그대로 실어 나른다.** `AdvanceResult.run`은 `CareerRun`이고
`WeekReportView.report`는 `WeekReport`다 — 값 객체를 한 겹 더 베끼면 필드가 늘 때마다
세 곳(도메인·DTO·스키마)을 고쳐야 하고, 그 중 하나를 빠뜨리면 조용히 값이 사라진다.
DTO가 새로 만드는 것은 **도메인에 없는 것**뿐이다: 서술 문장, 멈춘 이유, 화면에 보일
선택지 목록.

체험판(§3-D8)도 같은 자료형을 쓴다. 다른 것은 세이브를 어디서 읽고 어디에 쓰는가뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from wwe_game.domain.entities.career_run import CareerRun, EndReason
from wwe_game.domain.value_objects.week_report import WeekReport
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle


class StepMode(StrEnum):
    """'다음' 한 번이 얼마나 가는지 (§3-D17)."""

    AUTO = "auto"
    """이벤트를 만날 때까지. 기본값이다 — `weekly`가 클릭 1560번이 되지 않게."""
    TICK = "tick"
    """정확히 `weeks_per_tick` 주만. 이벤트를 만나면 그 전에 멈춘다."""


class StopReason(StrEnum):
    """진행이 멈춘 이유. **어디서 멈췄는지가 곧 화면의 상태다.**"""

    EVENT = "event"
    """대기 이벤트를 만났다 — 선택하기 전에는 더 못 간다."""
    TICK = "tick"
    """요청한 만큼 갔다."""
    ENDED = "ended"
    """커리어가 끝났다 (§3-D16 은퇴 5조건)."""
    PLE = "ple"
    """대형 대회에서 한 번 끊었다 (§3-D17). 굵은 틱을 쓰는 모드는 끊지 않는다."""


# ── 명령 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class StartRunCommand:
    """새 커리어. **나이는 받지 않는다** — 20세 고정이다(§3-D10).

    이름과 모드만 필수다. 나머지 셋은 `based_on`이 채워 주거나 직접 넘긴다(§3-D10-1).
    """

    user_id: int
    name: str
    mode_code: str
    based_on: str | None = None
    """바탕으로 삼을 실존 선수. 그 선수의 디비전·스타일·국적이 **기본값**이 된다."""
    gender: Gender | None = None
    country_code: str | None = None
    play_style: PlayStyle | None = None
    seed: int | None = None
    """생략하면 유스케이스가 만든다. 테스트가 재현을 고정할 때만 넘긴다."""


@dataclass(frozen=True)
class AdvanceCommand:
    run_id: int
    user_id: int
    step: StepMode = StepMode.AUTO


@dataclass(frozen=True)
class ChooseCommand:
    run_id: int
    user_id: int
    choice_code: str


@dataclass(frozen=True)
class GuestStartCommand:
    """체험판 시작. `user_id`가 없다 — 저장은 브라우저가 한다(§3-D8)."""

    name: str
    mode_code: str
    based_on: str | None = None
    gender: Gender | None = None
    country_code: str | None = None
    play_style: PlayStyle | None = None
    seed: int | None = None


@dataclass(frozen=True)
class GuestAdvanceCommand:
    """**상태를 통째로 받는다.** 서버는 규칙만 돌리고 다음 상태를 돌려준다."""

    run: CareerRun
    step: StepMode = StepMode.AUTO


@dataclass(frozen=True)
class GuestChooseCommand:
    run: CareerRun
    choice_code: str


# ── 결과 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ChoiceView:
    """화면에 보이는 선택지. **위험도·확률은 넣지 않는다**(§11-14).

    카드 데이터의 `risk`·`injury_risk`는 판정용 수치라 그대로 내보내면 최적해가
    드러난다. 플레이어가 읽어야 하는 것은 라벨뿐이다.
    """

    code: str
    label: str


@dataclass(frozen=True)
class PendingEventView:
    """대기 중인 이벤트. 본문은 이미 변주가 골라진 상태다."""

    code: str
    title: str
    body: str
    choices: tuple[ChoiceView, ...]


@dataclass(frozen=True)
class WeekReportView:
    """주차 리포트 + 그 주차의 문장. 리포트 자체는 도메인 값이라 그대로 든다."""

    report: WeekReport
    narration: str

    @property
    def week(self) -> int:
        return self.report.week


@dataclass(frozen=True)
class AdvanceResult:
    """'다음' 한 번의 결과. **여러 주차가 쌓일 수 있다**(§3-D17 `auto`)."""

    run: CareerRun
    weeks: tuple[WeekReportView, ...] = ()
    stop_reason: StopReason = StopReason.TICK
    pending_event: PendingEventView | None = None

    @property
    def ended(self) -> bool:
        return self.stop_reason is StopReason.ENDED

    @property
    def end_reason(self) -> EndReason | None:
        return self.run.end_reason


@dataclass(frozen=True)
class PresetView:
    """생성 화면의 "○○를 바탕으로" 목록 한 줄 (§3-D10-1).

    **이름은 내보내되 바탕이 될 뿐이다** — 캐릭터 이름은 사용자가 따로 정한다.
    """

    source: str
    gender: Gender
    play_style: PlayStyle
    country_code: str
    """목록 밖 출신은 `OTHER`(기타)다 — 비워 두지 않는다 (§3-D10-1)."""


@dataclass(frozen=True)
class ModeView:
    """`GET /modes` 한 줄. **비로그인 허용 여부가 여기서 나온다**(§3-D8)."""

    code: str
    label: str
    weeks_per_tick: int
    ticks: int
    event_budget: int
    guest_allowed: bool


@dataclass(frozen=True)
class CareerLogPage:
    """커리어 로그 한 페이지 (§7 `GET /runs/{id}/log`)."""

    entries: tuple[WeekReportView, ...] = ()
    total: int = 0
    offset: int = 0

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.entries) < self.total


@dataclass(frozen=True)
class CareerSummary:
    """끝난 커리어의 요약. 은퇴 화면과 트로피 목록이 읽는다."""

    run: CareerRun
    titles_won: tuple[str, ...] = ()
    trophies: tuple[str, ...] = field(default_factory=tuple)
    grand_slam_level: int = 0
