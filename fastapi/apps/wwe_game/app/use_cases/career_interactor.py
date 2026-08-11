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
    CareerLogPage,
    ChoiceView,
    ChooseCommand,
    GuestAdvanceCommand,
    GuestChooseCommand,
    GuestStartCommand,
    ModeView,
    NewsFeedPage,
    PendingEventView,
    PresetView,
    StartRunCommand,
    WeekReportView,
)
from wwe_game.app.ports.input.career_use_case import (
    CareerUseCase,
    ChoiceRequiredError,
    GuestModeNotAllowedError,
    NoPendingEventError,
    RunAlreadyActiveError,
)
from wwe_game.app.ports.output.career_repository import CareerRepository
from wwe_game.app.ports.output.narration_port import NarrationPort
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.constants.character_presets import PRESETS
from wwe_game.domain.constants.countries import country_of
from wwe_game.domain.constants.event_deck import BY_CODE
from wwe_game.domain.entities.career_run import CareerRun, EndReason, start_run
from wwe_game.domain.services import (
    career_advance,
    career_end,
    event_draw,
    news_feed,
    team_engine,
)
from wwe_game.domain.services.character_creation import build_identity
from wwe_game.domain.services.week_simulation import apply_week
from wwe_game.domain.value_objects.advance_outcome import AdvanceOutcome, StopReason
from wwe_game.domain.value_objects.game_mode import GAME_MODES, game_mode_of
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

    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> CareerLogPage:
        entries, total = await self._repository.read_log(
            run_id, user_id, offset=offset, limit=limit
        )
        return CareerLogPage(entries=entries, total=total, offset=offset)

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
        items = news_feed.compile_feed(pairs, team_news, str(run.identity.name))
        return NewsFeedPage(
            items=items[offset : offset + limit], total=len(items), offset=offset
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

    def choose_guest(self, command: GuestChooseCommand) -> AdvanceResult:
        self._require_guest_mode(command.run.mode.code)
        resolved = self._resolve(command.run, command.choice_code)
        return self._view(resolved, self._resting_reason(resolved))

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
        return StopReason.EVENT if run.is_blocked else StopReason.READY
