"""HTTP 경계의 Pydantic 스키마 (하네스 §7).

**응답에 내부 수치를 담지 않는다**(§11-14). 선택지의 `risk`·`injury_risk`, 주사위 값,
확률 상수는 전부 빠진다 — 그대로 내보내면 최적해가 드러나 '고르는 재미'가 사라진다.

JSON은 camelCase, 도메인은 snake_case다. 변환은 **이 경계에서만** 일어난다 — 덱 로더가
`_STAT_KEYS`로 같은 일을 하는 것과 같은 규약이다(§3-D19).
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field
from wwe_game.adapter.inbound.api.schemas.guest_schema import GuestRunState, to_state
from wwe_game.app.dtos.career_dto import (
    AdvanceResult,
    CareerLogPage,
    ModeView,
    NewsFeedPage,
    PresetView,
    StatsView,
    WeekReportView,
)
from wwe_game.domain.constants import career_flags as flags
from wwe_game.domain.constants import career_rules as rules
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.play_styles import KOREAN_STYLE_NAMES
from wwe_game.domain.constants.ple_calendar import calendar_for, date_of
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.entities.career_run import CareerRun
from wwe_game.domain.services import (
    briefcase_desk,
    contract_desk,
    contract_office,
    elimination,
    finisher_desk,
    match_rating,
    news_article,
    quarter_plan,
    rivalry_desk,
    rivalry_engine,
    show_report,
    signature_desk,
    staff_scene,
    week_simulation,
)
from wwe_game.domain.services.news_feed import NewsItem
from wwe_game.domain.services.show_report import ShowReport
from wwe_game.domain.value_objects.body_part import PARTS, BodyPart
from wwe_game.domain.value_objects.finisher import (
    CUSTOM_CODE,
    NAME_MAX_LEN,
    NAME_MIN_LEN,
)
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.match_kind import format_of as match_format_of
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal
from wwe_game.domain.value_objects.title import (
    GRAND_SLAM_GROUPS,
    TITLES,
    Title,
    grand_slam_level,
    group_counts,
)
from wwe_game.domain.value_objects.week_report import WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda name: "".join(
            part if i == 0 else part.capitalize()
            for i, part in enumerate(name.split("_"))
        ),
        populate_by_name=True,
    )


# ── 요청 ─────────────────────────────────────────────────────


class StartRunRequest(_Camel):
    """새 커리어. **나이는 받지 않는다** — 20세 고정이다(§3-D10)."""

    name: str
    mode: str
    based_on: str | None = None
    """바탕으로 삼을 실존 선수. 나머지 셋의 기본값이 된다(§3-D10-1)."""
    gender: str | None = None
    country: str | None = None
    play_style: str | None = None


class AdvanceRequest(_Camel):
    step: str = "auto"
    """`auto`(기본) = 이벤트를 만날 때까지 · `tick` = 정확히 한 틱 (§3-D17)."""


class ChoiceRequest(_Camel):
    choice: str


# ── 응답 ─────────────────────────────────────────────────────


class ChoiceSchema(_Camel):
    code: str
    label: str


class PendingEventSchema(_Camel):
    code: str
    title: str
    body: str
    choices: list[ChoiceSchema]


class BeatSchema(_Camel):
    """경기 진행 한 마디 — 입장 하나, 탈락 하나 (§3-D34)."""

    kind: str
    """`enter` · `eliminate` · `win`."""
    name: str
    number: int = 0
    """입장 순번. `enter`에만 채워진다."""
    by: str | None = None
    """누가 탈락시켰는가(`eliminate`) · 무슨 기술로 끝냈는가(`finisher`, §3-D81)."""
    momentum: int = 50
    """그 순간 플레이어 쪽으로 기운 정도(0~100) — §3-D81. 50이 팽팽함이다."""


class CrewSchema(_Camel):
    """그 밤에 링을 둘러싼 사람들 (§3-D93).

    **경기가 있는 주차에만 온다.** 프로모·결장 주차에는 링이 서지 않는다.
    """

    gm: str = ""
    commentators: list[str] = Field(default_factory=list)
    ring_announcer: str = ""
    """**타이틀전에만 채워진다** — 벨트가 걸린 밤에는 소개가 먼저다."""
    referee: str = ""
    player_manager: str = ""
    """내 옆에 서는 사람. 정보창에 `w/`로 붙는다."""
    rival_manager: str = ""


class NegotiatorSchema(_Camel):
    """재계약 자리에 마주 앉는 사람 (§3-D93 규칙 2 · §3-D84)."""

    name: str
    title: str
    """원본의 직함 그대로 — 누구와 이야기하는지가 그 한 줄에 있다."""


class WeekSchema(_Camel):
    week: int
    """커리어 통산 주차(1~1560). 정렬·키에 쓴다."""
    year: int
    month: int
    week_of_month: int
    """게임 달력이 되읽은 날짜 — 화면은 "2년차 9월 2주"로 말한다 (§3-D21-1의 짝)."""
    kind: str
    result: str | None
    narration: str
    show: str | None = None
    title_at_stake: str | None = None
    opponent: str | None = None
    match_kind: str | None = None
    match_label: str | None = None
    """경기 형식 — "로열럼블 매치"처럼 화면에 그대로 나간다 (§3-D32)."""
    match_field: int = 2
    """참가 인원. 여럿이 붙는 경기는 화면이 상대 한 명을 말하면 안 된다."""
    cursed: bool = False
    """댄하우젠의 저주로 진 경기인지 (§3-D28). 화면이 평범한 패배와 다르게 그린다."""
    stars: float = 0.0
    """그 경기의 별점 (§3-D56). 경기가 없는 주차는 0이다."""
    match_summary: str | None = None
    """탈락 경기의 한 줄 요약 (§3-D34). **다시 연 로그에도 이것만은 남는다.**"""
    tournament_round: int = 0
    """킹 앤 퀸 오브 더 링의 회전 (§3-D33). 0이면 토너먼트 경기가 아니다."""
    elimination_match: bool = False
    """**여럿이 붙고 중간에 탈락자가 나오는 경기인가** (2026-08-14 사용자 요청).

    럼블·챔버·배틀로얄이 그렇다. 참자만 많은 경기(트리플 스렛)와 나눠 두는 이유:
    화면이 등장 순서와 탈락 수를 세울지 말지를 이 값 하나로 정한다."""
    entry_number: int = 0
    """**몇 번으로 입장했는가** — 럼블의 번호이자 챔버의 포드 순서다. 0이면 없다."""
    eliminations: int = 0
    """내가 떨어뜨린 사람 수."""
    place: int = 0
    """최종 순위. 1이면 우승 — 분모는 `match_field`다."""
    title_shot_from: str | None = None
    """`earned`(럼블·챔버 도전권) · `briefcase`(가방) — 자격이 아니라 **권리로** 선 자리 (§3-D36)."""
    crew: CrewSchema | None = None
    """링 밖의 사람들 (§3-D93). **경기 주차에만 온다.**"""
    beats: list[BeatSchema] | None = None
    """입장·탈락 전체 (§3-D34). 진행 중인 응답에만 실린다 — 저장하지 않기 때문이다.

    **문장이 아니라 구조로 보낸다.** "3번으로 입장"을 여기서 만들면 화면이 플레이어
    이름을 강조하거나 줄을 접는 것을 다시 파싱해야 한다.
    """
    # ── 여기부터 3차 평가에서 "만드는데 안 나간다"로 꼽은 것들 (§3-D73) ──
    pay: int = 0
    """그 주 수입(달러). 무소속 주차는 인디 개런티다 (§3-D50)."""
    title_defended: bool = False
    """방어에 성공했는지. **이긴 것과 지킨 것은 다른 사건이다** — 승리 줄이 같아 보이면
    챔피언으로 산 구간이 화면에서 통째로 평평해진다."""
    vacated: list[str] = Field(default_factory=list)
    """그 주에 **반납한** 벨트 (§3-D40). 길게 다치면 벨트를 내려놓는데, 그 사건이
    지금까지 로그에 한 줄도 없었다 — 다음에 벨트 목록을 보면 그냥 사라져 있다."""
    injury_part: str | None = None
    """다친 곳의 이름 (§3-D43). **몸은 기억한다**가 이 게임의 문장인데 어디를 다쳤는지가
    응답에 없었다."""
    call_up: str | None = None
    """`earned`(실력으로) · `emergency`(공백을 메우러) — 콜업의 결 (§3-D22·D22-1)."""
    draft_night: bool = False
    """그 주가 연말 드래프트였는지 (§3-D54). 소속이 바뀌는 밤이다."""
    stat_delta: dict[str, int] = Field(default_factory=dict)
    """그 주에 오르내린 스탯 (§3-D75 평가의 남은 자리). **성장이 보이지 않았다** —
    로그는 "이겼다"만 말하고 그 승리가 무엇을 남겼는지는 프로필의 숫자가 조용히
    올라갈 뿐이었다."""
    wear_delta: int = 0
    """그 주에 쌓인 마모. 몸이 닳는 것이 화면에 없었다."""
    promo_hit: bool | None = None
    """프로모가 먹혔는지 (§3-D41). 경기 없는 주차의 유일한 성패다 — `None`은
    프로모 주차가 아니라는 뜻이다."""


class SkillSchema(_Camel):
    """경기력 드롭다운 한 줄 — 파워·스피드·운영과 스타일 전용 축 (§3-D29)."""

    name: str
    value: int


class StatsSchema(_Camel):
    popularity: int
    in_ring: int
    mic_work: int
    backstage: int
    alignment: int
    wear: int
    play_style: str
    play_style_label: str
    skills: list[SkillSchema]


class TeamSchema(_Camel):
    """지금 속한 팀 (§3-D30). `label`이 화면에 그대로 나간다 — 이름이 없으면 "A & B"."""

    label: str
    name: str
    members: list[str]
    kind: str
    formed_week: int


class RivalrySchema(_Camel):
    """진행 중인 대립 한 줄 — **누구와, 어느 단계까지** 왔는지 (§2-D4)."""

    rival: str
    stage: str
    heat: int
    started_week: int
    opened_by: str = "rival"
    """`player`(내가 걸었다) · `rival`(상대가 걸어왔다) — §3-D86.

    **열기가 같아도 이야기가 다르다.** 내가 지목한 상대와 나를 지목해 온 상대는
    같은 대립이 아니고, 화면이 그걸 다르게 말해야 한다."""


class ContractSchema(_Camel):
    """지금 맺고 있는 계약 (§3-D47). 무소속이면 `RunSchema.contract`가 없다."""

    weekly_pay: int
    annual_pay: int
    """`Contract.annual_pay` — **도메인이 곱한다.** 화면이 52를 곱하면 두 곳이 갈린다."""
    signed_week: int
    ends_week: int
    years: int
    weeks_left: int
    """만료까지 남은 주차. 음수가 되지 않게 0에서 자른다 — 만료가 지나도 협상 주차를
    부상으로 건너뛸 수 있다(`Contract.expires_at`)."""


class MoneySchema(_Camel):
    """돈과 계약 (§3-D47·D50). **3차 평가에서 통째로 빠져 있던 축이다** (§3-D73).

    도메인은 2026-08-11에 다 만들어 뒀는데 응답에 한 필드도 안 나갔다. 잔액이 30년
    쌓이고 커리어의 3분의 1이 무소속을 겪는데, 화면은 그 어느 것도 몰랐다.
    """

    balance: int
    """누적 잔액(달러)."""
    contract: ContractSchema | None = None
    market_value: int = 0
    """**지금 몸값** — `contract_office.appraise()`. 맺고 있는 주급과 견주라고 함께 낸다.

    이 둘이 갈리는 것이 재계약의 긴장이다: 몸값이 주급보다 높으면 손해를 보며 뛰는
    중이고, 낮으면 지난 계약이 지금의 나를 먹여 살리는 중이다.
    """
    unsigned_weeks: int = 0
    """계약 없이 보낸 주차 (§3-D50). 0이면 소속이 있다."""
    fade_in_weeks: int | None = None
    """몇 주 뒤 잊히는가 — `FADE_GRACE_WEEKS`까지 남은 주차. 소속이 있으면 `None`.

    **무소속 구간의 유일한 시계다.** 이게 없으면 2년 반을 "왜 대회가 없지" 하며 보낸다.
    """


class GrandSlamGroupSchema(_Camel):
    name: str
    count: int
    """그 그룹에서 감은 횟수. 0이면 아직 빈 칸이다."""


class GrandSlamSchema(_Camel):
    """그랜드슬램 진행도 (§3-D20). **3차 평가에서 화면에 없다고 꼽은 자리** (§3-D73).

    `safe` 정책 실측 달성률이 55%인 훈장인데, 네 칸 중 무엇이 비었는지 볼 수가 없었다.
    등급은 **가장 적게 채운 그룹**이 정한다 — 월드를 다섯 번 감아도 US가 없으면 0이다.
    """

    level: int
    """0 미달 · 1 그랜드슬램 · 2 더블 그랜드슬램."""
    groups: list[GrandSlamGroupSchema] = Field(default_factory=list)


PLAYER_FLAGS: Final[dict[str, str]] = {
    flags.PAINKILLER: "진통제",
    flags.GROUNDED: "지상 전환",
    flags.PUSH_FROZEN: "푸시 동결",
    flags.GRUDGE: "라커룸 앙금",
    flags.MANAGER: "매니저",
    flags.NEMESIS_LOCKED: "숙적 고정",
    flags.CURSED: "댄하우젠의 저주",
    flags.WENT_INTO_BUSINESS: "제멋대로",
    flags.SUSPENSION_PENDING: "징계 대기",
}
"""화면에 나가는 상태 표식과 그 이름 (§3-D79).

