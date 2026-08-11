"""ORM ↔ 도메인 (하네스 §6 네이밍 · T9).

**변환을 리포지토리에서 떼어 놓는다.** 리포지토리는 언제 무엇을 읽고 쓸지를 정하고,
여기는 모양만 바꾼다. 섞어 두면 쿼리를 고칠 때마다 변환을 다시 읽어야 한다.

**도메인 값 객체가 검증을 맡는다.** DB에서 올라온 값도 `WrestlerStats`·`Condition`·
`CareerRun`의 `__post_init__`을 그대로 지난다 — 손으로 고친 행이나 예전 스키마가 남긴
값이 조용히 들어오지 않는다(§3-D8이 체험판에 요구한 것과 같은 방어다).
"""

from __future__ import annotations

from wwe_game.adapter.outbound.orm.career_orm import (
    CareerLogEntryModel,
    CareerRivalryModel,
    CareerRunModel,
)
from wwe_game.app.dtos.career_dto import WeekReportView
from wwe_game.domain.constants.countries import Country
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
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.team import Team
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.week_report import OutcomeKind, WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_identity import (
    Gender,
    PlayStyle,
    RingName,
    WrestlerIdentity,
)
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats


class CareerMapper:
    """세이브 한 건을 양쪽 모양으로 옮긴다."""

    @staticmethod
    def to_domain(
        row: CareerRunModel,
        *,
        rivalries: tuple[CareerRivalryModel, ...] = (),
        seen_events: frozenset[str] = frozenset(),
        trophies: tuple[Trophy, ...] = (),
    ) -> CareerRun:
        """자식 표는 **불러온 것만 채운다** — 로그는 여기 들어오지 않는다.

        로그는 세이브의 일부가 아니라 세이브가 남긴 자취다. 30년이면 1560줄이라
        재개할 때마다 끌고 오면 안 된다.
        """
        identity = WrestlerIdentity(
            name=RingName(row.name),
            gender=Gender(row.gender),
            country=Country(row.country),
            play_style=PlayStyle(row.play_style),
        )
        pending = (
            EventInstance(
                code=row.pending_code,
                week=row.pending_week or 0,
                body_index=row.pending_body_index or 0,
                rival_name=row.pending_rival,
            )
            if row.pending_code
            else None
        )
        return CareerRun(
            identity=identity,
            mode=game_mode_of(row.mode_code),
            seed=row.seed,
            id=row.id,
            user_id=row.user_id,
            week=row.week,
            stats=WrestlerStats(
                popularity=row.popularity,
                in_ring=row.in_ring,
                mic_work=row.mic_work,
                backstage=row.backstage,
                alignment=row.alignment,
            ),
            condition=Condition(
                grade=InjuryGrade(row.condition_grade),
                weeks_left=row.condition_weeks_left,
                wear=row.wear,
                part=BodyPart(row.condition_part) if row.condition_part else None,
            ),
            rivalries=tuple(
                Rivalry(
                    rival_name=r.rival_name,
                    stage=RivalryStage(r.stage),
                    heat=r.heat,
                    started_week=r.started_week,
                )
                for r in rivalries
            ),
            pending_event=pending,
            seen_events=seen_events,
            recent_events=tuple(row.recent_events or ()),
            flags=frozenset(row.flags or ()),
            team=_team_from_row(row.team),
            events_fired=row.events_fired,
            release_weeks=row.release_weeks,
            decline_weeks=row.decline_weeks,
            injured_parts=frozenset(row.injured_parts or ()),
            tournament_round=row.tournament_round,
            title_shot=row.title_shot,
            briefcase_week=row.briefcase_week,
            status=RunStatus(row.status),
            end_reason=EndReason(row.end_reason) if row.end_reason else None,
            trophies=trophies,
            brand=Brand(row.brand),
            titles_held=frozenset(Title(t) for t in row.titles_held or ()),
            titles_won=tuple(Title(t) for t in row.titles_won or ()),
            money=row.money or 0,
            contract=_contract_from_row(row),
            unsigned_weeks=row.unsigned_weeks or 0,
        )

    @staticmethod
    def apply_to_row(row: CareerRunModel, run: CareerRun) -> None:
        """도메인 상태를 행에 덮어쓴다. **새 행이든 갱신이든 같은 경로다.**"""
        row.user_id = run.user_id  # type: ignore[assignment]
        row.name = run.identity.name.value
        row.gender = run.identity.gender.value
        row.country = run.identity.country.value
        row.play_style = run.identity.play_style.value
        row.team = _team_to_row(run.team)
        row.mode_code = run.mode.code.value
        row.seed = run.seed
        row.week = run.week
        row.popularity = run.stats.popularity
        row.in_ring = run.stats.in_ring
        row.mic_work = run.stats.mic_work
        row.backstage = run.stats.backstage
        row.alignment = run.stats.alignment
        row.condition_grade = run.condition.grade.value
        row.condition_part = (
            run.condition.part.value if run.condition.part is not None else None
        )
        row.condition_weeks_left = run.condition.weeks_left
        row.wear = run.condition.wear
        pending = run.pending_event
        row.pending_code = pending.code if pending else None
        row.pending_week = pending.week if pending else None
        row.pending_body_index = pending.body_index if pending else None
        row.pending_rival = pending.rival_name if pending else None
        row.brand = run.brand.value
        row.titles_held = sorted(t.value for t in run.titles_held)
        row.titles_won = [t.value for t in run.titles_won]
        row.flags = sorted(run.flags)
        row.recent_events = list(run.recent_events)
        row.events_fired = run.events_fired
        row.release_weeks = run.release_weeks
        row.decline_weeks = run.decline_weeks
        row.injured_parts = sorted(run.injured_parts)
        row.tournament_round = run.tournament_round
        row.title_shot = run.title_shot
        row.briefcase_week = run.briefcase_week
        row.status = run.status.value
        row.end_reason = run.end_reason.value if run.end_reason else None
        row.money = run.money
        contract = run.contract
        row.contract_pay = contract.weekly_pay if contract else None
        row.contract_signed_week = contract.signed_week if contract else None
        row.contract_ends_week = contract.ends_week if contract else None
        row.unsigned_weeks = run.unsigned_weeks

    @staticmethod
    def log_row(run_id: int, view: WeekReportView) -> CareerLogEntryModel:
        report = view.report
        return CareerLogEntryModel(
            run_id=run_id,
            week=report.week,
            kind=report.kind.value,
            result=report.result.value if report.result else None,
            show_name=report.show.name if report.show else None,
            title_code=(report.title_at_stake.value if report.title_at_stake else None),
            narration=view.narration,
            opponent=report.opponent,
            match_kind=report.match_kind.value if report.match_kind else None,
            match_summary=view.match_summary,
            popularity=view.stats.popularity if view.stats else None,
            alignment=view.stats.alignment if view.stats else None,
        )

    @staticmethod
    def log_view(row: CareerLogEntryModel) -> WeekReportView:
        """로그 한 줄을 화면용으로. **판정 중간값은 복원하지 않는다.**

        저장하지 않았으니 되살릴 수도 없다 — 로그를 다시 읽는 화면이 필요로 하는 것은
        무슨 일이 있었는지와 그 문장뿐이다.
        """
        return WeekReportView(
            report=WeekReport(
                week=row.week,
                kind=WeekKind(row.kind),
                result=OutcomeKind(row.result) if row.result else None,
                title_at_stake=Title(row.title_code) if row.title_code else None,
                opponent=row.opponent,
                match_kind=MatchKind(row.match_kind) if row.match_kind else None,
            ),
            narration=row.narration,
            match_summary=row.match_summary,
            # 뉴스가 읽는 것은 이 둘뿐이다 (§3-D39). 나머지 스탯은 저장하지 않는다.
            stats=(
                WrestlerStats(popularity=row.popularity, alignment=row.alignment)
                if row.popularity is not None and row.alignment is not None
                else None
            ),
        )


