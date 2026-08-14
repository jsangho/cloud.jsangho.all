"""세이브 하나 — 애그리거트 루트 (하네스 §5).

**불변이다.** 진행은 새 `CareerRun`을 만들어 돌려준다. 시드 고정 순수 함수로 판정하기로
한 이상(§3-D4) 상태를 제자리에서 바꾸면 재현이 깨진다. 저장은 진행 단위로 한 번이라
중간 상태가 DB로 새지도 않는다(§3-D6).

액트는 필드가 아니라 파생값이다. 저장하면 인기도와 어긋날 수 있고, 무엇보다 **액트는
내려갈 수도 있어야** 한다 — 인기도가 떨어지면 3에서 2로 돌아온다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from wwe_game.domain.constants.career_clock import CAREER_WEEKS, RETIREMENT_AGE
from wwe_game.domain.exceptions import InvalidCareerRunError, RunNotActiveError
from wwe_game.domain.value_objects.condition import HEALTHY, Condition
from wwe_game.domain.value_objects.contract import (
    DEBUT_CONTRACT_WEEKS,
    DEBUT_WEEKLY_PAY,
    Contract,
)
from wwe_game.domain.value_objects.game_mode import GameMode
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal
from wwe_game.domain.value_objects.team import Team
from wwe_game.domain.value_objects.title import TITLES, Brand, Title
from wwe_game.domain.value_objects.wrestler_identity import WrestlerIdentity
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

ACT2_POPULARITY = 30
ACT3_POPULARITY = 60
ACT4_AGE = 43
ACT4_AGE_POPULAR = 47
"""액트 경계. 수치 근거는 이벤트 덱 스키마 §3.

**인기도가 나이보다 우선한다**(2026-08-06 사용자 결정). 인기도 60 이상이면 황혼(액트 4)
진입이 43세에서 47세로 미뤄진다 — 관중이 찾는 선수는 나이로 밀려나지 않는다.

