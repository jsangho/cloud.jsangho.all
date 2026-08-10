"""T8 진행 루프 — `auto`·`tick` 두 모드 · '다음'만으로 완주 · 대기 이벤트가 막는다.

리포지토리는 메모리 대역을 쓴다. **DB를 켜지 않는 이유**: 이 단위가 지키는 계약은
"규칙을 순서대로 부르고 한 번에 저장한다"이지 SQL이 아니다 — 그건 T9의 몫이다.
"""

from __future__ import annotations

import pytest
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
from wwe_game.app.dtos.career_dto import (
    AdvanceCommand,
    ChooseCommand,
    GuestAdvanceCommand,
    GuestStartCommand,
    StartRunCommand,
    WeekReportView,
)
from wwe_game.app.ports.input.career_use_case import (
    ChoiceRequiredError,
    GuestModeNotAllowedError,
    NoPendingEventError,
    RunAlreadyActiveError,
)
from wwe_game.app.ports.output.career_repository import (
    CareerRepository,
    RunNotFoundError,
)
from wwe_game.app.use_cases.career_interactor import CareerInteractor
from wwe_game.domain.constants.career_clock import CAREER_WEEKS
from wwe_game.domain.entities.career_run import CareerRun, EndReason
from wwe_game.domain.services.career_advance import MAX_WEEKS_PER_ADVANCE
from wwe_game.domain.value_objects.advance_outcome import StepMode, StopReason
from wwe_game.domain.value_objects.game_mode import game_mode_of
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle

USER = 1
OTHER_USER = 2


class MemoryRepository(CareerRepository):
    """메모리 대역. 세이브 하나와 로그만 든다 — 포트가 약속한 것이 그뿐이다."""

    def __init__(self) -> None:
        self.runs: dict[int, CareerRun] = {}
        self.log: dict[int, list[WeekReportView]] = {}
        self.saves = 0
        self._next_id = 1

    async def find_active(self, user_id: int) -> CareerRun | None:
        return next(
            (r for r in self.runs.values() if r.user_id == user_id and r.is_active),
            None,
        )

    async def get(self, run_id: int, user_id: int) -> CareerRun:
        run = self.runs.get(run_id)
        if run is None or run.user_id != user_id:
            raise RunNotFoundError("커리어를 찾을 수 없습니다.")
        return run

    async def save(
        self, run: CareerRun, weeks: tuple[WeekReportView, ...] = ()
    ) -> CareerRun:
        self.saves += 1
        if run.id is None:
            run = run.evolve(id=self._next_id)
            self._next_id += 1
        self.runs[run.id] = run
        self.log.setdefault(run.id, []).extend(weeks)
        return run

    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> tuple[tuple[WeekReportView, ...], int]:
        await self.get(run_id, user_id)
        entries = self.log.get(run_id, [])
        return tuple(entries[offset : offset + limit]), len(entries)


@pytest.fixture
def repo() -> MemoryRepository:
    return MemoryRepository()


@pytest.fixture
def interactor(repo: MemoryRepository) -> CareerInteractor:
    return CareerInteractor(
        repository=repo, narrator=RuleNarrator(), seed_factory=lambda: 4242
    )


def start_command(mode: str = "weekly", **extra: object) -> StartRunCommand:
    return StartRunCommand(
        user_id=USER,
        name="장상호",
        mode_code=mode,
        gender=Gender.MALE,
        country_code="KR",
        play_style=PlayStyle.TECHNICIAN,
        **extra,  # type: ignore[arg-type]
    )


class TestStart:
    @pytest.mark.asyncio
    async def test_a_new_career_begins_at_week_zero(
        self, interactor: CareerInteractor
    ) -> None:
        result = await interactor.start(start_command())
        assert result.run.week == 0
        assert result.run.id is not None
        assert result.stop_reason is StopReason.READY
        assert result.weeks == ()

    @pytest.mark.asyncio
    async def test_a_preset_fills_the_blanks(
        self, interactor: CareerInteractor
    ) -> None:
        result = await interactor.start(
            StartRunCommand(
                user_id=USER, name="장상호", mode_code="weekly", based_on="로만 레인즈"
            )
        )
        # 로만 레인즈의 CSV 값은 "All Rounder | Heel Style"이고 프리셋은 첫 값을 준다.
        assert result.run.identity.play_style is PlayStyle.ALL_ROUNDER

    @pytest.mark.asyncio
    async def test_a_second_career_is_refused(
        self, interactor: CareerInteractor
    ) -> None:
        await interactor.start(start_command())
        with pytest.raises(RunAlreadyActiveError):
            await interactor.start(start_command())

    @pytest.mark.asyncio
    async def test_retiring_frees_the_slot(self, interactor: CareerInteractor) -> None:
        first = await interactor.start(start_command())
        assert first.run.id is not None
        await interactor.retire(first.run.id, USER)
        assert (await interactor.start(start_command())).run.week == 0

    @pytest.mark.asyncio
    async def test_the_seed_is_injected(self, interactor: CareerInteractor) -> None:
        assert (await interactor.start(start_command())).run.seed == 4242


