"""체험판 세이브의 JSON 코덱 (하네스 §7 `/guest/*` · §3-D8).

**상태를 서버에 저장하지 않는다.** 클라이언트가 세이브 전체를 보내면 서버가 규칙을 돌려
다음 상태를 통째로 돌려주고, 저장은 브라우저가 한다.

## 신뢰하지 않되 막지도 않는다

받은 값은 전부 **도메인 값 객체를 거쳐** 되살아난다 — 범위 밖 스탯·모르는 코드·1560
초과 주차는 그 자리에서 터지고 라우터가 400으로 옮긴다(§11-26). 반대로 규칙에 맞는
값이면 그대로 받는다: 체험판은 순위표와 엮이지 않으므로(§3-D7) 조작해도 잃을 것이 없고,
막으려 들면 결국 서버가 상태를 들고 있어야 해서 §3-D8의 전제가 무너진다.

## ORM 매퍼와 따로 두는 이유

`career_mapper.py`가 하는 일과 겹쳐 보이지만 **대상이 다르다** — 그쪽은 표 하나의
컬럼이고 이쪽은 브라우저가 들고 다니는 JSON이다. 합치면 DB 스키마를 바꿀 때마다
체험판 저장 포맷이 깨져 옛 세이브를 못 읽는다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from wwe_game.domain.constants.countries import country_of
from wwe_game.domain.entities.career_run import (
    CareerRun,
    EndReason,
    EventInstance,
    Rivalry,
    RivalryStage,
    RunStatus,
    Trophy,
)
from wwe_game.domain.value_objects.body_part import BodyPart
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.contract import Contract
from wwe_game.domain.value_objects.game_mode import game_mode_of
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal
from wwe_game.domain.value_objects.team import Team
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class GuestRunState(BaseModel):
    """브라우저가 들고 다니는 세이브 한 벌. **필드 이름은 도메인과 같다.**

    camelCase로 바꾸지 않는 이유: 이 자료형은 화면이 읽는 것이 아니라 **그대로 돌려보내는
    것**이다. 사람이 읽을 응답(`AdvanceResponse`)은 따로 있고, 그쪽이 camelCase를 쓴다.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    gender: str
    country: str
    play_style: str
    mode: str
    seed: int
    week: int = 0
    stats: dict[str, int] = Field(default_factory=dict)
    condition: dict[str, int | str | None] = Field(default_factory=dict)
    """`part`가 None일 수 있어 값 타입에 None이 들어간다 (§3-D43)."""
    rivalries: list[dict[str, Any]] = Field(default_factory=list)
    pending_event: dict[str, Any] | None = None
    seen_events: list[str] = Field(default_factory=list)
    recent_events: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    events_fired: int = 0
    release_weeks: int = 0
    decline_weeks: int = 0
    injured_parts: list[str] = Field(default_factory=list)
    tournament_round: int = 0
    title_shot: bool = False
    briefcase_week: int = 0
    status: str = RunStatus.ACTIVE.value
    end_reason: str | None = None
    trophies: list[dict[str, Any]] = Field(default_factory=list)
    brand: str = Brand.NXT.value
    titles_held: list[str] = Field(default_factory=list)
    titles_won: list[str] = Field(default_factory=list)
    team: dict[str, Any] | None = None
    money: int = 0
    contract: dict[str, int] | None = None
    """계약 한 장 또는 무소속 (§3-D47). 옛 세이브에는 없어 None으로 읽힌다."""
    unsigned_weeks: int = 0
    goal: str | None = None
    """이번 분기에 건 것 (§3-D80). 옛 체험판 세이브는 없으므로 기본이 `None`이다."""
    goal_quarter: int = -1
    offer_week: int = 0
    """재계약 협상이 열린 주차 (§3-D84). 옛 체험판 세이브는 0이다."""