액트 4를 아예 인기도로 막지는 않는다. 고별사·횃불·명예의 전당이 거기 있어서, 못 가면
커리어를 끝맺는 카드를 영영 못 본다. 늦출 뿐 없애지 않는 이유다.
"""

HEAT_MIN = 0
HEAT_MAX = 100


class RunStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    """50세 만기로 끝났다. 커리어를 끝까지 살아낸 경우다."""
    RETIRED = "retired"
    """만기 전에 닫혔다 — 본인 선택·부진·중대 부상."""


class EndReason(StrEnum):
    AGE_50 = "age_50"
    PLAYER = "player"
    RELEASED = "released"
    """단체가 계약을 끊었다 — **사유가 둘이다**(§13-Q14).

    하나는 평판이 바닥나 못 참아 주는 것이고, 다른 하나는 35세를 넘겨 입지가
    무너진 것이다. 처음엔 뒤엣것을 `DECLINE`으로 따로 뒀는데 실측에서 한 번도
    발생하지 않았다 — 같은 사람을 노리는 두 규칙이라 방출이 늘 먼저 물었다.
    계약이 끊기는 사건은 하나이므로 엔딩도 하나로 모은다.
    """
    INJURY = "injury"
    FADED = "faded"
    """무소속으로 너무 오래 있었다 — **아무도 부르지 않아서 끝났다** (§3-D50).

    방출과 다르다. 방출은 이제 커리어를 닫지 않고 계약만 끊는다: 실제로 방출은
    다른 곳에서 다시 시작하는 계기이지 끝이 아니다. 끝나는 것은 그 뒤로도
    아무 오퍼가 오지 않았을 때다.
    """


class RivalryStage(StrEnum):
    INDIFFERENT = "indifferent"
    HEATED = "heated"
    NEMESIS = "nemesis"


@dataclass(frozen=True)
class Rivalry:
    """서사를 만드는 것은 여기다 (하네스 §2-D4)."""

    rival_name: str
    stage: RivalryStage
    heat: int
    started_week: int

    def __post_init__(self) -> None:
        if not HEAT_MIN <= self.heat <= HEAT_MAX:
            raise InvalidCareerRunError(
                f"heat는 {HEAT_MIN}~{HEAT_MAX} 범위여야 합니다: {self.heat}"
            )
        if self.started_week < 0:
            raise InvalidCareerRunError(
                f"started_week는 음수일 수 없습니다: {self.started_week}"
            )


@dataclass(frozen=True)
class EventInstance:
    """실제로 뽑혀 플레이어 앞에 놓인 이벤트. 있으면 진행이 막힌다 (§3-D2)."""

    code: str
    week: int
    body_index: int = 0
    """어느 본문 변주로 보여줄지. 같은 카드가 다시 떠도 다른 장면이 나온다."""
    rival_name: str | None = None


@dataclass(frozen=True)
class Trophy:
    code: str
    week: int


@dataclass(frozen=True)
class CareerRun:
    identity: WrestlerIdentity
    mode: GameMode
    seed: int
    id: int | None = None
    user_id: int | None = None
    """비로그인 체험판은 None이다 (§3-D8). 저장은 클라이언트가 한다."""
    week: int = 0
    stats: WrestlerStats = field(default_factory=WrestlerStats)
    condition: Condition = HEALTHY
    rivalries: tuple[Rivalry, ...] = ()
    pending_event: EventInstance | None = None
    seen_events: frozenset[str] = frozenset()
    recent_events: tuple[str, ...] = ()
    """쿨다운용 최근 이벤트 코드. 전체 이력은 `career_log_entries`에 있다."""
    flags: frozenset[str] = frozenset()
    """이벤트 선택이 남긴 표식 (덱 스키마 §6). `career_rules`가 읽는다 —
    `suspension_pending`은 방출 유예를 절반으로 줄이고, `painkiller_habit`은
    부상 굴림을 올린다. 카드가 아니라 규칙이 읽는 값이라 여기 산다."""
    events_fired: int = 0
    """지금까지 발동한 이벤트 수. **예산 계산의 분자다.**

    `seen_events`(once 카드)와 `recent_events`(최근 64개)로 세면 둘 다 포화해서
    예산이 영영 안 줄고 이벤트가 과하게 뜬다.
    """
    release_weeks: int = 0
    """백스테이지 평판이 방출 임계 아래에 머문 연속 주차 (§3-D24)."""
    decline_weeks: int = 0
    """입지가 임계 아래에 머문 연속 주차. 부진 은퇴의 유예 기간을 센다 (§3-D16).

    한 주 삐끗한 것과 반년째 밀려나는 것을 구분하려면 누적이 필요하다.
    """
    status: RunStatus = RunStatus.ACTIVE
    end_reason: EndReason | None = None
    trophies: tuple[Trophy, ...] = ()
    brand: Brand = Brand.NXT
    """소속 브랜드. **커리어는 NXT에서 시작해 콜업으로 올라간다** (스펙)."""
    titles_held: frozenset[Title] = frozenset()
    """지금 감고 있는 벨트."""
    titles_won: tuple[Title, ...] = ()
    """획득 이력을 **순서대로** 쌓는다. 집합이 아니라 튜플인 이유는 **횟수를 세야** 하기
    때문이다 — 더블 그랜드슬램은 각 그룹을 두 번씩 채운 것으로 판정한다(스펙)."""

    injured_parts: frozenset[str] = frozenset()
    """지금까지 다친 적 있는 부위 (§3-D43). **몸이 기억한다.**

    한 번 무너진 무릎은 다음에도 무릎이다 — 이력이 스타일보다 앞서 다음 부상의 자리를
    정하고, 재발한 부위는 회복이 더 오래 간다. 이게 없으면 부위는 숫자에 붙은 이름표에
    지나지 않는다.

    문자열로 두는 이유는 `flags`·`titles_held`와 같다 — JSON 칼럼에 그대로 실린다.
    """
    tournament_round: int = 0
    """킹 앤 퀸 오브 더 링에서 지금까지 이긴 라운드 수 (§3-D33). 0이면 참가 중이 아니다.

    **한 주에 안 끝나는 유일한 형식이라 상태가 필요하다.** 다른 경기는 그 주에 결판이
    나므로 리포트 하나로 끝나지만, 토너먼트는 "지난주에 이겼는가"를 다음 주가 알아야
    한다. 대회가 지나가면 이기든 지든 0으로 돌아간다 — 해마다 새로 연다.
    """
    title_shot: bool = False
    """레슬매니아 1선 도전권 — **럼블·챔버 우승이 준다** (§3-D36).

    레슬매니아 주차에 인기도 관문을 건너뛰고 월드 벨트를 건다. 그 밤이 지나면 이기든
    지든 사라진다 — 도전권은 한 번 쓰는 것이다.
    """
    briefcase_week: int = 0
    """머니 인 더 뱅크 가방을 딴 주차. 0이면 없다 (§3-D36).

    **불리언이 아니라 주차인 이유는 기한이 있어서다.** 처음엔 "쓸 때까지 안 사라진다"로
    뒀는데, 실측 20판 중 **17판이 가방을 든 채 은퇴했다** — 쓸지 말지 묻는 카드가 뜰
    확률이 낮아서다. 기한이 없으면 "언제든지 쓸 수 있는 권리"가 "대개 못 쓰는 권리"가 된다.

    `run.flags`가 아니라 여기 사는 이유: 표식은 **카드가 남기고 규칙이 읽는** 값이라는
    약속이 있고(§3-D26 · `test_the_rule_flags_are_not_also_card_conditions`), 가방은
    반대로 **규칙이 주고 카드가 읽는다.** 표식으로 만들면 그 감사가 깨진다.
    """

    money: int = 0
    """지금까지 번 돈에서 쓴 돈을 뺀 잔액(달러) (§3-D47).

    **쌓이기만 하는 값이 아니다** — 선택지가 비용을 물린다(§3-D48). 통산 수입을 따로
    두지 않는 이유: 화면이 묻는 것은 "지금 쓸 수 있는가"이고, 통산은 로그가 답한다.
    """
    contract: Contract | None = None
    """지금 맺고 있는 계약. **무소속이면 None이다** (§3-D50).

    방출은 이 값을 지우는 사건이지 커리어를 닫는 사건이 아니다.
    """
    unsigned_weeks: int = 0
    goal: QuarterGoal | None = None
    """지금 분기에 건 것 (§3-D80). `None`이면 아직 안 골랐다 — 진행이 막힌다."""
    goal_quarter: int = -1
    offer_week: int = 0
    """재계약 협상이 열린 주차 (§3-D84). 0이면 열려 있지 않다.

    **제시액을 저장하지 않는다** — 몸값은 그 주차의 상태에서 언제든 되짚을 수 있고
    (`contract_office.appraise`), 저장하면 세이브를 손댄 값과 규칙이 갈린다(§3-D8)."""
    """그 목표를 고른 분기 번호. **지난 목표는 남기지 않는다** — 그 분기에 무슨 일이
    있었는지는 뉴스가 이미 말한다."""
    """계약 없이 보낸 연속 주차 (§3-D50). 계약을 맺으면 0으로 돌아간다.

    `release_weeks`와 다른 값이다 — 저쪽은 **잘리기까지** 남은 인내를 세고, 이쪽은
    **잊히기까지** 남은 시간을 센다. 하나로 합치면 방출 직후가 곧 종료 직전이 된다.
    """

    team: Team | None = None
    """지금 속한 태그팀·스테이블 (§3-D30). 혼자면 None.

    표식(`in_tag_team`·`in_stable`)이 "팀에 있다"를 말한다면 이 값은 **누구와, 무슨
    이름으로**를 말한다. 둘을 나눠 두는 이유: 카드 조건은 표식만 보면 되고, 화면은
    이름이 필요하다.
    """

    def __post_init__(self) -> None:
        if not 0 <= self.week <= CAREER_WEEKS:
            raise InvalidCareerRunError(
                f"주차는 0~{CAREER_WEEKS} 범위여야 합니다: {self.week}"
            )
        # 끝난 커리어는 이유가 있어야 하고, 진행 중인 커리어는 이유가 없어야 한다.
        if (self.status is RunStatus.ACTIVE) != (self.end_reason is None):
            raise InvalidCareerRunError(
                f"status와 end_reason이 어긋납니다: {self.status}, {self.end_reason}"
            )
        if (
            self.status is RunStatus.COMPLETED
            and self.end_reason is not EndReason.AGE_50
        ):
            raise InvalidCareerRunError("COMPLETED는 만기(age_50)로만 도달합니다.")
        if self.pending_event is not None and self.status is not RunStatus.ACTIVE:
            raise InvalidCareerRunError(
                "끝난 커리어에 대기 이벤트가 남아 있을 수 없습니다."
            )
        # 감고 있는데 딴 적이 없는 벨트는 있을 수 없다. 조작된 체험판 상태를 여기서 막는다.
        never_won = self.titles_held - set(self.titles_won)
        if never_won:
            raise InvalidCareerRunError(
                f"보유 벨트가 획득 이력에 없습니다: {sorted(never_won)}"
            )
        # 다른 브랜드 벨트를 들고 있을 수 없다. 드래프트가 반납을 빠뜨리면 여기서 걸린다.
        misplaced = {
            t
            for t in self.titles_held
            if self.brand not in TITLES[t].brands
            or TITLES[t].gender is not self.identity.gender
        }
        if misplaced:
            raise InvalidCareerRunError(
                f"소속·디비전이 아닌 벨트를 보유 중입니다: {sorted(misplaced)}"
            )
        if self.money < 0:
            raise InvalidCareerRunError(f"잔액은 음수일 수 없습니다: {self.money}")
        if self.unsigned_weeks < 0:
            raise InvalidCareerRunError(
                f"무소속 주차는 음수일 수 없습니다: {self.unsigned_weeks}"
            )
        # 무소속이 벨트를 들고 있을 수는 없다. 계약 해지가 반납을 빠뜨리면 여기서 걸린다.
        if self.contract is None and self.titles_held:
            raise InvalidCareerRunError(
                f"무소속인데 벨트를 들고 있습니다: {sorted(self.titles_held)}"
            )
        # 계약이 있는데 무소속 주차가 쌓여 있을 수 없다 — 한쪽만 갱신하는 버그를 막는다.
        if self.contract is not None and self.unsigned_weeks:
            raise InvalidCareerRunError(
                f"계약이 있는데 무소속 주차가 남아 있습니다: {self.unsigned_weeks}"
            )

    # ── 파생값 ────────────────────────────────────────────────

    @property
    def age(self) -> int:
        return self.identity.age_at(self.week)

    @property
    def briefcase(self) -> bool:
        return self.briefcase_week > 0

    @property
    def act(self) -> int:
        """1 루키 · 2 미드카드 · 3 메인이벤터 · 4 황혼. 저장하지 않고 매번 계산한다.

        인기도가 높으면 황혼이 4년 늦게 온다 (`ACT4_AGE_POPULAR`).
        """
        popular = self.stats.popularity >= ACT3_POPULARITY
        if self.age >= (ACT4_AGE_POPULAR if popular else ACT4_AGE):
            return 4
        if popular:
            return 3
        if self.stats.popularity >= ACT2_POPULARITY:
            return 2
        return 1

    def won_count(self, title: Title) -> int:
        """그 벨트를 몇 번 감았는지. 더블 그랜드슬램 판정의 재료다."""
        return self.titles_won.count(title)

    @property
    def is_signed(self) -> bool:
        """단체와 계약이 있는가. 없으면 무소속이고 인디를 뛴다 (§3-D50)."""
        return self.contract is not None

    @property
    def is_active(self) -> bool:
        return self.status is RunStatus.ACTIVE

    @property
    def is_blocked(self) -> bool:
        """대기 이벤트가 있으면 '다음'이 막힌다 — 라우터가 409로 답한다 (§8)."""
        return self.pending_event is not None

    @property
    def weeks_remaining(self) -> int:
        return CAREER_WEEKS - self.week

    @property
    def ticks_elapsed(self) -> int:
        return self.week // self.mode.weeks_per_tick

    @property
    def is_at_retirement_age(self) -> bool:
        return self.age >= RETIREMENT_AGE

    # ── 상태 검사 ─────────────────────────────────────────────

    def require_active(self) -> None:
        """끝난 세이브 조작을 막는다. 검증이 아니라 상태 위반이라 409다 (§8)."""
        if not self.is_active:
            raise RunNotActiveError("이미 끝난 커리어입니다.")

    # ── 전이 ─────────────────────────────────────────────────
    #
    # 주차 시뮬·이벤트 추첨·선택 판정은 T3~T5의 도메인 서비스가 맡는다.
    # 여기 있는 것은 어떤 규칙에서도 같은 뜻인 최소 전이뿐이다.

    def evolve(self, **changes: object) -> CareerRun:
        """필드를 바꾼 새 세이브. `__post_init__`이 다시 불변식을 검사한다."""
        return replace(self, **changes)  # type: ignore[arg-type]

    def ended(self, reason: EndReason) -> CareerRun:
        """커리어를 닫는다. 대기 이벤트는 함께 지운다 — 답할 사람이 없어졌다."""
        self.require_active()
        status = (
            RunStatus.COMPLETED if reason is EndReason.AGE_50 else RunStatus.RETIRED
        )
        return replace(self, status=status, end_reason=reason, pending_event=None)


def start_run(
    *,
    identity: WrestlerIdentity,
    mode: GameMode,
    seed: int,
    user_id: int | None = None,
) -> CareerRun:
    """새 커리어. 20세 0주차에서 **육성 계약을 들고** 출발한다 (§3-D10 · §3-D47)."""
    return CareerRun(
        identity=identity,
        mode=mode,
        seed=seed,
        user_id=user_id,
        # **첫 분기는 그냥 뛴다** (§3-D80). 데뷔 첫날 커리어 목표를 세우는 선수는
        # 없고, 게임 쪽으로도 아무것도 모르는 채 고르라고 하면 그건 선택이 아니라
        # 제비뽑기다. 석 달을 살아 본 뒤 13주차에 처음 묻는다.
        goal=QuarterGoal.DRIFT,
        goal_quarter=0,
        contract=Contract(
            weekly_pay=DEBUT_WEEKLY_PAY,
            signed_week=0,
            ends_week=DEBUT_CONTRACT_WEEKS,
        ),
    )