class TestAdvance:
    @pytest.mark.asyncio
    async def test_auto_runs_until_something_stops_it(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        result = await interactor.advance(
            AdvanceCommand(run_id=started.run.id, user_id=USER)
        )
        assert result.weeks
        assert result.stop_reason in {
            StopReason.EVENT,
            StopReason.PLE,
            StopReason.ENDED,
            StopReason.MAX_WEEKS,
        }
        assert result.run.week == len(result.weeks)

    @pytest.mark.asyncio
    async def test_tick_advances_exactly_one_tick(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command(mode="quarterly"))
        assert started.run.id is not None
        result = await interactor.advance(
            AdvanceCommand(run_id=started.run.id, user_id=USER, step=StepMode.TICK)
        )
        ticked = game_mode_of("quarterly").weeks_per_tick
        # 이벤트·PLE를 먼저 만나면 그 전에 선다 — 넘어가지만 않으면 된다.
        assert 1 <= len(result.weeks) <= ticked
        if result.stop_reason is StopReason.TICK:
            assert len(result.weeks) == ticked

    @pytest.mark.asyncio
    async def test_every_week_gets_a_sentence(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        result = await interactor.advance(
            AdvanceCommand(run_id=started.run.id, user_id=USER)
        )
        assert all(view.narration for view in result.weeks)
        assert all("{" not in view.narration for view in result.weeks)

    @pytest.mark.asyncio
    async def test_one_advance_saves_once(
        self, interactor: CareerInteractor, repo: MemoryRepository
    ) -> None:
        # 진행 한 번 = 저장 한 번 (§3-D6). 중간 상태를 흘리지 않는다.
        started = await interactor.start(start_command())
        assert started.run.id is not None
        before = repo.saves
        await interactor.advance(AdvanceCommand(run_id=started.run.id, user_id=USER))
        assert repo.saves == before + 1

    @pytest.mark.asyncio
    async def test_a_pending_event_blocks_progress(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        run_id = started.run.id
        for _ in range(60):
            result = await interactor.advance(
                AdvanceCommand(run_id=run_id, user_id=USER)
            )
            if result.stop_reason is StopReason.EVENT:
                assert result.pending_event is not None
                with pytest.raises(ChoiceRequiredError):
                    await interactor.advance(
                        AdvanceCommand(run_id=run_id, user_id=USER)
                    )
                return
            if result.stop_reason is StopReason.ENDED:
                break
        pytest.fail("이벤트를 한 번도 만나지 못했다")

    @pytest.mark.asyncio
    async def test_another_users_run_is_not_found(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        with pytest.raises(RunNotFoundError):
            await interactor.advance(
                AdvanceCommand(run_id=started.run.id, user_id=OTHER_USER)
            )


class TestChoose:
    @pytest.mark.asyncio
    async def test_a_choice_clears_the_block_and_advances_again(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        run_id = started.run.id
        for _ in range(60):
            result = await interactor.advance(
                AdvanceCommand(run_id=run_id, user_id=USER)
            )
            if result.stop_reason is StopReason.EVENT:
                assert result.pending_event is not None
                code = result.pending_event.choices[0].code
                answered = await interactor.choose(
                    ChooseCommand(run_id=run_id, user_id=USER, choice_code=code)
                )
                assert answered.pending_event is None
                assert not answered.run.is_blocked
                return
            if result.stop_reason is StopReason.ENDED:
                break
        pytest.fail("이벤트를 한 번도 만나지 못했다")

    @pytest.mark.asyncio
    async def test_choosing_without_an_event_is_refused(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command())
        assert started.run.id is not None
        with pytest.raises(NoPendingEventError):
            await interactor.choose(
                ChooseCommand(
                    run_id=started.run.id, user_id=USER, choice_code="아무거나"
                )
            )


class TestFullCareer:
    @pytest.mark.asyncio
    async def test_next_alone_finishes_a_career(
        self, interactor: CareerInteractor
    ) -> None:
        """§11-1 — '다음'만 눌러도 끝까지 간다. 선택은 늘 첫 항목으로."""
        started = await interactor.start(start_command())
        assert started.run.id is not None
        run_id = started.run.id
        clicks = 0
        result = started
        while not result.run.end_reason and clicks < 4000:
            clicks += 1
            if result.pending_event is not None:
                result = await interactor.choose(
                    ChooseCommand(
                        run_id=run_id,
                        user_id=USER,
                        choice_code=result.pending_event.choices[0].code,
                    )
                )
                continue
            result = await interactor.advance(
                AdvanceCommand(run_id=run_id, user_id=USER)
            )
        assert result.run.end_reason is not None, f"{clicks}번 눌러도 안 끝났다"
        assert result.ended or result.run.end_reason is not None

    @pytest.mark.asyncio
    async def test_the_log_collects_every_week(
        self, interactor: CareerInteractor
    ) -> None:
        started = await interactor.start(start_command(mode="yearly"))
        assert started.run.id is not None
        run_id = started.run.id
        for _ in range(5):
            result = await interactor.advance(
                AdvanceCommand(run_id=run_id, user_id=USER)
            )
            if result.pending_event is not None:
                await interactor.choose(
                    ChooseCommand(
                        run_id=run_id,
                        user_id=USER,
                        choice_code=result.pending_event.choices[0].code,
                    )
                )
        page = await interactor.read_log(run_id, USER, limit=10)
        assert page.total > 0
        assert len(page.entries) <= 10
        assert page.entries[0].week == 1


class TestSafetyCeiling:
    def test_an_advance_never_runs_forever(self) -> None:
        """§3-D5 — 멈춤 조건을 못 만나도 상한에서 선다."""
        from wwe_game.domain.services import career_advance

        # 예산을 다 쓴 세이브는 이벤트가 안 뜨고, yearly는 PLE에서도 안 선다.
        run = make_run(mode="yearly", week=100).evolve(
            events_fired=game_mode_of("yearly").event_budget
        )
        outcome = career_advance.advance(run)
        assert outcome.stop_reason is StopReason.MAX_WEEKS
        assert outcome.weeks_advanced == MAX_WEEKS_PER_ADVANCE

    def test_the_ceiling_never_runs_past_the_career(self) -> None:
        from wwe_game.domain.services import career_advance

        run = make_run(mode="yearly", week=CAREER_WEEKS - 3).evolve(
            events_fired=game_mode_of("yearly").event_budget
        )
        outcome = career_advance.advance(run)
        assert outcome.run.week <= CAREER_WEEKS
        assert outcome.stop_reason in {StopReason.MAX_WEEKS, StopReason.ENDED}

    def test_a_closed_career_cannot_advance(self) -> None:
        from wwe_game.domain.exceptions import RunNotActiveError
        from wwe_game.domain.services import career_advance

        closed = make_run().ended(EndReason.PLAYER)
        with pytest.raises(RunNotActiveError):
            career_advance.advance(closed)


class TestGuest:
    def test_a_guest_can_play_the_allowed_modes(
        self, interactor: CareerInteractor
    ) -> None:
        started = interactor.start_guest(
            GuestStartCommand(
                name="장상호",
                mode_code="yearly",
                gender=Gender.MALE,
                country_code="KR",
                play_style=PlayStyle.TECHNICIAN,
                seed=7,
            )
        )
        assert started.run.user_id is None
        result = interactor.advance_guest(GuestAdvanceCommand(run=started.run))
        assert result.weeks
        assert result.run.week == len(result.weeks)

    @pytest.mark.parametrize("mode", ["monthly", "weekly"])
    def test_locked_modes_are_refused(
        self, interactor: CareerInteractor, mode: str
    ) -> None:
        with pytest.raises(GuestModeNotAllowedError):
            interactor.start_guest(
                GuestStartCommand(
                    name="장상호",
                    mode_code=mode,
                    gender=Gender.MALE,
                    country_code="KR",
                    play_style=PlayStyle.TECHNICIAN,
                )
            )

    def test_a_guest_run_is_never_saved(
        self, interactor: CareerInteractor, repo: MemoryRepository
    ) -> None:
        started = interactor.start_guest(
            GuestStartCommand(
                name="장상호",
                mode_code="yearly",
                gender=Gender.MALE,
                country_code="KR",
                play_style=PlayStyle.TECHNICIAN,
            )
        )
        interactor.advance_guest(GuestAdvanceCommand(run=started.run))
        assert repo.saves == 0
        assert repo.runs == {}

    def test_the_guest_shares_the_login_rules(
        self, interactor: CareerInteractor
    ) -> None:
        """§11-25 — 같은 규칙이라 같은 시드는 같은 결과를 낸다."""
        from wwe_game.domain.services import career_advance

        guest = interactor.start_guest(
            GuestStartCommand(
                name="장상호",
                mode_code="yearly",
                gender=Gender.MALE,
                country_code="KR",
                play_style=PlayStyle.TECHNICIAN,
                seed=99,
            )
        )
        direct = career_advance.advance(guest.run)
        through_use_case = interactor.advance_guest(GuestAdvanceCommand(run=guest.run))
        assert direct.run == through_use_case.run
        assert direct.stop_reason is through_use_case.stop_reason


class TestMeta:
    def test_four_modes_with_guest_flags(self, interactor: CareerInteractor) -> None:
        modes = interactor.modes()
        assert len(modes) == 4
        assert {m.code for m in modes if m.guest_allowed} == {"yearly", "quarterly"}

    def test_presets_are_offered_for_creation(
        self, interactor: CareerInteractor
    ) -> None:
        presets = interactor.presets()
        assert len(presets) >= 150
        assert all(p.country_code for p in presets)