def to_domain(state: GuestRunState) -> CareerRun:
    """JSON → 세이브. **값 객체가 입구에서 검증한다** — 어긴 값은 여기서 터진다."""
    identity = WrestlerIdentity(
        name=RingName(state.name),
        gender=Gender(state.gender),
        country=country_of(state.country),
        play_style=PlayStyle(state.play_style),
    )
    condition = Condition(
        grade=InjuryGrade(str(state.condition.get("grade", InjuryGrade.HEALTHY.value))),
        weeks_left=int(state.condition.get("weeks_left", 0)),
        wear=int(state.condition.get("wear", 0)),
        part=(
            BodyPart(str(state.condition["part"]))
            if state.condition.get("part")
            else None
        ),
    )
    return CareerRun(
        identity=identity,
        mode=game_mode_of(state.mode),
        seed=state.seed,
        user_id=None,
        week=state.week,
        stats=WrestlerStats(**state.stats) if state.stats else WrestlerStats(),
        condition=condition,
        rivalries=tuple(
            Rivalry(
                rival_name=str(r["rival_name"]),
                stage=RivalryStage(r["stage"]),
                heat=int(r["heat"]),
                started_week=int(r["started_week"]),
            )
            for r in state.rivalries
        ),
        pending_event=(
            EventInstance(
                code=str(state.pending_event["code"]),
                week=int(state.pending_event["week"]),
                body_index=int(state.pending_event.get("body_index", 0)),
                rival_name=state.pending_event.get("rival_name"),
            )
            if state.pending_event
            else None
        ),
        seen_events=frozenset(state.seen_events),
        recent_events=tuple(state.recent_events),
        flags=frozenset(state.flags),
        events_fired=state.events_fired,
        release_weeks=state.release_weeks,
        decline_weeks=state.decline_weeks,
        injured_parts=frozenset(state.injured_parts),
        tournament_round=state.tournament_round,
        title_shot=state.title_shot,
        briefcase_week=state.briefcase_week,
        status=RunStatus(state.status),
        end_reason=EndReason(state.end_reason) if state.end_reason else None,
        trophies=tuple(
            Trophy(code=str(t["code"]), week=int(t["week"])) for t in state.trophies
        ),
        brand=Brand(state.brand),
        titles_held=frozenset(Title(t) for t in state.titles_held),
        titles_won=tuple(Title(t) for t in state.titles_won),
        team=(
            Team(
                name=str(state.team.get("name", "")),
                members=tuple(str(m) for m in state.team.get("members", ())),
                formed_week=int(state.team.get("formed_week", 0)),
            )
            if state.team
            else None
        ),
        money=state.money,
        unsigned_weeks=state.unsigned_weeks,
        goal=QuarterGoal(state.goal) if state.goal else None,
        goal_quarter=state.goal_quarter,
        offer_week=state.offer_week,
        contract=(
            Contract(
                weekly_pay=int(state.contract["weekly_pay"]),
                signed_week=int(state.contract["signed_week"]),
                ends_week=int(state.contract["ends_week"]),
            )
            if state.contract
            else None
        ),
    )


def to_state(run: CareerRun) -> GuestRunState:
    """세이브 → JSON. 브라우저가 이걸 그대로 보관했다가 다음 요청에 실어 보낸다."""
    return GuestRunState(
        name=str(run.identity.name),
        gender=run.identity.gender.value,
        country=run.identity.country.value,
        play_style=run.identity.play_style.value,
        mode=run.mode.code.value,
        seed=run.seed,
        week=run.week,
        stats={
            "popularity": run.stats.popularity,
            "in_ring": run.stats.in_ring,
            "mic_work": run.stats.mic_work,
            "backstage": run.stats.backstage,
            "alignment": run.stats.alignment,
        },
        condition={
            "grade": run.condition.grade.value,
            "weeks_left": run.condition.weeks_left,
            "wear": run.condition.wear,
            "part": run.condition.part.value if run.condition.part else None,
        },
        rivalries=[
            {
                "rival_name": r.rival_name,
                "stage": r.stage.value,
                "heat": r.heat,
                "started_week": r.started_week,
            }
            for r in run.rivalries
        ],
        pending_event=(
            {
                "code": run.pending_event.code,
                "week": run.pending_event.week,
                "body_index": run.pending_event.body_index,
                "rival_name": run.pending_event.rival_name,
            }
            if run.pending_event
            else None
        ),
        seen_events=sorted(run.seen_events),
        recent_events=list(run.recent_events),
        flags=sorted(run.flags),
        events_fired=run.events_fired,
        release_weeks=run.release_weeks,
        decline_weeks=run.decline_weeks,
        injured_parts=sorted(run.injured_parts),
        tournament_round=run.tournament_round,
        title_shot=run.title_shot,
        briefcase_week=run.briefcase_week,
        status=run.status.value,
        end_reason=run.end_reason.value if run.end_reason else None,
        trophies=[{"code": t.code, "week": t.week} for t in run.trophies],
        brand=run.brand.value,
        titles_held=sorted(t.value for t in run.titles_held),
        titles_won=[t.value for t in run.titles_won],
        team=(
            {
                "name": run.team.name,
                "members": list(run.team.members),
                "formed_week": run.team.formed_week,
            }
            if run.team
            else None
        ),
        money=run.money,
        unsigned_weeks=run.unsigned_weeks,
        contract=(
            {
                "weekly_pay": run.contract.weekly_pay,
                "signed_week": run.contract.signed_week,
                "ends_week": run.contract.ends_week,
            }
            if run.contract
            else None
        ),
        goal=run.goal.value if run.goal else None,
        goal_quarter=run.goal_quarter,
        offer_week=run.offer_week,
    )
