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

`StepMode`·`StopReason`은 여기서 정의하지 않고 도메인에서 가져온다 — 진행 루프가 순수
함수라 멈춘 이유를 도메인이 직접 정하고, 같은 열거형을 두 곳에 두면 값이 갈릴 때 어느
쪽이 맞는지 알 수 없다. 어댑터가 편히 쓰도록 이름만 여기로 다시 내보낸다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wwe_game.domain.constants.play_styles import KOREAN_STYLE_NAMES
from wwe_game.domain.entities.career_run import CareerRun, EndReason
from wwe_game.domain.services.news_feed import NewsItem
from wwe_game.domain.services.show_report import ShowReport
from wwe_game.domain.value_objects.advance_outcome import StepMode, StopReason
from wwe_game.domain.value_objects.ring_skills import breakdown
from wwe_game.domain.value_objects.title import Title
from wwe_game.domain.value_objects.week_report import WeekReport
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

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
class SetGoalCommand:
    """이번 분기에 걸 것을 정한다 (§3-D80). `ChooseCommand`와 따로 둔다 —
    이벤트 응답과 목표 선언은 성격이 반대라 한 명령으로 합치면 그 구분이 사라진다."""

    run_id: int
    user_id: int
    goal_code: str


@dataclass(frozen=True)
class GuestSetGoalCommand:
    """체험판의 분기 목표 (§3-D80·D8). 세이브를 통째로 받아 통째로 돌려준다."""

    run: CareerRun
    goal_code: str


@dataclass(frozen=True)
class AnswerOfferCommand:
    """재계약 협상에 답한다 (§3-D84). `SetGoalCommand`와 나란한 자리다 —
    둘 다 **먼저 정하는 것**이고, 둘 다 답하기 전에는 진행이 막힌다."""

    run_id: int
    user_id: int
    offer_code: str


@dataclass(frozen=True)
class GuestAnswerOfferCommand:
    """체험판의 재계약 협상 (§3-D84·D8)."""

    run: CareerRun
    offer_code: str


@dataclass(frozen=True)
class CashInCommand:
    """가방을 쓰기로 한다 (§3-D85).

    **답할 것이 없다** — 목표·협상과 달리 이건 멈춤이 아니라 상시 행동이라, 고를
    선택지가 아니라 "지금 한다"는 사실 하나뿐이다. 그래서 코드 필드가 없다.
    """

    run_id: int
    user_id: int


@dataclass(frozen=True)
class CallOutCommand:
    """그 사람에게 시비를 건다 (§3-D86). 상대 이름이 곧 선택이다."""

    run_id: int
    user_id: int
    rival_name: str


@dataclass(frozen=True)
class GuestCallOutCommand:
    """체험판의 시비 걸기 (§3-D86·D8)."""

    run: CareerRun
    rival_name: str


@dataclass(frozen=True)
class ChangeFinisherCommand:
    """피니셔를 바꾼다 (§3-D88).

    **두 갈래가 한 명령에 들어 있다** — 목록에서 고르면 `code`, 이름을 직접 지으면
    `name`. 둘 중 하나만 채워지고, 어느 쪽인지는 유스케이스가 아니라 **화면이
    먼저 정한다**(2026-08-14 사용자 결정).
    """

    run_id: int
    user_id: int
    code: str = ""
    name: str = ""
    hold: str = ""
    """지금 것을 그대로 쓰고 **다시 묻는 날만 미룬다** — `quarter`·`year`·`forever`.

    `code`·`name`보다 앞선다: 안 바꾸겠다는 선언이므로 함께 와도 이쪽이 이긴다."""


@dataclass(frozen=True)
class NameSignatureCommand:
    """시그니처 칸을 사거나 이름을 새긴다 (§3-D92).

    **셋이 한 명령에 들어 있다** — 칸 사기(`buy`) · 이름 새기기(`name`) · 이름 지우기
    (`drop`). 어느 쪽인지는 화면이 먼저 정하고 보낸다(§3-D88의 두 갈래와 같은 규약).
    """

    run_id: int
    user_id: int
    slot: int = 0
    name: str = ""
    buy: bool = False
    drop: bool = False


@dataclass(frozen=True)
class GuestNameSignatureCommand:
    """체험판의 시그니처 구매 (§3-D92·D8)."""

    run: CareerRun
    slot: int = 0
    name: str = ""
    buy: bool = False
    drop: bool = False


@dataclass(frozen=True)
class GuestChangeFinisherCommand:
    """체험판의 피니셔 교체 (§3-D88·D8)."""

    run: CareerRun
    code: str = ""
    name: str = ""
    hold: str = ""


@dataclass(frozen=True)
class GuestCashInCommand:
    """체험판의 가방 현금화 (§3-D85·D8)."""

    run: CareerRun


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
class GuestResumeCommand:
    """다시 열었을 때 **진행하지 않고 상태만 읽는다** — 로그인 쪽 `current()`의 짝이다.

    이게 없던 동안 화면은 재개에 `advance(tick)`를 대신 썼고, 그 대가가 셋이었다:
    새로고침 한 번이 한 틱(분기 모드면 12주)을 태웠고, 대기 이벤트가 있으면 409라
    화면이 세이브를 지웠으며, 진행하지 않아도 될 자리에서 규칙이 돌았다.
    """

    run: CareerRun


@dataclass(frozen=True)
class GuestChooseCommand:
    run: CareerRun
    choice_code: str


