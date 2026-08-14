"""진행 코디네이터 (하네스 §6 · T8).

**판정은 하나도 하지 않는다.** 주차 시뮬·이벤트 추첨·은퇴 판정은 전부 도메인의 순수
함수이고(§3-D1), 여기가 하는 일은 셋뿐이다.

1. 세이브를 읽는다 (또는 요청 본문에서 받는다)
2. `career_advance.advance()`를 부른다
3. 결과에 문장을 붙여 **한 번에** 저장한다 (§3-D6)

**로그인과 체험판이 같은 규칙을 쓴다**(§11-25). 둘 다 2번의 같은 함수를 부르고, 갈리는
것은 1·3번뿐이다 — 체험판은 상태를 요청 본문에서 받아 아무 데도 쓰지 않는다(§3-D8).
규칙을 순수 함수로 떼어 놨기 때문에 그 공유가 저절로 된다. 유스케이스가 규칙을 품고
있으면 언젠가 한쪽만 고쳐진다.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import replace

from wwe_game.app.dtos.career_dto import (
    AdvanceCommand,
    AdvanceResult,
    AnswerOfferCommand,
    CallOutCommand,
    CareerLogPage,
    CashInCommand,
    ChoiceView,
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
    PendingEventView,
    PresetView,
    SetGoalCommand,
    StartRunCommand,
    WeekReportView,
)
from wwe_game.app.ports.input.career_use_case import (
    CareerUseCase,
    ChoiceRequiredError,
    GuestModeNotAllowedError,
    NoPendingEventError,
    ReportNotFoundError,
    RunAlreadyActiveError,
)
from wwe_game.app.ports.output.career_repository import CareerRepository
from wwe_game.app.ports.output.narration_port import NarrationPort
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.constants.character_presets import PRESETS
from wwe_game.domain.constants.countries import country_of
from wwe_game.domain.constants.event_deck import BY_CODE
from wwe_game.domain.entities.career_run import CareerRun, EndReason, start_run
from wwe_game.domain.exceptions import InvalidChoiceError
from wwe_game.domain.services import (
    briefcase_desk,
    career_advance,
    career_end,
    contract_desk,
    event_draw,
    news_feed,
    quarter_plan,
    rivalry_desk,
    rivalry_scene,
    roster_scene,
    show_report,
    team_engine,
    title_news,
)
from wwe_game.domain.services.character_creation import build_identity
from wwe_game.domain.services.rivalry_scene import SceneNews
from wwe_game.domain.services.roster_scene import RosterNews
from wwe_game.domain.services.show_report import ShowReport
from wwe_game.domain.services.title_news import TitleNews
from wwe_game.domain.services.week_simulation import apply_week
from wwe_game.domain.value_objects.advance_outcome import AdvanceOutcome, StopReason
from wwe_game.domain.value_objects.contract_offer import OfferChoice
from wwe_game.domain.value_objects.game_mode import GAME_MODES, game_mode_of
from wwe_game.domain.value_objects.quarter_goal import QuarterGoal
from wwe_game.domain.value_objects.week_report import WeekKind
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle

SEED_BITS = 32
"""시드의 크기. 재현이 목적이라 암호학적 강도는 필요 없지만, 겹치면 두 커리어가 똑같아진다."""


def _new_seed() -> int:
    return secrets.randbits(SEED_BITS)


class CareerInteractor(CareerUseCase):
    """`CareerUseCase`의 유일한 구현."""

    def __init__(
        self,
        *,
        repository: CareerRepository,
        narrator: NarrationPort,
        seed_factory: Callable[[], int] = _new_seed,
    ) -> None:
        self._repository = repository
        self._narrator = narrator
        self._seed_factory = seed_factory
        """시드를 주입받는 이유: 테스트가 재현을 고정해야 한다. 기본값은 난수다."""

    # ── 로그인 플레이 ─────────────────────────────────────────

    async def start(self, command: StartRunCommand) -> AdvanceResult:
        if await self._repository.find_active(command.user_id) is not None:
            raise RunAlreadyActiveError("이미 진행 중인 커리어가 있습니다.")
        run = self._new_run(
            name=command.name,
            mode_code=command.mode_code,
            based_on=command.based_on,
            gender=command.gender,
            country_code=command.country_code,
            play_style=command.play_style,
            seed=command.seed,
            user_id=command.user_id,
        )
        saved = await self._repository.save(run)
        return self._view(saved, StopReason.READY)

    async def current(self, user_id: int) -> AdvanceResult | None:
        run = await self._repository.find_active(user_id)
        if run is None:
            return None
        return self._view(run, self._resting_reason(run))

    async def advance(self, command: AdvanceCommand) -> AdvanceResult:
        run = await self._repository.get(command.run_id, command.user_id)
        self._require_unblocked(run)
        outcome = career_advance.advance(run, step=command.step)
        weeks = self._narrate(run, outcome)
        saved = await self._repository.save(outcome.run, weeks)
        return self._view(saved, outcome.stop_reason, weeks)

    async def choose(self, command: ChooseCommand) -> AdvanceResult:
        run = await self._repository.get(command.run_id, command.user_id)
        resolved = self._resolve(run, command.choice_code)
        saved = await self._repository.save(resolved)
        return self._view(saved, self._resting_reason(saved))

    async def set_goal(self, command: SetGoalCommand) -> AdvanceResult:
        """분기 목표를 걸고 그 자리에서 멈춘 채 돌려준다 (§3-D80).

        **진행시키지 않는다.** 고른 것을 화면이 먼저 보여 주고, 다음 '다음'부터
        그 배수로 흘러가는 편이 "내가 이걸 걸었다"를 읽게 한다.
        """
        run = await self._repository.get(command.run_id, command.user_id)
        goal = _goal_of(command.goal_code)
        saved = await self._repository.save(quarter_plan.choose(run, goal))
        return self._view(saved, self._resting_reason(saved))

    async def answer_offer(self, command: AnswerOfferCommand) -> AdvanceResult:
        """재계약 협상에 답하고 그 자리에서 멈춘 채 돌려준다 (§3-D84).

        **진행시키지 않는다** — `set_goal`과 같은 이유다. 도장을 찍었는지 나갔는지를
        화면이 먼저 보여 줘야 "내가 이걸 골랐다"가 읽힌다.
        """
        run = await self._repository.get(command.run_id, command.user_id)
        answered = contract_desk.answer(run, _offer_of(command.offer_code))
        saved = await self._repository.save(answered)
        return self._view(saved, self._resting_reason(saved))

    async def cash_in(self, command: CashInCommand) -> AdvanceResult:
        """가방을 쓰기로 하고 그 자리에서 멈춘 채 돌려준다 (§3-D85).

        **진행시키지 않는다** — `set_goal`·`answer_offer`와 같은 이유다. 다만 저
        둘은 막힌 것을 푸는 답이고 이건 **안 해도 그만인 행동**이라, 화면이 이걸
        하지 않고 '다음'을 눌러도 아무 일도 일어나지 않아야 한다.
        """
        run = await self._repository.get(command.run_id, command.user_id)
        saved = await self._repository.save(briefcase_desk.cash_in(run))
        return self._view(saved, self._resting_reason(saved))

    async def call_out(self, command: CallOutCommand) -> AdvanceResult:
        """시비를 걸고 그 자리에서 멈춘 채 돌려준다 (§3-D86)."""
        run = await self._repository.get(command.run_id, command.user_id)
        saved = await self._repository.save(
            rivalry_desk.call_out(run, command.rival_name)
        )
        return self._view(saved, self._resting_reason(saved))

    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> CareerLogPage:
        """로그 한 페이지. **세이브를 함께 읽는다** — 별점이 시드를 필요로 한다(§3-D56).

        쿼리가 하나 늘지만 로그는 탭을 열 때만 읽고(§3-D45의 방침), 별점을 저장하지
        않기로 한 대가가 이 한 번이다.
        """
        run = await self._repository.get(run_id, user_id)
        entries, total = await self._repository.read_log(
            run_id, user_id, offset=offset, limit=limit
        )
        return CareerLogPage(entries=entries, total=total, offset=offset, seed=run.seed)

    async def read_report(self, run_id: int, user_id: int, week: int) -> ShowReport:
        """그 주차의 리포트 (§3-D45).

        **로그에서 그 한 줄만 읽는다.** 리포트는 새 규칙이 아니라 보는 방식이라
        (§3-D45), 필요한 것은 그 주차 기록 하나와 시드뿐이다.
        """
        run = await self._repository.get(run_id, user_id)
        if not show_report.is_reportable(run, week):
            raise ReportNotFoundError(f"{week}주차는 대회 주차가 아닙니다.")
        entries, _ = await self._repository.read_log(
            run_id, user_id, offset=max(0, week - 1), limit=1
        )
        found = next((v for v in entries if v.week == week), None)
        if found is None:
            raise ReportNotFoundError(f"{week}주차 기록이 없습니다.")
        # **달력이 아니라 그날 실제로 있었던 일을 본다.** 부상으로 결장했거나(§3-D37)
        # 프로모만 한 주차에는 리포트를 열지 않는다 — 링에 서지도 않은 밤의 카드다.
        # 로그를 가진 이 경로는 물어볼 수 있으므로 여기서 막는다(체험판은 로그가 없어
        # 그대로 둔다 · §3-D51). 주간 방송은 §3-D60에서 열렸다.
        if found.report.kind not in (
            WeekKind.PLE,
            WeekKind.SPECIAL,
            WeekKind.WEEKLY_SHOW,
        ):
            raise ReportNotFoundError(f"{week}주차는 경기가 선 밤이 아닙니다.")
        return show_report.build(
            run, found.report, found.narration, self._narrator.venue_of(run, week)
        )

    async def read_news(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> NewsFeedPage:
        """로그 전체를 훑어 **남을 만한 사건만** 세운다 (§3-D31).

        전체를 읽는 이유: 뉴스는 로그의 3% 남짓이라, 로그를 페이지 단위로 잘라 뉴스를
        만들면 어떤 페이지는 통째로 비어 화면이 "사건 없음"으로 보인다. 30년치라도
        1560행이고 진행마다 다시 읽지 않는다.
        """
        run = await self._repository.get(run_id, user_id)
        entries, _ = await self._repository.read_log(
            run_id, user_id, offset=0, limit=CAREER_WEEKS
        )
        # 옛 로그 행에는 주차별 스탯이 없다 — 그때만 최종 스탯으로 되돌아간다 (§3-D39).
        pairs = tuple((view.report, view.stats or run.stats) for view in entries)
        # 연대기는 살아 있는 팀 목록을 들고 걸어야 한다 — 주차마다 따로 굴리면
        # 존재한 적 없는 팀이 해체된다 (2026-08-10 감사).
        team_news = team_engine.chronicle(run.seed, run.week)
        scene_news = self._scene_news(run)
        roster_news = self._roster_news(run)
        belt_news = self._belt_news(run)
        items = news_feed.compile_feed(
            pairs,
            team_news,
            str(run.identity.name),
            run.seed,
            scene_news,
            roster_news,
            belt_news,
        )
        return NewsFeedPage(
            items=items[offset : offset + limit],
            total=len(items),
            offset=offset,
            seed=run.seed,
        )

    @staticmethod
    def _scene_news(run: CareerRun) -> tuple[SceneNews, ...]:
        return rivalry_scene.chronicle(
            run.seed,
            run.week,
            run.identity.gender,
            exclude=str(run.identity.name),
            brand=run.brand,
        )

    @staticmethod
    def _roster_news(run: CareerRun) -> tuple[RosterNews, ...]:
        return roster_scene.chronicle(
            run.week, run.identity.gender, run.brand, run.seed
        )

    @staticmethod
    def _belt_news(run: CareerRun) -> tuple[TitleNews, ...]:
        return title_news.chronicle(
            run.seed,
            run.week,
            run.identity.gender,
            run.brand,
            exclude=str(run.identity.name),
            skip=frozenset(run.titles_held),
        )

    async def retire(self, run_id: int, user_id: int) -> AdvanceResult:
        run = await self._repository.get(run_id, user_id)
        run.require_active()
        closed = run.ended(EndReason.PLAYER)
        saved = await self._repository.save(closed)
        return self._view(saved, StopReason.ENDED)

    # ── 체험판 (§3-D8) ────────────────────────────────────────

    def start_guest(self, command: GuestStartCommand) -> AdvanceResult:
        self._require_guest_mode(command.mode_code)
        run = self._new_run(
            name=command.name,
            mode_code=command.mode_code,
            based_on=command.based_on,
            gender=command.gender,
            country_code=command.country_code,
            play_style=command.play_style,
            seed=command.seed,
            user_id=None,
        )
        return self._view(run, StopReason.READY)

    def advance_guest(self, command: GuestAdvanceCommand) -> AdvanceResult:
        self._require_guest_mode(command.run.mode.code)
        self._require_unblocked(command.run)
        outcome = career_advance.advance(command.run, step=command.step)
        weeks = self._narrate(command.run, outcome)
        return self._view(outcome.run, outcome.stop_reason, weeks)

    def resume_guest(self, command: GuestResumeCommand) -> AdvanceResult:
        """다시 열었을 뿐이다 — **진행하지 않는다**. `current()`와 같은 자리다.

        대기 이벤트가 있으면 그대로 실어 보낸다. `_require_unblocked`를 부르지 않는
        이유가 여기 있다 — 재개에서 막으면 답할 화면 자체가 안 뜬다.
        """
        self._require_guest_mode(command.run.mode.code)
        return self._view(command.run, self._resting_reason(command.run))

    def choose_guest(self, command: GuestChooseCommand) -> AdvanceResult:
        self._require_guest_mode(command.run.mode.code)
        resolved = self._resolve(command.run, command.choice_code)
        return self._view(resolved, self._resting_reason(resolved))

    def set_guest_goal(self, command: GuestSetGoalCommand) -> AdvanceResult:
        """체험판의 분기 목표 (§3-D80). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        self._require_guest_mode(command.run.mode.code)
        chosen = quarter_plan.choose(command.run, _goal_of(command.goal_code))
        return self._view(chosen, self._resting_reason(chosen))

    def answer_guest_offer(self, command: GuestAnswerOfferCommand) -> AdvanceResult:
        """체험판의 재계약 협상 (§3-D84). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        self._require_guest_mode(command.run.mode.code)
        answered = contract_desk.answer(command.run, _offer_of(command.offer_code))
        return self._view(answered, self._resting_reason(answered))

    def cash_in_guest(self, command: GuestCashInCommand) -> AdvanceResult:
        """체험판의 가방 현금화 (§3-D85). 로그인 쪽과 **같은 도메인 동작**을 쓴다."""
        self._require_guest_mode(command.run.mode.code)
        cashed = briefcase_desk.cash_in(command.run)
        return self._view(cashed, self._resting_reason(cashed))

    def call_out_guest(self, command: GuestCallOutCommand) -> AdvanceResult:
        """체험판의 시비 걸기 (§3-D86)."""
        self._require_guest_mode(command.run.mode.code)
        opened = rivalry_desk.call_out(command.run, command.rival_name)
        return self._view(opened, self._resting_reason(opened))

    def read_guest_news(self, command: GuestResumeCommand) -> NewsFeedPage:
        """체험판 인박스 (§3-D67). **배경만** — 내 로그가 서버에 없다."""
        self._require_guest_mode(command.run.mode.code)
        items = news_feed.compile_feed(
            (),
            team_engine.chronicle(command.run.seed, command.run.week),
            str(command.run.identity.name),
            command.run.seed,
            self._scene_news(command.run),
            self._roster_news(command.run),
            self._belt_news(command.run),
        )
        return NewsFeedPage(
            items=items, total=len(items), offset=0, seed=command.run.seed
        )

    def read_guest_report(self, command: GuestReportCommand) -> ShowReport:
        """그 밤의 리포트, 체험판 (§3-D51).

        **로그를 되읽지 않는다** — 체험판 세이브에는 로그가 없다(§3-D8). 세울 수 있는
        것은 배경(그날의 벨트·그 무렵)이고 그것은 시드와 주차만으로 정해진다. 내 경기
        기록은 화면이 이미 그 줄에 들고 있으므로 서버가 다시 실어 보내지 않는다.

        **지나지 않은 주차는 거절한다.** 세이브를 고쳐 미래를 물으면 아직 일어나지 않은
        밤의 계보가 나온다 — 판정이 아니라 세계를 미리 보는 것이라 여기서 막는다.
        """
        self._require_guest_mode(command.run.mode.code)
        if command.week > command.run.week:
            raise ReportNotFoundError(f"{command.week}주차는 아직 지나지 않았습니다.")
        if not show_report.is_reportable(command.run, command.week):
            raise ReportNotFoundError(f"{command.week}주차는 대회 주차가 아닙니다.")
        return show_report.build_night(
            command.run,
            command.week,
            busy=command.busy,
            stakes=command.stakes,
            venue=self._narrator.venue_of(command.run, command.week),
        )

    # ── 메타 ──────────────────────────────────────────────────

    def modes(self) -> tuple[ModeView, ...]:
        return tuple(
            ModeView(
                code=mode.code.value,
                label=mode.code.value,
                weeks_per_tick=mode.weeks_per_tick,
                ticks=mode.total_ticks,
                event_budget=mode.event_budget,
                guest_allowed=mode.guest_allowed,
            )
            for mode in GAME_MODES.values()
        )

    def presets(self) -> tuple[PresetView, ...]:
        return tuple(
            PresetView(
                source=preset.source,
                gender=preset.gender,
                play_style=preset.play_style,
                country_code=preset.country.value,
            )
            for preset in PRESETS
        )

    # ── 내부 ──────────────────────────────────────────────────

    def _new_run(
        self,
        *,
        name: str,
        mode_code: str,
        based_on: str | None,
        gender: Gender | None,
        country_code: str | None,
        play_style: PlayStyle | None,
        seed: int | None,
        user_id: int | None,
    ) -> CareerRun:
        identity = build_identity(
            name=name,
            based_on=based_on,
            gender=gender,
            country=country_of(country_code),
            play_style=play_style,
        )
        return start_run(
            identity=identity,
            mode=game_mode_of(mode_code),
            seed=seed if seed is not None else self._seed_factory(),
            user_id=user_id,
        )

    def _resolve(self, run: CareerRun, choice_code: str) -> CareerRun:
        """선택을 반영한다. 종료 판정까지 여기서 끝낸다 — 커리어를 끝내는 선택지가 있다."""
        run.require_active()
        if not run.is_blocked:
            raise NoPendingEventError("선택할 이벤트가 없습니다.")
        resolved = event_draw.resolve_choice(run, choice_code)
        return career_end.close_if_ended(resolved)

    def _require_unblocked(self, run: CareerRun) -> None:
        run.require_active()
        if run.is_blocked:
            raise ChoiceRequiredError("먼저 선택을 마쳐야 합니다.")

    def _require_guest_mode(self, mode_code: str) -> None:
        """체험판은 `yearly`·`quarterly`만 (§3-D8 · §11-24).

        나머지 두 모드는 틱이 390·1560개라 상태가 브라우저에 안 들어간다.
        """
        if not game_mode_of(mode_code).guest_allowed:
            raise GuestModeNotAllowedError("이 모드는 로그인 후 플레이할 수 있습니다.")

    def _narrate(
        self, run: CareerRun, outcome: AdvanceOutcome
    ) -> tuple[WeekReportView, ...]:
        """리포트마다 문장을 붙인다.

        **서술은 그 주차를 만들어 낸 상태를 봐야 한다**(§narration_port). 진행이 끝난
        뒤의 세이브로 문장을 만들면 30주 뒤에 오른 인기도가 첫 주 승리 문장에 반영돼
        온도가 어긋난다. 그래서 리포트를 되짚으며 상태를 다시 굴린다.
        """

        views: list[WeekReportView] = []
        cursor = run
        for report in outcome.reports:
            views.append(
                WeekReportView(
                    report=report,
                    narration=self._narrator.narrate(cursor, report),
                    # 비트는 이 응답에만 살고 요약만 로그에 남는다 (§3-D34).
                    match_summary=(
                        report.sequence.summary if report.sequence else None
                    ),
                )
            )
            if cursor.is_active:
                cursor = apply_week(cursor, report)
            # **그 주차 끝의 스탯**을 붙인다 (§3-D39). 반영 전 값을 쓰면 그 주에 일어난
            # 힐턴이 다음 주 것으로 밀린다.
            views[-1] = replace(views[-1], stats=cursor.stats)
        return tuple(views)

    def _view(
        self,
        run: CareerRun,
        stop_reason: StopReason,
        weeks: tuple[WeekReportView, ...] = (),
    ) -> AdvanceResult:
        return AdvanceResult(
            run=run,
            weeks=weeks,
            stop_reason=stop_reason,
            pending_event=self._pending_view(run),
        )

    def _pending_view(self, run: CareerRun) -> PendingEventView | None:
        """대기 이벤트를 화면용으로. **본문 변주는 이미 골라져 있다.**"""
        pending = run.pending_event
        if pending is None:
            return None
        card = BY_CODE[pending.code]
        return PendingEventView(
            code=card.code,
            title=card.title,
            body=card.body_at(pending.body_index),
            choices=tuple(
                ChoiceView(code=choice.code, label=choice.label)
                for choice in card.choices
            ),
        )

    def _resting_reason(self, run: CareerRun) -> StopReason:
        """진행하지 않은 응답의 상태값. 끝났는지 · 막혔는지 · 그냥 서 있는지."""
        if not run.is_active:
            return StopReason.ENDED
        if run.is_blocked:
            return StopReason.EVENT
        # 협상이 열려 있으면 그것부터다 (§3-D84) — `advance`의 우선순위와 같아야 한다.
        # 여기서 순서가 갈리면 재개 화면과 진행 화면이 서로 다른 것을 물어본다.
        if contract_desk.is_open(run):
            return StopReason.OFFER
        # 목표를 아직 안 걸었으면 화면이 그 사실을 알아야 한다 (§3-D80).
        return StopReason.GOAL if quarter_plan.needs_goal(run) else StopReason.READY


def _goal_of(code: str) -> QuarterGoal:
    """코드 → 목표. 모르는 코드는 400이 되도록 도메인 예외로 바꾼다."""
    try:
        return QuarterGoal(code)
    except ValueError as exc:
        raise InvalidChoiceError(f"선택할 수 없는 목표입니다: {code}") from exc


def _offer_of(code: str) -> OfferChoice:
    """코드 → 협상 선택지 (§3-D84). `_goal_of`와 같은 모양이다."""
    try:
        return OfferChoice(code)
    except ValueError as exc:
        raise InvalidChoiceError(f"선택할 수 없는 항목입니다: {code}") from exc