**표식과 신호를 나눈다** (T11에서 정한 구분). `TEAM_PENDING`·`CASH_IN_PENDING`처럼
규칙이 읽고 지우는 **신호**는 여기 없다 — 그건 다음 주차에 무슨 일이 일어날지에
대한 내부 예약이지 지금 내 상태가 아니다. 여기 있는 것은 전부 "지금 나에게 붙어
있는 것"이다.

모르는 코드는 조용히 빠진다. 새 플래그를 더할 때 이 표에 넣을지 정하는 것이,
그 플래그가 표식인지 신호인지 정하는 것과 같다.
"""


class TrophySchema(_Camel):
    code: str
    week: int


class GoalRequest(_Camel):
    goal: str


class ChampionGroupSchema(_Camel):
    """한 브랜드(또는 통합)의 벨트들. 순서는 아래 `_CHAMPION_GROUPS`가 정한다."""

    brand: str
    label: str
    champions: list[TitleHolderSchema] = Field(default_factory=list)


class GuestGoalRequest(_Camel):
    state: GuestRunState
    goal: str


class GoalOptionSchema(_Camel):
    """고를 수 있는 목표 하나 (§3-D80). 잔액이 모자란 것은 아예 오지 않는다."""

    code: str
    label: str
    blurb: str
    cost: int


class OfferRequest(_Camel):
    offer: str


class CallOutRequest(_Camel):
    rival: str


class FinisherRequest(_Camel):
    """피니셔 교체 (§3-D88). **둘 중 하나만 채운다** — 목록에서 고르면 `code`,
    이름을 직접 지으면 `name`. 어느 갈래인지는 화면이 먼저 정한다."""

    code: str = ""
    name: str = ""
    hold: str = ""
    """지금 것을 그대로 쓰고 다시 묻는 날만 미룬다 — `quarter`·`year`·`forever`."""


class GuestFinisherRequest(_Camel):
    state: GuestRunState
    code: str = ""
    name: str = ""
    hold: str = ""


class FinisherOptionSchema(_Camel):
    code: str
    label: str
    blurb: str


class FinisherSchema(_Camel):
    """지금 쓰는 피니셔와 바꿀 수 있는 자리 (§3-D88).

    **수치가 없다** — 피니셔는 판정에 한 톨도 안 닿는다.
    """

    code: str
    name: str
    blurb: str
    custom: bool
    """직접 지은 이름인지."""
    can_change: bool
    settled: bool = False
    """**평생 쓰기로 못 박았는가** — 참이면 화면이 바꾸기 자리를 아예 안 낸다."""
    weeks_until_change: int
    """다시 바꿀 수 있을 때까지 남은 주차. **첫 분기에는 여기가 0이 아니다.**"""
    options: list[FinisherOptionSchema] = Field(default_factory=list)
    """목록에서 고르는 갈래의 선택지 — 기본기 + 내 계열."""
    name_min: int = 2
    name_max: int = 20
    """직접 짓는 갈래의 길이 제한. 링네임과 같다(§3-D12)."""


class SignatureRequest(_Camel):
    """시그니처 구매 (§3-D92). **셋 중 하나를 뜻한다.**

    | 보낸 것 | 뜻 |
    |---|---|
    | `buy` | 칸을 하나 더 산다 — `slot`·`name`은 안 본다 |
    | `drop` | 그 칸의 이름을 지운다 (돈은 안 돌아온다) |
    | `name` | 그 칸에 이름을 새긴다 |
    """

    slot: int = 0
    name: str = ""
    buy: bool = False
    drop: bool = False


class GuestSignatureRequest(_Camel):
    state: GuestRunState
    slot: int = 0
    name: str = ""
    buy: bool = False
    drop: bool = False


class SignatureSlotSchema(_Camel):
    """시그니처 칸 하나 (§3-D92)."""

    index: int
    name: str = ""
    """새긴 이름. **비어 있으면 계열 기술에서 굴려 쓴다**(§3-D91) — 그 칸이 없는
    것이 아니라, 아직 *내* 기술이 아닌 것이다."""


class SignatureSchema(_Camel):
    """산 칸과 이름들, 그리고 값 (§3-D92).

    **판정에 안 닿는다** — 사는 것은 그 경기가 어떻게 적히는가뿐이다(§3-D88과 같다).
    """

    slots: list[SignatureSlotSchema] = Field(default_factory=list)
    max_slots: int
    expand_cost: int | None = None
    """다음 칸의 값. **`None`이면 다 열었다** — 화면이 그 자리를 안 낸다."""
    naming_cost: int
    """칸 하나에 이름을 새기는 값."""
    finisher_naming_cost: int
    """피니셔 이름을 직접 짓는 값 (§3-D88의 그 자리가 이제 유료다)."""
    money: int
    """지금 잔액. **화면이 살 수 있는지를 스스로 판단하게 한다** — 서버가 `canBuy`를
    내려보내면 값과 잔액이 어긋날 때 어느 쪽이 맞는지 알 수 없다."""
    name_min: int = 2
    name_max: int = 20


class GuestCallOutRequest(_Camel):
    state: GuestRunState
    rival: str


class CallOutSchema(_Camel):
    """지금 시비를 걸 수 있는 자리 (§3-D86). **못 걸면 `None`이다.**

    후보는 규칙이 뽑을 때 쓰는 것과 같은 풀에서 나온다 — 급과 브랜드가 맞는 사람만
    선다(§3-D53). 세이브를 다시 열어도 같은 목록이다(§3-D4).
    """

    candidates: list[str] = Field(default_factory=list)
    slots_left: int = 0
    """남은 대립 자리. 0이면 못 건다 — `MAX_ACTIVE`가 상한이다."""


class GuestOfferRequest(_Camel):
    state: GuestRunState
    offer: str


class BriefcaseSchema(_Camel):
    """손에 든 머니 인 더 뱅크 가방 (§3-D85). **없으면 `None`이다.**

    **챔피언의 값은 담지 않는다** — 이름뿐이다. 인기도를 함께 내면 그것이 곧 승률의
    힌트가 되고, 그 순간 "지금 쓸까"는 판단이 아니라 계산이 된다 (§11-14).
    """

    title: str
    """겨누는 벨트의 이름 — 소속 브랜드의 월드 벨트."""
    champion: str
    """지금 그 벨트를 든 사람. 내가 들고 있으면 내 이름이다."""
    weeks_left: int
    """자동 현금화까지 남은 주차. **미루면 규칙이 대신 쓴다** — 그 시계가 곧 긴장이다."""
    pending: bool
    """이미 "쓴다"고 정했는가. 정한 뒤에는 무를 수 없다."""
    can_cash_in: bool
    """지금 뛰어들 수 있는가. 무소속이거나 이미 그 벨트를 감고 있으면 거짓이다."""


class OfferOptionSchema(_Camel):
    """재계약 협상의 선택지 하나 (§3-D84).

    **거절 확률은 내보내지 않는다** (§11-14). "등을 돌릴 수 있다"는 `blurb`가 말하고,
    그 이상은 수치라 그대로 내면 최적해가 드러난다 — 확률이 보이면 `PUSH`는 도박이
    아니라 계산이 된다.
    """

    code: str
    label: str
    blurb: str
    weekly_pay: int
    """그 선택지로 도장을 찍었을 때의 주급. 나간다(`walk`)면 0이다."""
    years: int
    """계약 연수. 0이면 계약을 맺지 않는다."""


class RunSchema(_Camel):
    id: int | None
    name: str
    """내 링네임. **화면이 명단에서 나를 짚으려면 필요하다** — 탈락 타임라인에서
    서른 줄 중 내 줄을 굵게 하는 데 쓴다 (§3-D34).
    """
    week: int
    year: int
    age: int
    brand: str
    mode: str
    status: str
    end_reason: str | None
    stats: StatsSchema
    condition: str
    titles_held: list[str]
    titles_won: list[str]
    team: TeamSchema | None = None
    rivalries: list[RivalrySchema] = Field(default_factory=list)
    money: MoneySchema | None = None
    """돈과 계약 (§3-D73). 옛 응답과 섞이지 않게 기본은 `None`이다."""
    injured_parts: list[str] = Field(default_factory=list)
    """다쳤던 곳들의 **이름** (§3-D43). *몸은 기억한다*가 이 게임의 문장인데
    화면에는 그 기억이 없었다 — 다음 부상이 여기로 돌아올 확률이 오른다."""
    trophies: list[TrophySchema] = Field(default_factory=list)
    """왕관 등 벨트가 아닌 훈장 (§3-D33). 토너먼트 우승이 로그를 지나가면 사라졌다."""
    flags: list[str] = Field(default_factory=list)
    """지금 붙어 있는 상태 표식의 **이름** (`PLAYER_FLAGS`). 신호는 빠진다."""
    grand_slam: GrandSlamSchema | None = None
    """그랜드슬램 진행도 (§3-D73)."""
    goal: str | None = None
    """이번 분기에 건 것 (§3-D80). 안 걸었으면 `None`이다."""
    champions: list[ChampionGroupSchema] = Field(default_factory=list)
    """**지금 이 세계선의 벨트와 그 주인 — 브랜드로 묶어서** (2026-08-13 사용자 요청).

    리포트의 `champions`는 그 밤의 카드에 설 사람들(내 브랜드·내 성별)이고, 이쪽은
    세계 전체다 — 내가 못 보는 브랜드의 벨트도 주인이 바뀌고 있다는 것이 §3-D38의
    전부이고, 그게 화면에 한 번도 안 나왔다.

    **통합 벨트는 따로 선다.** 위민스 태그팀(§3-D72)과 남녀 스피드는 한 브랜드의
    것이 아니라, RAW 줄에 끼워 넣으면 그 벨트가 무엇인지가 사라진다.
    """
    goal_options: list[GoalOptionSchema] = Field(default_factory=list)
    """지금 고를 수 있는 목표들. **비어 있으면 지금은 고를 때가 아니다** —
    NXT·무소속 구간이거나 이미 이번 분기를 걸었다."""
    next_kind: str = ""
    """**다음 주에 무엇이 서는가** (§3-D81-3, 2026-08-14 사용자 요청).

    `weekly_show` · `ple` · `special`이면 경기 밤이고, 그때 '다음' 버튼이 '경기
    시작'으로 바뀐다 — FM이 경기 앞에서 멈추는 것과 같은 자리다. 끝난 커리어는 빈
    문자열이다."""
    next_show: str | None = None
    """다음 주가 대회면 그 이름. 주간 방송·프로모면 `None`이다."""
    finisher: FinisherSchema | None = None
    """지금 쓰는 피니셔 (§3-D88). **늘 있다** — 안 골랐으면 수플렉스다."""
    signature: SignatureSchema | None = None
    """시그니처 칸과 값 (§3-D92). **늘 있다** — 기본 한 칸으로 시작한다."""
    negotiator: NegotiatorSchema | None = None
    """재계약 자리에 마주 앉는 사람 (§3-D93). **협상 중이 아니면 `None`이다.**"""
    call_out: CallOutSchema | None = None
    """지금 시비를 걸 수 있는 자리 (§3-D86). 자리가 없거나 상대가 없으면 `None`."""
    briefcase: BriefcaseSchema | None = None
    """손에 든 가방 (§3-D85). **없으면 `None`** — 화면은 이 값만 보고 자리를 낸다.

    `flags`의 표식과 다르다: 저쪽은 "지금 나에게 붙어 있는 것"의 이름표이고, 이쪽은
    **행동할 수 있는 자리**다. 시계와 대상이 함께 와야 고를 수 있다."""
    offer_options: list[OfferOptionSchema] = Field(default_factory=list)
    """재계약 협상의 선택지들 (§3-D84). **비어 있으면 협상 중이 아니다.**

    제시 주급은 따로 담지 않는다 — `money.market_value`가 곧 그 값이고(둘 다
    `contract_office.appraise`), 같은 수를 두 번 실어 보내면 언젠가 갈린다."""
    disclaimer: str = Field(
        default="이 게임의 전개는 가상입니다.",
        description="로그 화면 하단에 상시 노출한다 (§3-D13).",
    )


class AdvanceResponse(_Camel):
    run: RunSchema
    weeks: list[WeekSchema]
    stop_reason: str
    pending_event: PendingEventSchema | None = None


class GuestStartRequest(_Camel):
    """체험판 시작. **로그인 쪽과 본문이 같다** — 다른 것은 저장 여부뿐이다."""

    name: str
    mode: str
    based_on: str | None = None
    gender: str | None = None
    country: str | None = None
    play_style: str | None = None
    seed: int | None = None
    """브라우저가 재접속 후 같은 커리어를 이어가려면 시드를 들고 있어야 한다."""


class GuestAdvanceRequest(_Camel):
    """진행 요청 + **세이브 전체**. 서버는 이걸로만 상태를 안다(§3-D8)."""

    state: GuestRunState
    step: str = "auto"


class GuestResumeRequest(_Camel):
    """재개 요청 — **세이브만 있고 `step`이 없다.** 진행하지 않기 때문이다."""

    state: GuestRunState


class GuestChoiceRequest(_Camel):
    state: GuestRunState
    choice: str


class GuestReportRequest(_Camel):
    """그 밤의 리포트 요청 (§3-D51). **세이브와 주차뿐이다.**

    로그인 쪽은 `runId`로 물을 수 있지만 체험판에는 서버가 아는 커리어가 없어
    세이브가 함께 와야 한다 — 벨트 계보와 배경 사건이 그 시드에서 나온다.
    """

    state: GuestRunState
    week: int = Field(..., ge=1)
    opponent: str | None = None
    """그날 내 상대 (§3-D52). 카드가 그를 같은 밤에 두 번 세우지 않게 한다."""
    title_at_stake: str | None = None
    """그날 내가 도전한 벨트의 **표시 이름**. 카드가 같은 벨트를 다시 걸지 않게 한다.

    화면이 알려 주는 이유는 서버에 로그가 없어서다 — 모르는 이름은 조용히 무시된다.
    """


class GuestAdvanceResponse(_Camel):
    """로그인 쪽 응답 + **세이브 전체**.

    `state`를 브라우저가 통째로 보관했다가 다음 요청에 그대로 실어 보낸다(§3-D8).
    `run`은 사람이 읽는 요약이고 `state`가 기계가 읽는 원본이다 — 둘을 합치면 화면이
    내부 필드(`seenEvents`·`recentEvents` 512칸)까지 받아 보게 된다.
    """

    run: RunSchema
    weeks: list[WeekSchema]
    stop_reason: str
    pending_event: PendingEventSchema | None = None
    state: GuestRunState


class ModeSchema(_Camel):
    code: str
    label: str
    weeks_per_tick: int
    ticks: int
    event_budget: int
    guest_allowed: bool


class PresetSchema(_Camel):
    source: str
    gender: str
    play_style: str
    play_style_label: str
    country: str


class LogPageSchema(_Camel):
    entries: list[WeekSchema]
    total: int
    offset: int
    has_more: bool


class NewsCommentSchema(_Camel):
    """댓글 한 줄과 표 (§3-D87). **표는 반응이지 판정이 아니다** — 이 숫자로는
    아무것도 계산되지 않는다."""

    author: str
    text: str
    up: int
    down: int


class NewsSchema(_Camel):
    week: int
    year: int
    month: int
    week_of_month: int
    kind: str
    headline: str
    mood: str
    crowd_line: str
    outlet: str = ""
    """기사를 낸 가상 매체 (§3-D87). **실존 매체는 쓰지 않는다** (§3-D13)."""
    title: str = ""
    """신문 제목 — `headline`에 매체의 말투만 입힌 것이다. 새 사실은 없다."""
    body: str = ""
    """기사 본문. **이미 일어난 일만 다시 말한다** — 언제·무엇·그 자리의 소리."""
    comments: list[NewsCommentSchema] = Field(default_factory=list)
    """대중의 반응 다섯 (§3-D87). 한 명은 늘 반대편에 선다."""
    byline: str = ""
    """취재한 사람 (§3-D93) — 백스테이지 인터뷰어가 곧 기자다."""
    quote: str = ""
    """링 밖의 누군가가 그 일에 대해 한 말. 없으면 빈 문자열이다."""


class TitleHolderSchema(_Camel):
    title: str
    holder: str
    mine: bool
    """내가 감고 있는 벨트인지 — 화면이 내 줄을 짚는다 (§3-D45)."""


class CardMatchSchema(_Camel):
    """그날 밤의 다른 경기 한 줄 (§3-D52). **문장이 아니라 구조다** — 문구는 화면이 만든다."""

    left: str
    right: str
    winner: str
    title: str | None = None
    changed_hands: bool = False
    vacant: bool = False
    stars: float = 0.0
    """그 경기의 별점 (§3-D56). 0.25 눈금."""
    match_label: str | None = None
    """경기 형식 (§3-D55). 싱글이면 null이다."""
    """빈 벨트를 두고 붙은 경기 — 앞 챔피언이 링을 떠났다 (§3-D52)."""


class ShowReportSchema(_Camel):
    """그 밤의 리포트 (§3-D45). **뉴스와 다르다** — 뉴스는 커리어의 기억이고
    이쪽은 한 밤의 카드다."""

    week: int
    show: str
    is_major: bool
    result: str | None = None
    opponent: str | None = None
    match_label: str | None = None
    title_at_stake: str | None = None
    narration: str = ""
    champions: list[TitleHolderSchema] = Field(default_factory=list)
    around: list[str] = Field(default_factory=list)
    """그 무렵 배경에서 일어난 일 (§3-D44)."""
    card: list[CardMatchSchema] = Field(default_factory=list)
    """그날 밤의 다른 경기들, 오프너부터 (§3-D52). **내 경기는 없다.**"""
    stars: float = 0.0
    """그 밤의 평점 — 카드의 평균 (§3-D56)."""
    venue: str = ""
    """그 밤의 경기장 (§3-D69)."""
    logo: str = ""
    """그 밤의 로고 키 (§3-D71). 화면이 `/ple/<key>.png`로 찾는다."""
    nights: int = 1
    """며칠에 걸쳐 열렸는가. 이틀이면 카드가 두 배다."""


class NewsPageSchema(_Camel):
    items: list[NewsSchema]
    total: int
    offset: int
    has_more: bool


# ── 도메인 → 스키마 ──────────────────────────────────────────


def _rival_tier(report: WeekReport, stats: WrestlerStats, seed: int) -> RivalTier:
    """그 경기 상대의 급 (§3-D66).

    **상대를 이름으로 찾는다.** 예전에는 내 인기도로 상대의 급을 짐작했는데
    (`tier_for_popularity(내 인기도)`), 그러면 내가 인기를 얻는 것만으로 상대가 누구든
    별점이 함께 올랐다 — 별점이 스탯의 다른 표기가 되는 자리다.

    이름이 없거나(여럿이 붙는 경기·프로모) 명부 밖이면 그때만 인기도로 되돌아간다.
    """
    member = roster.member_of(report.opponent or "", seed)
    if member is None:
        return roster.tier_for_popularity(stats.popularity)
    return roster.tier_at(member, report.week)


def _stars_of(view: WeekReportView, seed: int) -> float:
    """내 경기의 별점 (§3-D56). **경기가 없는 주차는 0이다.**

    저장하지 않고 그 주차의 재료로 되짚는다 — 경기력은 로그 행이 들고 있는 그 주차
    스탯(§3-D39)이고, 없는 옛 행은 0으로 남는다(그때는 별점을 매길 근거가 없다).
    """
    report = view.report
    if report.result is None or view.stats is None:
        return 0.0
    stage = None
    if report.show is not None:
        stage = "major" if report.show.is_major else "ple"
    elif report.kind is WeekKind.SPECIAL:
        stage = "special"
    return match_rating.rate(
        seed,
        report.week,
        in_ring=view.stats.in_ring,
        rival_tier=_rival_tier(report, view.stats, seed),
        stage=stage,
        has_title=report.title_at_stake is not None,
        has_stipulation=report.match_kind is not MatchKind.SINGLES,
        salt="player",
    )


def to_crew(
    report: WeekReport,
    seed: int,
    *,
    brand: str,
    player: str,
    stable: str,
) -> CrewSchema | None:
    """그 주차의 링 밖 사람들 (§3-D93). **경기가 없으면 `None`이다.**"""
    if report.match_kind is None or report.result is None:
        return None
    crew = staff_scene.crew_for(
        brand,
        report.week,
        seed,
        title_match=report.title_at_stake is not None,
        player=player,
        player_stable=stable,
        opponent=report.opponent or "",
    )
    return CrewSchema(
        gm=crew.gm,
        commentators=list(crew.commentators),
        ring_announcer=crew.ring_announcer,
        referee=crew.referee,
        player_manager=crew.player_manager,
        rival_manager=crew.rival_manager,
    )


def to_week(
    view: WeekReportView,
    seed: int = 0,
    *,
    brand: str = "",
    player: str = "",
    stable: str = "",
) -> WeekSchema:
    report = view.report
    year, month, week_of_month = date_of(report.week)
    return WeekSchema(
        week=report.week,
        year=year,
        month=month,
        week_of_month=week_of_month,
        kind=report.kind.value,
        result=report.result.value if report.result else None,
        narration=view.narration,
        show=report.show.name if report.show else None,
        title_at_stake=report.title_at_stake.value if report.title_at_stake else None,
        opponent=report.opponent,
        match_kind=report.match_kind.value if report.match_kind else None,
        match_label=(
            match_format_of(report.match_kind).label if report.match_kind else None
        ),
        match_field=(
            match_format_of(report.match_kind).field if report.match_kind else 2
        ),
        cursed=report.cursed,
        stars=_stars_of(view, seed),
        tournament_round=report.tournament_round,
        title_shot_from=(
            report.title_shot_from.value if report.title_shot_from else None
        ),
        match_summary=view.match_summary,
        # **여럿이 붙는 경기의 자리** (2026-08-14 사용자 요청). 시퀀스가 이미 들고
        # 있던 값을 문장(`match_summary`)뿐 아니라 구조로도 내보낸다 — 화면이 숫자를
        # 문장에서 다시 파싱하지 않게.
        elimination_match=(
            report.match_kind in elimination.ELIMINATES if report.match_kind else False
        ),
        entry_number=report.sequence.entry_number if report.sequence else 0,
        eliminations=report.sequence.eliminated_by_player if report.sequence else 0,
        place=report.sequence.place if report.sequence else 0,
        pay=report.pay,
        title_defended=report.title_defended,
        vacated=[t.value for t in report.vacated],
        injury_part=PARTS[report.injury_part].label if report.injury_part else None,
        call_up=report.call_up.value if report.call_up else None,
        draft_night=report.draft_night,
        stat_delta=dict(report.stat_delta),
        wear_delta=report.wear_delta,
        promo_hit=report.promo_hit,
        crew=to_crew(report, seed, brand=brand, player=player, stable=stable),
        beats=(
            [
                BeatSchema(
                    kind=beat.kind.value,
                    name=beat.name,
                    number=beat.number,
                    by=beat.by,
                    momentum=beat.momentum,
                )
                for beat in report.sequence.beats
            ]
            if report.sequence
            else None
        ),
    )


def to_report(report: ShowReport) -> ShowReportSchema:
    return ShowReportSchema(
        week=report.week,
        show=report.show,
        is_major=report.is_major,
        result=report.result,
        opponent=report.opponent,
        match_label=(
            match_format_of(MatchKind(report.match_label)).label
            if report.match_label
            else None
        ),
        title_at_stake=report.title_at_stake,
        narration=report.narration,
        champions=[
            TitleHolderSchema(title=c.title, holder=c.holder, mine=c.mine)
            for c in report.champions
        ],
        around=list(report.around),
        card=[
            CardMatchSchema(
                left=m.left,
                right=m.right,
                winner=m.winner,
                title=m.title,
                changed_hands=m.changed_hands,
                vacant=m.vacant,
                stars=m.stars,
                match_label=m.match_label,
            )
            for m in report.card
        ],
        stars=report.stars,
        venue=report.venue,
        logo=report.logo,
        nights=report.nights,
    )


def title_of_display(name: str) -> Title | None:
    """벨트의 표시 이름 → 도메인 값. 모르는 이름은 None이다.

    **문자열이 도메인에 닿기 전에 여기서 멈춘다** — 체험판은 로그가 서버에 없어서
    "그날 내가 도전한 벨트"를 화면이 알려 줘야 하는데(§3-D52), 화면이 들고 있는 것은
    표시 이름뿐이다. 그 변환은 어댑터의 일이고, 도메인은 `Title`만 받는다.
    """
    return _TITLE_BY_DISPLAY.get(name)


_TITLE_BY_DISPLAY: Final[dict[str, Title]] = {
    spec.display_name: title for title, spec in TITLES.items()
}


def to_stats(stats: StatsView) -> StatsSchema:
    return StatsSchema(
        popularity=stats.popularity,
        in_ring=stats.in_ring,
        mic_work=stats.mic_work,
        backstage=stats.backstage,
        alignment=stats.alignment,
        wear=stats.wear,
        play_style=stats.play_style.value,
        play_style_label=stats.play_style_label,
        skills=[SkillSchema(name=n, value=v) for n, v in stats.skills],
    )


def to_money(run: CareerRun) -> MoneySchema:
    """돈과 계약을 화면 모양으로 (§3-D73).

    **몸값을 함께 낸다.** 잔액만 보내면 숫자 하나가 늘기만 하는 화면이 되고, 그건
    §3-D48이 아직 안 푼 문제("돈의 소비처가 없다")를 화면에서 되풀이하는 것이다.
    지금 주급과 지금 몸값이 나란히 서면 적어도 "덜 받고 있다"는 읽을 거리가 생긴다.
    """
    contract = run.contract
    return MoneySchema(
        balance=run.money,
        contract=(
            ContractSchema(
                weekly_pay=contract.weekly_pay,
                annual_pay=contract.annual_pay,
                signed_week=contract.signed_week,
                ends_week=contract.ends_week,
                years=contract.years,
                weeks_left=max(0, contract.ends_week - run.week),
            )
            if contract
            else None
        ),
        market_value=contract_office.appraise(run),
        unsigned_weeks=run.unsigned_weeks,
        fade_in_weeks=(
            max(0, rules.FADE_GRACE_WEEKS - run.unsigned_weeks)
            if contract is None
            else None
        ),
    )


def to_grand_slam(run: CareerRun) -> GrandSlamSchema:
    """네 그룹의 진행도 (§3-D73). 순서는 `GRAND_SLAM_GROUPS`가 정한 그대로다."""
    counts = group_counts(run.titles_won, run.identity.gender)
    return GrandSlamSchema(
        level=grand_slam_level(run.titles_won, run.identity.gender),
        groups=[
            GrandSlamGroupSchema(name=name, count=counts[name])
            for name, _ in GRAND_SLAM_GROUPS[run.identity.gender]
        ],
    )


_CHAMPION_GROUPS: Final[tuple[tuple[str, str], ...]] = (
    ("raw", "RAW"),
    ("smackdown", "스맥다운"),
    ("nxt", "NXT"),
    ("unified", "브랜드 통합"),
)
"""화면에 서는 순서와 이름. **통합이 마지막이다** — 브랜드 셋을 먼저 읽고 나서
"그리고 이건 어디서나 걸린다"로 닫는 편이 목록이 덜 흔들린다."""


def to_champion_groups(run: CareerRun) -> list[ChampionGroupSchema]:
    """세계선의 챔피언을 브랜드로 묶는다 (§3-D83).

    **브랜드가 둘 이상이면 통합이다.** 여성부 태그팀과 남녀 스피드가 그렇고
    (§3-D72), 이유는 서로 다르지만 화면에서 서는 자리는 같다 — 한 브랜드의 것이
    아니라는 사실이 그 벨트를 읽는 열쇠이기 때문이다.
    """
    buckets: dict[str, list[TitleHolderSchema]] = {
        key: [] for key, _ in _CHAMPION_GROUPS
    }
    for champion in show_report.world_champions(run):
        brands = TITLES[champion.title].brands
        key = next(iter(brands)).value if len(brands) == 1 else "unified"
        buckets[key].append(
            TitleHolderSchema(
                title=TITLES[champion.title].display_name,
                holder=champion.holder,
                mine=champion.mine,
            )
        )
    return [
        ChampionGroupSchema(brand=key, label=label, champions=buckets[key])
        for key, label in _CHAMPION_GROUPS
        if buckets[key]
    ]


def to_briefcase(run: CareerRun) -> BriefcaseSchema | None:
    """손에 든 가방을 화면 모양으로 (§3-D85). 안 들고 있으면 `None`.

    **챔피언은 벨트 목록과 같은 곳에서 읽는다**(`show_report.world_champions`) —
    따로 물으면 같은 세계선의 같은 벨트에 두 이름이 뜰 수 있다.
    """
    title = briefcase_desk.target_title(run)
    if not briefcase_desk.holds(run) or title is None:
        return None
    champion = next(
        (c.holder for c in show_report.world_champions(run) if c.title is title), ""
    )
    return BriefcaseSchema(
        title=TITLES[title].display_name,
        champion=champion,
        weeks_left=briefcase_desk.weeks_left(run),
        pending=briefcase_desk.is_pending(run),
        can_cash_in=briefcase_desk.can_cash_in(run),
    )


def _next_kind(run: CareerRun) -> str:
    """다음 주의 성격 (§3-D81-3). **규칙이 쓰는 것과 같은 함수를 부른다** —
    `week_kind_of`가 이미 `run.week + 1`을 보므로 화면과 판정이 갈리지 않는다.

    끝난 커리어와 마지막 주차는 빈 문자열이다: 다음 주가 없다.
    """
    if not run.is_active or run.weeks_remaining < 1:
        return ""
    return week_simulation.week_kind_of(run).value


def _next_show(run: CareerRun) -> str | None:
    """다음 주가 대회면 그 이름. 아니면 `None`."""
    if _next_kind(run) not in (WeekKind.PLE.value, WeekKind.SPECIAL.value):
        return None
    if not run.is_signed:
        return None
    calendar = calendar_for(run.brand, run.seed)
    upcoming = run.week + 1
    if not calendar.is_show_week(upcoming):
        return None
    return calendar.show_for(upcoming).name


def to_finisher(run: CareerRun) -> FinisherSchema:
    """지금 쓰는 피니셔와 고를 수 있는 것들 (§3-D88). **늘 채운다.**"""
    now = finisher_desk.current(run)
    return FinisherSchema(
        code=now.code,
        name=now.name,
        blurb=now.blurb,
        custom=now.code == CUSTOM_CODE,
        can_change=finisher_desk.can_change(run),
        settled=finisher_desk.is_settled(run),
        weeks_until_change=finisher_desk.weeks_until_change(run),
        options=[
            FinisherOptionSchema(code=f.code, label=f.name, blurb=f.blurb)
            for f in finisher_desk.options(run)
        ],
        name_min=NAME_MIN_LEN,
        name_max=NAME_MAX_LEN,
    )


def to_negotiator(run: CareerRun) -> NegotiatorSchema | None:
    """마주 앉는 사람 (§3-D93 규칙 2). **협상 중이 아니면 `None`** — 화면이 자리를 안 낸다."""
    if not run.is_active or run.offer_week <= 0:
        return None
    person = staff_scene.negotiator_for(run.brand.value, run.offer_week, run.seed)
    if person is None:
        return None
    return NegotiatorSchema(name=person.name, title=person.title)


def to_signature(run: CareerRun) -> SignatureSchema:
    """산 칸과 이름들 (§3-D92). **늘 채운다** — 한 칸은 처음부터 있다."""
    opened = signature_desk.slots(run)
    names = run.signature_names
    return SignatureSchema(
        slots=[
            SignatureSlotSchema(
                index=index,
                name=names[index] if index < len(names) else "",
            )
            for index in range(opened)
        ],
        max_slots=signature_desk.MAX_SLOTS,
        expand_cost=signature_desk.expand_cost(run),
        naming_cost=signature_desk.SIGNATURE_NAMING,
        finisher_naming_cost=signature_desk.FINISHER_NAMING,
        money=run.money,
        name_min=NAME_MIN_LEN,
        name_max=NAME_MAX_LEN,
    )


def to_call_out(run: CareerRun) -> CallOutSchema | None:
    """지금 걸 수 있는 상대들 (§3-D86). 못 걸면 `None` — 화면이 자리를 안 낸다."""
    if not rivalry_desk.can_call_out(run):
        return None
    return CallOutSchema(
        candidates=list(rivalry_desk.candidates(run)),
        slots_left=rivalry_engine.MAX_ACTIVE - len(run.rivalries),
    )


def to_offer_options(run: CareerRun) -> list[OfferOptionSchema]:
    """지금 열려 있는 협상의 선택지들 (§3-D84). 협상 중이 아니면 빈 목록이다.

    **금액은 도메인에 묻는다**(`contract_desk.pay_for`) — 여기서 곱셈을 다시 적으면
    보여 준 금액과 실제로 찍히는 금액이 갈린다.
    """
    if not contract_desk.is_open(run):
        return []
    return [
        OfferOptionSchema(
            code=spec.choice.value,
            label=spec.label,
            blurb=spec.blurb,
            weekly_pay=contract_desk.pay_for(run, spec),
            years=spec.years,
        )
        for spec in contract_desk.options(run)
    ]


def to_advance(result: AdvanceResult) -> AdvanceResponse:
    run = result.run
    return AdvanceResponse(
        run=RunSchema(
            id=run.id,
            name=str(run.identity.name),
            week=run.week,
            year=run.week // 52 + 1,
            age=run.age,
            brand=run.brand.value,
            mode=run.mode.code.value,
            status=run.status.value,
            end_reason=run.end_reason.value if run.end_reason else None,
            stats=to_stats(StatsView.of(run)),
            condition=run.condition.grade.value,
            titles_held=sorted(t.value for t in run.titles_held),
            titles_won=[t.value for t in run.titles_won],
            rivalries=[
                RivalrySchema(
                    rival=r.rival_name,
                    stage=r.stage.value,
                    heat=r.heat,
                    started_week=r.started_week,
                    opened_by=r.opened_by.value,
                )
                for r in run.rivalries
            ],
            money=to_money(run),
            grand_slam=to_grand_slam(run),
            goal=quarter_plan.plan_of(run).goal.value
            if run.goal and quarter_plan.plan_of(run).goal is not QuarterGoal.DRIFT
            else (run.goal.value if run.goal else None),
            champions=to_champion_groups(run),
            goal_options=[
                GoalOptionSchema(
                    code=spec.goal.value,
                    label=spec.label,
                    blurb=spec.blurb,
                    cost=spec.cost,
                )
                for spec in (
                    quarter_plan.options(run) if quarter_plan.needs_goal(run) else ()
                )
            ],
            briefcase=to_briefcase(run),
            next_kind=_next_kind(run),
            next_show=_next_show(run),
            finisher=to_finisher(run),
            signature=to_signature(run),
            negotiator=to_negotiator(run),
            call_out=to_call_out(run),
            offer_options=to_offer_options(run),
            injured_parts=[
                PARTS[BodyPart(code)].label
                for code in sorted(run.injured_parts)
                if code in {p.value for p in BodyPart}
            ],
            trophies=[TrophySchema(code=t.code, week=t.week) for t in run.trophies],
            flags=[PLAYER_FLAGS[f] for f in sorted(run.flags) if f in PLAYER_FLAGS],
            team=(
                TeamSchema(
                    label=run.team.label,
                    name=run.team.name,
                    members=list(run.team.members),
                    kind=run.team.kind.value,
                    formed_week=run.team.formed_week,
                )
                if run.team
                else None
            ),
        ),
        weeks=[
            to_week(
                w,
                run.seed,
                brand=run.brand.value,
                player=str(run.identity.name),
                stable=run.team.name if run.team else "",
            )
            for w in result.weeks
        ],
        stop_reason=result.stop_reason.value,
        pending_event=(
            PendingEventSchema(
                code=result.pending_event.code,
                title=result.pending_event.title,
                body=result.pending_event.body,
                choices=[
                    ChoiceSchema(code=c.code, label=c.label)
                    for c in result.pending_event.choices
                ],
            )
            if result.pending_event
            else None
        ),
    )


def to_guest(result: AdvanceResult) -> GuestAdvanceResponse:
    """로그인 응답에 세이브 전체를 덧붙인다."""
    base = to_advance(result)
    return GuestAdvanceResponse(
        run=base.run,
        weeks=base.weeks,
        stop_reason=base.stop_reason,
        pending_event=base.pending_event,
        state=to_state(result.run),
    )


def to_mode(view: ModeView) -> ModeSchema:
    return ModeSchema(
        code=view.code,
        label=view.label,
        weeks_per_tick=view.weeks_per_tick,
        ticks=view.ticks,
        event_budget=view.event_budget,
        guest_allowed=view.guest_allowed,
    )


def to_preset(view: PresetView) -> PresetSchema:
    return PresetSchema(
        source=view.source,
        gender=view.gender.value,
        play_style=view.play_style.value,
        play_style_label=KOREAN_STYLE_NAMES[view.play_style],
        country=view.country_code,
    )


def to_log(page: CareerLogPage) -> LogPageSchema:
    return LogPageSchema(
        entries=[to_week(e, page.seed) for e in page.entries],
        total=page.total,
        offset=page.offset,
        has_more=page.has_more,
    )


def to_news_item(
    item: NewsItem, seed: int = 0, *, brand: str = "", manager: str = ""
) -> NewsSchema:
    """뉴스 한 줄 + **그 자리에서 세운 기사** (§3-D87).

    기사는 저장하지 않고 매번 되짚는다 — `title_scene`(§3-D38)·별점(§3-D56)과 같은
    자리라, 시드만 있으면 언제든 같은 기사가 선다.
    """
    _, month, week_of_month = date_of(item.week)
    article = news_article.build(item, seed, brand=brand, manager=manager)
    return NewsSchema(
        week=item.week,
        year=item.year,
        month=month,
        week_of_month=week_of_month,
        kind=item.kind.value,
        headline=item.headline,
        mood=item.mood.value,
        crowd_line=item.crowd_line,
        outlet=article.outlet,
        title=article.title,
        body=article.body,
        comments=[
            NewsCommentSchema(author=c.author, text=c.text, up=c.up, down=c.down)
            for c in article.comments
        ],
        byline=article.byline,
        quote=article.quote,
    )


def to_news(page: NewsFeedPage) -> NewsPageSchema:
    return NewsPageSchema(
        items=[
            to_news_item(i, page.seed, brand=page.brand, manager=page.manager)
            for i in page.items
        ],
        total=page.total,
        offset=page.offset,
        has_more=page.has_more,
    )