def _team_to_row(team: Team | None) -> dict[str, object] | None:
    if team is None:
        return None
    return {
        "name": team.name,
        "members": list(team.members),
        "formed_week": team.formed_week,
    }


def _contract_from_row(row: CareerRunModel) -> Contract | None:
    """세 칼럼을 계약 한 장으로 모은다. **하나라도 비면 무소속이다**.

    옛 세이브에는 이 칸들이 없어 전부 None으로 읽힌다 — 그 세이브는 계약 없이
    뛰던 것이 아니라 계약이라는 개념 이전의 것이지만, 결과는 같게 둔다:
    다음 협상 주차에 새로 맺는다(§3-D49). 마이그레이션으로 소급해 채우면
    "그때 몸값이 얼마였는가"를 지금 스탯으로 지어내야 한다.
    """
    if row.contract_pay is None or row.contract_ends_week is None:
        return None
    return Contract(
        weekly_pay=row.contract_pay,
        signed_week=row.contract_signed_week or 0,
        ends_week=row.contract_ends_week,
    )


def _team_from_row(raw: dict[str, object] | None) -> Team | None:
    """행에 없으면 혼자다. **옛 세이브에는 이 칸이 없다** — None이 정상이다."""
    if not raw:
        return None
    return Team(
        name=str(raw.get("name", "")),
        members=tuple(str(m) for m in raw.get("members", ())),
        formed_week=int(raw.get("formed_week", 0)),  # type: ignore[arg-type]
    )
