"""커리어 샌드박스의 **상태와 설정**. 규칙은 여기 없다 — 모양만 있다.

## 왜 저장하는데도 안 터지는가

이전 커리어 시뮬레이터(`wwe_game`)는 38,326줄로 불어나 버려졌다(`f7a678f`,
2026-09-28). 해부한 결과 원인은 둘이었다 — **`career_runs` 테이블**이 생기자
세이브·불러오기·버전 호환·진행도·트로피가 따라왔고, **이벤트 카드 덱 18,994줄**이
얹혔다.

이번에는 저장을 한다(사용자 요구 — 재접속 복구·은퇴 기록 보존). 그래서 **터진
곳을 구조로 막는다**:

1. **규칙은 순수 함수다.** 이 패키지는 `sqlalchemy`·`fastapi`를 import 하지 않고
   앞으로도 하지 않는다. 저장 계층은 아래 `WorldState` 를 **통째로 스냅샷**할 뿐
   규칙을 모른다. 그래서 "저장 때문에 규칙이 불어나는" 경로가 없다.
2. **덱을 만들지 않는다.** 사건은 카드가 아니라 조건식에서 나온다
   (`career_events`). 덱이 없으면 "이벤트 하나 더" 가 파일 하나 더가 되지 않는다.
3. **멱등 키 하나로 중복을 막는다.** 주차 진행·시즌 결산·나이 증가·선택 해결·
   은퇴 확정이 전부 `WorldState.applied` 한 집합을 쓴다. 중복 방지 코드를
   기능마다 따로 쓰지 않는다 — 그게 지난번에 불어난 방식이다.

## 게임 안 시간과 실제 시간을 섞지 않는다

**나이는 게임 안 값이다**(`Wrestler.age`). 실제 생년월일에서 계산하지 않는다 —
`match_sim` 쪽 장난감은 로스터의 실제 생일을 쓰지만(`_age_on`), 커리어는 시즌을
넘기며 늙어야 하므로 실제 달력과 무관해야 한다. 한 시즌(52주)이 **1년**이고,
나이는 시즌 결산에서만 오른다(`career_season`). 그래서 주차 진행이 몇 번
재시도되어도 나이는 움직이지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: 한 시즌의 주차. **52주가 1년**이고 그래서 나이가 시즌당 1 오른다.
#:
#: 기본값일 뿐이다 — 실제로 쓰이는 값은 `Balance.season_weeks` 다. 상수를 직접
#: 읽는 코드를 두지 않는다(그러면 설정이 설정이 아니게 된다).
SEASON_WEEKS = 52

#: 주당 행동 포인트 기본값. 밸런스는 `Balance` 에서 조정한다.
ACTION_POINTS = 2


class Status(StrEnum):
    """선수의 **활동 상태**. 나이·부상과 독립된 축이다.

    `RETIREMENT_PENDING` 이 `RETIRED` 와 갈라져 있는 것이 핵심이다 — 은퇴
    **의사**는 확정이 아니다(사용자 요구 §3.1). 의사만 있는 선수는 계속 경기한다.
    """

    ACTIVE = "active"
    INJURED = "injured"
    RETIREMENT_PENDING = "retirement_pending"
    RETIRED = "retired"


#: 대진에 설 수 있는 상태. **은퇴·부상은 빠진다.**
BOOKABLE = (Status.ACTIVE, Status.RETIREMENT_PENDING)


class RetirementCause(StrEnum):
    """은퇴 **원인**. 단일 조건이 아니라 유형이 여럿이다(사용자 요구 §3.1).

    `REQUESTED` 와 `OFFER_ACCEPTED` 가 갈라져 있다 — 선수가 스스로 요청한 것과,
    게임이 제안해서 플레이어가 받아들인 것은 같은 사건이 아니다.
    """

    AGE_DECLINE = "age_decline"
    REPEATED_INJURY = "repeated_injury"
    SEVERE_INJURY = "severe_injury"
    MEDICAL = "medical"
    VOLUNTARY = "voluntary"
    POOR_FORM = "poor_form"
    GOAL_COMPLETE = "goal_complete"
    REQUESTED = "requested"
    OFFER_ACCEPTED = "offer_accepted"


class Severity(StrEnum):
    """부상 심각도. 회복 기간·능력치 영향·은퇴 위험이 여기서 갈린다."""

    MINOR = "minor"
    SERIOUS = "serious"
    CAREER_THREATENING = "career_threatening"


class RelationKind(StrEnum):
    RIVAL = "rival"
    ALLY = "ally"
    TAG_TEAM = "tag_team"
    MENTOR = "mentor"
    PROTEGE = "protege"


class Alignment(StrEnum):
    FACE = "face"
    HEEL = "heel"


@dataclass(frozen=True)
class Balance:
    """**밸런스 설정 한 곳.** 임계값·확률을 코드에 흩어 두지 않는다.

    사용자 요구 §3.2 — "확률 기반 로직을 사용하는 경우 임계값과 확률은 설정값으로
    관리한다." 그래서 규칙 함수는 전부 `balance` 를 인수로 받는다. 테스트가 수치를
    바꿔 끼울 수 있고, 시즌 길이도 이 안에 있다.
    """

    #: 시즌 길이. **52주가 기본이고 설정으로 바꿀 수 있다**(사용자 요구 §1).
    season_weeks: int = SEASON_WEEKS
    action_points: int = ACTION_POINTS

    # ── 인기도 ────────────────────────────────────────────────
    min_popularity: int = 10
    max_popularity: int = 100
    promotion_popularity: int = 55

    # ── 나이 ─────────────────────────────────────────────────
    #: 이 나이부터 체력·회복력이 깎이기 시작한다. **능력치 일괄 하락이 아니다** —
    #: 기술·마이크는 경험으로 계속 오른다(사용자 요구 §2).
    decline_age: int = 33
    #: 데뷔 가능 나이 범위.
    min_debut_age: int = 18
    max_debut_age: int = 40

    # ── 부상 ─────────────────────────────────────────────────
    #: 심각도별 결장 주차 범위.
    out_weeks: tuple[tuple[int, int], ...] = (
        (1, 3),  # minor
        (4, 10),  # serious
        (12, 30),  # career_threatening
    )
    #: 같은 부위를 다시 다칠 확률 가중. 누적 부상이 많으면 재발이 잦다.
    recurrence_weight: float = 0.35

    # ── 은퇴 위험 ─────────────────────────────────────────────
    #: 밴드 경계. 점수는 0~1 로 정규화된다.
    risk_caution: float = 0.40
    risk_high: float = 0.65
    #: 사건을 열기 시작하는 점수. **이 값을 넘어도 은퇴가 아니다** — 사건이 열릴
    #: 뿐이고 확정은 플레이어 선택이나 별도 확정 절차를 거친다(§3.2).
    risk_event_floor: float = 0.45
    #: 자동 은퇴가 가능한 최소 점수. 여기에 **더해** 의사까지 있어야 한다.
    #: 단일 요소로 은퇴가 확정되지 않게 만드는 둘째 자물쇠다.
    risk_auto_floor: float = 0.85
    #: 성적 부진 판정 — 최근 이만큼 연패하면 부진으로 센다.
    poor_form_losses: int = 6

    def season_of(self, absolute_week: int) -> int:
        """절대 주차를 시즌 번호로. 1-based 둘 다."""
        return (absolute_week - 1) // self.season_weeks + 1


@dataclass(frozen=True)
class Ability:
    """능력치 넷. **노화가 일괄로 깎지 않는다**(사용자 요구 §2).

    `in_ring`·`mic` 는 경험으로 오르고, `stamina`·`resilience` 는 나이와 부상으로
    내린다. 그래서 노장은 "약한 선수" 가 아니라 **다른 선수**다 — 잘하지만 쉽게
    지치고 늦게 회복한다.
    """

    in_ring: int = 40
    mic: int = 40
    stamina: int = 70
    resilience: int = 70

    def clamped(self) -> Ability:
        def c(v: int) -> int:
            return max(1, min(100, v))

        return Ability(
            in_ring=c(self.in_ring),
            mic=c(self.mic),
            stamina=c(self.stamina),
            resilience=c(self.resilience),
        )


@dataclass(frozen=True)
class AbilitySnapshot:
    """시즌 끝의 능력치. **추이를 보여 주려고 남긴다**(사용자 요구 §6 대시보드)."""

    season: int
    age: int
    ability: Ability


@dataclass(frozen=True)
class Injury:
    """부상 하나. **결장으로 끝나지 않는다** — 이력이 은퇴 위험에 들어간다(§3.3)."""

    kind: str
    severity: str
    season: int
    week: int
    weeks_out: int
    #: 회복 완료 여부. 결장이 끝나면 True.
    recovered: bool = False
    #: 같은 부위 재발인가. 재발은 위험 평가에서 더 무겁다.
    recurrence: bool = False
    #: 영구 활동 불가. True 면 복귀 선택지가 아예 열리지 않는다(§4).
    permanent: bool = False


@dataclass(frozen=True)
class RetirementIntent:
    """은퇴 **의사**. 확정이 아니다(사용자 요구 §3.1 · §3.4).

    `origin` 이 둘을 가른다 — `self` 는 선수가 스스로 은퇴를 요청한 것이고,
    `offered` 는 게임이 "결정하라" 고 제안한 것이다. 같은 상태로 묶으면 화면이
    "선수가 그만두고 싶어 한다" 와 "결정할 때가 됐다" 를 구별할 수 없다.
    """

    origin: str
    cause: str
    season: int
    week: int
    #: "마지막 시즌 선언" — 이 시즌 끝에 은퇴한다는 의사.
    final_season: bool = False


@dataclass(frozen=True)
class Retirement:
    """은퇴 **확정**. 선수당 한 번만 생긴다(멱등 키가 지킨다).

    당시 수치를 **복사해서** 들고 있다. 은퇴 선수 프로필이 현재 로스터 값을 다시
    읽으면, 나중에 규칙이 바뀌었을 때 과거 기록이 소급해 바뀐다(사용자 요구 §5 —
    "은퇴 당시 나이·전적·주요 타이틀을 기록").
    """

    cause: str
    season: int
    week: int
    age: int
    wins: int
    losses: int
    #: 은퇴 당시 보유했던 벨트 — 공석 처리 전 모습.
    held: tuple[str, ...] = ()
    #: 역대 획득 수.
    reigns: int = 0
    titles: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Wrestler:
    """로스터 한 명. 플레이어도 NPC도 같은 모양이다.

    같은 모양인 것은 결정이다 — 은퇴·부상·관계 규칙을 플레이어와 NPC에 두 번
    쓰지 않기 위해서다. 다른 점은 `is_player` 한 칸뿐이다.
    """

    name: str
    style: str
    brand: str = "NXT"
    age: int = 24
    #: **커리어 시작 시 나이.** 시즌이 지나도 바뀌지 않는다(사용자 요구 §2).
    debut_age: int = 24
    alignment: str = Alignment.FACE
    popularity: int = 20
    ability: Ability = field(default_factory=Ability)
    #: 컨디션 0~100. 부상과 **다른 축**이다 — 지쳤을 뿐 출전은 할 수 있다.
    condition: int = 80
    status: str = Status.ACTIVE
    wins: int = 0
    losses: int = 0
    #: 역대 획득 기록. 같은 벨트를 여러 번 들면 여러 번 들어간다.
    reigns: tuple[str, ...] = ()
    #: 지금 들고 있는 벨트.
    held: tuple[str, ...] = ()
    injuries: tuple[Injury, ...] = ()
    out_weeks: int = 0
    #: 연속 패배. 성적 부진 판정에 쓴다.
    #:
    #: **경기 기록이 아니다** — 악역 전환(`heel_turn`)이 0으로 되돌린다. 그래서
    #: 연승·연패 기록을 이 칸에서 거꾸로 셈하지 않는다.
    losing_streak: int = 0
    #: 현재 연승. 경기 결과로만 움직인다(`career_engine._apply_outcome`).
    win_streak: int = 0
    #: 최장 연승. 줄지 않는다.
    best_win_streak: int = 0
    #: 위 두 칸을 **언제부터 셌는가** — `(시즌, 주차)`. `None` 이면 데뷔부터 빠짐없이
    #: 센 값이다.
    #:
    #: v1 세이브에는 연승 칸이 없었다. 옛 경기를 로그로 다시 셀 수 없는 선수는
    #: 업그레이드 시점부터 0으로 세기 시작하고 그 시점을 여기 적는다
    #: (`career_world_codec._upgrade_v1_to_v2`). **추정해서 채우지 않는다** — 이 칸이
    #: 있으면 화면은 "그 이후 집계" 라고 적어야 한다.
    streaks_since: tuple[int, int] | None = None
    #: 최근 연속 출전 주차. 경기 부담이 은퇴 위험에 들어간다(§3.2).
    consecutive_matches: int = 0
    trend: tuple[AbilitySnapshot, ...] = ()
    intent: RetirementIntent | None = None
    retirement: Retirement | None = None
    is_player: bool = False

    @property
    def retired(self) -> bool:
        return self.status == Status.RETIRED

    @property
    def match_count(self) -> int:
        """총 경기 수. **저장하지 않는다** — 경기마다 `wins` 나 `losses` 중 정확히
        하나가 오르므로(무승부가 없다) 합이 곧 경기 수이고, v1 세이브에서도 정확하다.

        무승부·무효 경기가 생기면 이 등식이 깨진다. 그때 저장 칸으로 바꾼다.
        """
        return self.wins + self.losses

    @property
    def bookable(self) -> bool:
        """대진에 설 수 있는가. **은퇴·부상은 빠진다**(사용자 요구 §3.4)."""
        return self.status in BOOKABLE and self.out_weeks <= 0

    @property
    def serious_injuries(self) -> int:
        return sum(
            1
            for i in self.injuries
            if i.severity in (Severity.SERIOUS, Severity.CAREER_THREATENING)
        )

    @property
    def permanently_out(self) -> bool:
        """의학적 영구 불가. 복귀 선택지를 열지 않는다(§4)."""
        return any(i.permanent for i in self.injuries)


@dataclass(frozen=True)
class Relationship:
    """관계 하나. **방향이 있다** — `a` 가 `b` 를 어떻게 보는가.

    양방향으로 저장하지 않는다. 배신이 비대칭이기 때문이다 — 배신한 쪽은 동맹으로
    알고 있고 당한 쪽은 라이벌이 된다. 한 줄로 묶으면 그 비대칭을 못 적는다.
    """

    a: str
    b: str
    kind: str
    #: -100(증오) ~ 100(신뢰). `kind` 와 독립이다 — 라이벌의 heat 는 적대의 크기다.
    heat: int = 0
    started_week: int = 1
    last_week: int = 1
    #: 상태 변경 이력 — "동맹이었다가 배신당했다" 를 화면이 적을 수 있어야 한다.
    history: tuple[str, ...] = ()

    def involves(self, name: str) -> bool:
        return name in (self.a, self.b)

    def other(self, name: str) -> str:
        return self.b if self.a == name else self.a


@dataclass(frozen=True)
class Title:
    """벨트 하나. **공석이 정상 상태다** — 은퇴한 챔피언의 벨트가 여기로 온다."""

    name: str
    brand: str
    #: 요구 인기도 — 사다리의 단계를 이 값이 만든다.
    required_popularity: int
    holder: str | None = None
    defenses: int = 0
    #: 현 재위가 시작된 절대 주차. 재위 기간을 여기서 센다.
    won_week: int | None = None

    @property
    def vacant(self) -> bool:
        return self.holder is None


@dataclass(frozen=True)
class Choice:
    """사건의 선택지 하나."""

    code: str
    label: str
    #: 고를 수 있는가. 규칙상 불가능한 선택지는 **지우지 않고 막는다** — 왜 못
    #: 고르는지 화면이 적을 수 있어야 한다(사용자 요구 §6 사건 화면).
    enabled: bool = True
    #: 못 고르는 이유, 또는 고르면 어떻게 되는지.
    note: str = ""


@dataclass(frozen=True)
class PendingEvent:
    """해결되지 않은 사건. **같은 사건을 두 번 해결할 수 없다**(`id` 가 멱등 키).

    `kind` 가 은퇴 계열이면 선택지에 은퇴 확정이 들어 있을 수 있다. 그래도
    **사건이 은퇴를 시키지 않는다** — 확정은 `career_retirement.confirm` 하나다.
    """

    id: str
    kind: str
    season: int
    week: int
    subject: str
    #: 상대가 있는 사건이면 그 이름.
    other: str | None = None
    headline: str = ""
    detail: str = ""
    choices: tuple[Choice, ...] = ()


@dataclass(frozen=True)
class LogEntry:
    """커리어 로그 한 줄. **사실만 적는다** — 문장은 화면이 만든다.

    서술 템플릿 뱅크를 두지 않는다. 지난번 붕괴의 18,994줄이 그 자리였다.
    """

    season: int
    week: int
    kind: str
    subject: str
    #: 화면이 조립할 수 있는 요약. 사실의 나열이고 산문이 아니다.
    summary: str = ""
    other: str | None = None
    result: str | None = None
    title: str | None = None


#: 경기 기록의 전후 상태 배열이 담는 칸과 **그 순서**. 저장 형식이다 — 순서를
#: 바꾸거나 칸을 끼워 넣으면 옛 기록의 숫자가 다른 뜻으로 읽힌다. 바꿀 때는 판본을
#: 올리고 업그레이드를 쓴다. 칸을 늘리려면 **끝에만** 붙이고 역시 판본을 올린다.
#:
#:     0 popularity  1 condition  2 wins  3 losses  4 win_streak  5 losing_streak
STATE_FIELDS: tuple[str, ...] = (
    "popularity",
    "condition",
    "wins",
    "losses",
    "win_streak",
    "losing_streak",
)


@dataclass(frozen=True)
class ParticipantRecord:
    """경기 참가자 한 명의 기록. **이름이 열쇠가 아니라 목록의 한 줄이다.**

    이 도메인에는 선수 ID 가 없고 이름이 사실상의 키다(관계·벨트·`find` 모두).
    이름을 dict 키로 쓰면 동명이인이 한 칸을 덮어쓰므로 목록으로 둔다 — 그래도
    이름이 같은 두 선수를 **구별해 주지는 못한다.** 코덱이 한 기록 안의 이름이
    서로 다른지 검사한다(2026-11-03 실측: 운영 세계 셋 모두 동명이인 0명).
    """

    name: str
    #: `MatchRecord.teams` 의 몇 번째 팀인가. 0 은 항상 플레이어 쪽이다.
    side: int
    #: 경기력의 가중 세 항 — `career_match.PowerParts` 의 (skill, draw, body).
    #: 시뮬레이션이 **실제로 쓴** 값이다(결과 반영 전 상태로 계산).
    power: tuple[float, float, float]
    #: `STATE_FIELDS` 순서의 값. 결과 반영 **직전**.
    before: tuple[int, ...]
    #: `STATE_FIELDS` 순서의 값. 결과 반영과 부상 판정 **직후**, 주차 마감(목표
    #: 보상) **전**.
    after: tuple[int, ...]


@dataclass(frozen=True)
class HeatChange:
    """경기가 움직인 관계 하나. 방향이 있다(`Relationship` 과 같이 `a → b`)."""

    a: str
    b: str
    #: 경기 전 heat. 관계가 없었으면 `None` — 이 경기로 관계가 **생긴** 것이다.
    before: int | None
    after: int


@dataclass(frozen=True)
class MatchRecord:
    """경기 하나의 **불변 기록.** 엔진이 경기 직후 한 번 만들고 아무도 고치지 않는다.

    값은 전부 **이미 계산된 것을 옮긴 것**이다 — `MatchOutcome` · `Card` ·
    `WeekReport` · 결과 반영 전후의 로스터. 기록을 만들면서 뽑기를 하거나 다시
    계산하지 않는다(골든이 지킨다).

    ## 승자를 가리키는 칸 넷

        winner_side  이긴 **팀**. 승패의 정본이다
        finisher     시뮬레이션이 승리를 **귀속시킨 개인**(`MatchOutcome.winner`).
                     싱글은 이긴 선수, 태그는 이긴 팀의 득점자 — 엔진 규칙이다
        scorer       핀폴일 때만. 핀을 딴 선수
        pinned       핀폴일 때만. 핀을 당한 선수

    서브미션·반칙승·카운트아웃·레프리 스톱에는 "핀을 딴 선수" 가 없다. 그래서
    `scorer`·`pinned` 는 그 경기들에서 `None` 이고 **추정해서 채우지 않는다.**

    ## 태그전 전적

    팀 전원이 팀 결과대로 1승 또는 1패를 받는다 — `after` 도 그렇다. 핀을 따고 당한
    개인은 `scorer`·`pinned` 가 따로 든다. 전적과 달리 **피로는 한 명만 받는다**
    (`career_engine._apply_outcome`) — 밸런스 판단이라 전적 수정과 갈라 뒀다.
    """

    id: str
    season: int
    week: int
    #: 경기 시점의 플레이어 브랜드. **쇼가 아니다** — 쇼 개념은 아직 없다.
    brand: str
    #: `MatchOutcome.kind` — single · title · tag.
    kind: str
    #: 대진 사유 — `Card.note`(일반 경기 · 라이벌전 · 도전 · 방어전 · 태그팀).
    reason: str
    title: str | None
    title_changed: bool
    #: `(플레이어 팀, 상대 팀)`. 싱글은 한 명씩.
    teams: tuple[tuple[str, ...], tuple[str, ...]]
    winner_side: int
    #: 플레이어 팀(`teams[0]`)의 경기 전 승리 확률 — `WeekReport.probability` 와 같다.
    probability: float
    finish: str
    rating: int
    finisher: str | None
    scorer: str | None
    pinned: str | None
    participants: tuple[ParticipantRecord, ...]
    heat: tuple[HeatChange, ...] = ()
    #: 이 경기로 플레이어가 입은 부상. NPC 는 경기로 다치지 않는다(엔진 규칙).
    injury: Injury | None = None
    #: 엔진이 계산한 인기도 변화 — `WeekReport.popularity_delta` 와 같다. 상한·하한에
    #: 걸리면 실제 변화(`after - before`)가 이보다 작다.
    popularity_delta: int = 0


@dataclass(frozen=True)
class SeasonSummary:
    """시즌 결산 한 장. **결산은 한 번만 생긴다**(멱등 키)."""

    season: int
    wins: int
    losses: int
    #: 시즌 종료 당시 나이 — 결산이 나이를 올리기 **전** 값이다.
    age: int
    ability: Ability
    #: 시즌 중 능력치 변화.
    ability_delta: Ability
    titles_won: tuple[str, ...] = ()
    defenses: int = 0
    injuries: int = 0
    #: 시즌 중 은퇴한 선수들.
    retired: tuple[str, ...] = ()
    #: 시즌의 주요 순간 — 로그에서 뽑은 것이다.
    highlights: tuple[str, ...] = ()
    risk_band: str = ""


class Phase(StrEnum):
    """시즌의 단계. **결산과 다음 시즌 시작이 갈라져 있다**(사용자 요구 §1).

    한 호출로 묶으면 "결산만 보고 아직 다음 시즌은 시작 안 함" 상태를 표현할 수
    없고, 중복 실행 방지도 두 곳에 써야 한다.
    """

    IN_SEASON = "in_season"
    #: 52주를 처리했고 결산을 기다린다. 주차 진행이 막힌다.
    SETTLEMENT = "settlement"
    #: 결산이 끝났고 다음 시즌 시작을 기다린다.
    OFFSEASON = "offseason"
    #: 플레이어가 은퇴했다. 세계는 남지만 진행이 멈춘다.
    ENDED = "ended"


@dataclass(frozen=True)
class WorldState:
    """**세계 하나의 전부.** 저장 계층은 이걸 통째로 스냅샷한다.

    `applied` 가 중복 방지의 전부다 — 주차 진행·결산·나이·선택 해결·은퇴 확정이
    전부 키를 하나 넣고 들어온다. 키가 이미 있으면 **아무 일도 일어나지 않는다.**
    기능마다 중복 방지 코드를 따로 쓰지 않는 이유이고, 재시도·동시 요청이
    안전한 이유다.
    """

    #: 결정론의 뿌리. 같은 시드·같은 입력이면 같은 결과다(사용자 요구 §7).
    seed: int
    player: str
    season: int = 1
    week: int = 1
    phase: str = Phase.IN_SEASON
    action_points: int = ACTION_POINTS
    roster: tuple[Wrestler, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    titles: tuple[Title, ...] = ()
    pending: tuple[PendingEvent, ...] = ()
    log: tuple[LogEntry, ...] = ()
    seasons: tuple[SeasonSummary, ...] = ()
    #: 플레이어 경기 기록. 오래된 것부터 잘린다(`career_match_record.MAX_MATCH_RECORDS`).
    matches: tuple[MatchRecord, ...] = ()
    #: **기록이 언제부터 있는가** — `(시즌, 주차)`. `None` 이면 데뷔부터 빠짐없이
    #: 기록했다(새 커리어). 값이 있으면 그 주차 **이전** 경기는 기록 도입 전이라
    #: 기록이 없다 — 세이브 v2 → v3 업그레이드가 그 시점의 주차를 적는다.
    #:
    #: 기록이 없는 경기의 사유는 `career_match_record.missing_reason` 이 가른다:
    #: 이 값 이전이면 "도입 전", 남은 가장 오래된 기록보다 이전이면 "보존 상한으로
    #: 잘림".
    match_records_since: tuple[int, int] | None = None
    #: 이미 적용한 연산의 키. **중복 적용을 막는 유일한 장치.**
    applied: frozenset[str] = frozenset()

    def find(self, name: str) -> Wrestler | None:
        for w in self.roster:
            if w.name == name:
                return w
        return None

    def require(self, name: str) -> Wrestler:
        found = self.find(name)
        if found is None:
            raise KeyError(f"로스터에 없는 선수: {name}")
        return found

    @property
    def hero(self) -> Wrestler:
        """플레이어 선수. 세계에 반드시 하나 있다."""
        return self.require(self.player)

    def relations_of(self, name: str) -> tuple[Relationship, ...]:
        return tuple(r for r in self.relationships if r.involves(name))

    def title_held_by(self, name: str) -> tuple[Title, ...]:
        return tuple(t for t in self.titles if t.holder == name)

    @property
    def retired_roster(self) -> tuple[Wrestler, ...]:
        """은퇴 선수 명부. **지우지 않으므로 항상 조회된다**(사용자 요구 §5)."""
        return tuple(w for w in self.roster if w.retired)
