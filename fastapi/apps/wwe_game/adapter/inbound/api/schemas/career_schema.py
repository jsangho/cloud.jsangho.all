"""HTTP 경계의 Pydantic 스키마 (하네스 §7).

**응답에 내부 수치를 담지 않는다**(§11-14). 선택지의 `risk`·`injury_risk`, 주사위 값,
확률 상수는 전부 빠진다 — 그대로 내보내면 최적해가 드러나 '고르는 재미'가 사라진다.

JSON은 camelCase, 도메인은 snake_case다. 변환은 **이 경계에서만** 일어난다 — 덱 로더가
`_STAT_KEYS`로 같은 일을 하는 것과 같은 규약이다(§3-D19).
"""

from __future__ import annotations

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
from wwe_game.domain.constants.play_styles import KOREAN_STYLE_NAMES
from wwe_game.domain.services.news_feed import NewsItem


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


class WeekSchema(_Camel):
    week: int
    kind: str
    result: str | None
    narration: str
    show: str | None = None
    title_at_stake: str | None = None
    opponent: str | None = None
    cursed: bool = False
    """댄하우젠의 저주로 진 경기인지 (§3-D28). 화면이 평범한 패배와 다르게 그린다."""


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


class GuestChoiceRequest(_Camel):
    state: GuestRunState
    choice: str


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
    kind: str
    headline: str
    mood: str
    crowd_line: str


class NewsPageSchema(_Camel):
    items: list[NewsSchema]
    total: int
    offset: int
    has_more: bool


# ── 도메인 → 스키마 ──────────────────────────────────────────


def to_week(view: WeekReportView) -> WeekSchema:
    report = view.report
    return WeekSchema(
        week=report.week,
        kind=report.kind.value,
        result=report.result.value if report.result else None,
        narration=view.narration,
        show=report.show.name if report.show else None,
        title_at_stake=report.title_at_stake.value if report.title_at_stake else None,
        opponent=report.opponent,
        cursed=report.cursed,
    )


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
        weeks=[to_week(w) for w in result.weeks],
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
        entries=[to_week(e) for e in page.entries],
        total=page.total,
        offset=page.offset,
        has_more=page.has_more,
    )


def to_news_item(item: NewsItem) -> NewsSchema:
    return NewsSchema(
        week=item.week,
        year=item.year,
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
