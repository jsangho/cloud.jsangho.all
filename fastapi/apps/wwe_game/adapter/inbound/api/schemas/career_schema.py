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
from wwe_game.domain.constants import roster
from wwe_game.domain.constants.play_styles import KOREAN_STYLE_NAMES
from wwe_game.domain.constants.ple_calendar import date_of
from wwe_game.domain.constants.roster import RivalTier
from wwe_game.domain.services import match_rating
from wwe_game.domain.services.news_feed import NewsItem
from wwe_game.domain.services.show_report import ShowReport
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.match_kind import format_of as match_format_of
from wwe_game.domain.value_objects.title import TITLES, Title
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
    """누가 탈락시켰는가. `eliminate`에만 채워진다."""


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
    title_shot_from: str | None = None
    """`earned`(럼블·챔버 도전권) · `briefcase`(가방) — 자격이 아니라 **권리로** 선 자리 (§3-D36)."""
    beats: list[BeatSchema] | None = None
    """입장·탈락 전체 (§3-D34). 진행 중인 응답에만 실린다 — 저장하지 않기 때문이다.

    **문장이 아니라 구조로 보낸다.** "3번으로 입장"을 여기서 만들면 화면이 플레이어
    이름을 강조하거나 줄을 접는 것을 다시 파싱해야 한다.
    """


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


class NewsSchema(_Camel):
    week: int
    year: int
    month: int
    week_of_month: int
    kind: str
    headline: str
    mood: str
    crowd_line: str


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


def to_week(view: WeekReportView, seed: int = 0) -> WeekSchema:
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
        beats=(
            [
                BeatSchema(
                    kind=beat.kind.value, name=beat.name, number=beat.number, by=beat.by
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
                )
                for r in run.rivalries
            ],
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
        weeks=[to_week(w, run.seed) for w in result.weeks],
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


def to_news_item(item: NewsItem) -> NewsSchema:
    _, month, week_of_month = date_of(item.week)
    return NewsSchema(
        week=item.week,
        year=item.year,
        month=month,
        week_of_month=week_of_month,
        kind=item.kind.value,
        headline=item.headline,
        mood=item.mood.value,
        crowd_line=item.crowd_line,
    )


def to_news(page: NewsFeedPage) -> NewsPageSchema:
    return NewsPageSchema(
        items=[to_news_item(i) for i in page.items],
        total=page.total,
        offset=page.offset,
        has_more=page.has_more,
    )