@dataclass(frozen=True)
class GuestReportCommand:
    """그 밤의 리포트를 체험판에서 (§3-D51).

    **세이브와 주차뿐이다.** 체험판에는 로그가 없어 리포트가 로그인 쪽처럼 그 주차
    기록을 되읽을 수 없다 — 세울 수 있는 것은 배경(벨트·그 무렵)이고, 그것은 시드와
    주차만으로 결정된다.
    """

    run: CareerRun
    week: int
    busy: tuple[str, ...] = ()
    """그날 이미 링에 오른 사람 — 내 상대다. 카드가 그를 두 번 세우지 않게 한다(§3-D52)."""
    stakes: tuple[Title, ...] = ()
    """그날 내가 도전한 벨트. 카드가 같은 벨트를 다시 걸지 않게 한다."""


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
    stats: WrestlerStats | None = None
    """그 주차 끝의 스탯 (§3-D39). 뉴스가 **인기도와 성향만** 읽는다.

    옛 로그 행에는 없다 — None이면 호출자가 최종 스탯으로 되돌아간다.
    """
    match_summary: str | None = None
    """탈락 경기의 한 줄 요약 (§3-D34).

    **리포트의 `sequence`와 나눠 둔다.** 진행 중인 주차는 비트 전체를 들고 있지만,
    다시 읽은 로그에는 이 한 줄만 남아 있다 — 화면이 두 경로에서 같은 값을 읽으려면
    비트가 없는 쪽에도 담길 자리가 필요하다.
    """

    @property
    def week(self) -> int:
        return self.report.week


@dataclass(frozen=True)
class ShowReportView:
    """그 밤의 리포트 (§3-D45). 도메인 값을 그대로 든다 — 조립은 도메인이 했다."""

    report: ShowReport


@dataclass(frozen=True)
class AdvanceResult:
    """'다음' 한 번의 결과. **여러 주차가 쌓일 수 있다**(§3-D17 `auto`)."""

    run: CareerRun
    weeks: tuple[WeekReportView, ...] = ()
    stop_reason: StopReason = StopReason.READY
    pending_event: PendingEventView | None = None

    @property
    def ended(self) -> bool:
        return self.stop_reason is StopReason.ENDED

    @property
    def end_reason(self) -> EndReason | None:
        return self.run.end_reason


@dataclass(frozen=True)
class StatsView:
    """화면이 그리는 스탯 한 벌 (2026-08-10 사용자 요청).

    **경기력만 속이 열린다** — `skills`가 파워·스피드·운영과 스타일 전용 축을
    (이름, 값)으로 들고 있고, 화면은 그걸 드롭다운으로 편다(§3-D29).

    내부 확률이나 주사위 값은 여기 오지 않는다(§11-14).
    """

    popularity: int
    in_ring: int
    mic_work: int
    backstage: int
    alignment: int
    wear: int
    play_style: PlayStyle
    play_style_label: str
    skills: tuple[tuple[str, int], ...]

    @classmethod
    def of(cls, run: CareerRun) -> StatsView:
        style = run.identity.play_style
        return cls(
            popularity=run.stats.popularity,
            in_ring=run.stats.in_ring,
            mic_work=run.stats.mic_work,
            backstage=run.stats.backstage,
            alignment=run.stats.alignment,
            wear=run.condition.wear,
            play_style=style,
            play_style_label=KOREAN_STYLE_NAMES[style],
            skills=breakdown(run.stats.in_ring, style).as_pairs,
        )


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
    seed: int = 0
    """그 커리어의 시드 (§3-D56). **별점을 되짚는 데 쓴다** — 별점은 저장하지 않고
    그 밤의 재료로 매번 계산하므로, 로그를 다시 열 때도 시드가 필요하다."""

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.entries) < self.total


@dataclass(frozen=True)
class NewsFeedPage:
    """내 세계선의 뉴스 한 페이지 (2026-08-10 사용자 지시 10번 · §3-D31).

    로그와 따로 두는 이유는 담는 것이 달라서다 — 로그는 **모든** 주차이고 뉴스는
    남을 만한 사건만이다. `weekly` 한 판이 1560주라 로그를 그대로 펼치면 읽을 수 없다.

    각 항목이 **군중 반응**을 함께 들고 온다(`mood` · `crowd_line`). 화면은 `mood`로
    색을 고르고 `crowd_line`을 헤드라인 아래에 붙인다.
    """

    items: tuple[NewsItem, ...] = ()
    total: int = 0
    offset: int = 0
    seed: int = 0
    """그 커리어의 시드 (§3-D87). **기사를 되짚는 데 쓴다** — 매체·본문 변주·댓글은
    저장하지 않고 매번 세우므로, 뉴스를 다시 열 때도 시드가 필요하다.
    `CareerLogPage.seed`가 별점 때문에 같은 자리에 있다(§3-D56)."""

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @property
    def by_year(self) -> tuple[tuple[int, tuple[NewsItem, ...]], ...]:
        """연도별로 묶은 것. 서른 해치를 한 줄로 늘어놓으면 어디가 어디인지 모른다."""
        years: dict[int, list[NewsItem]] = {}
        for item in self.items:
            years.setdefault(item.year, []).append(item)
        return tuple((year, tuple(rows)) for year, rows in sorted(years.items()))


@dataclass(frozen=True)
class CareerSummary:
    """끝난 커리어의 요약. 은퇴 화면과 트로피 목록이 읽는다."""

    run: CareerRun
    titles_won: tuple[str, ...] = ()
    trophies: tuple[str, ...] = field(default_factory=tuple)
    grand_slam_level: int = 0
