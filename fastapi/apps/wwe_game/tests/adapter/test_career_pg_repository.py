"""T9 영속화 — 세이브·재개가 실제 DB에서 동작한다 (대기 이벤트·컨디션 포함).

SQLite 인메모리에서 진짜 쿼리를 돌린다. 검증 대상은 **왕복**이다 — 저장한 세이브를 다시
읽었을 때 같은 커리어인가. kayfabe의 어댑터 테스트와 같은 방식이다.

실행 (반드시 `fastapi/` 안에서):

    PYTHONUTF8=1 PYTHONPATH=apps:. uv run pytest apps/wwe_game/tests
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from _helpers import make_run  # noqa: I001  (tests 트리에 __init__.py가 없다)
from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from wwe_game.adapter.outbound.narration.rule_narrator import RuleNarrator
from wwe_game.adapter.outbound.pg.career_pg_repository import CareerPgRepository
from wwe_game.app.dtos.career_dto import AdvanceCommand, StartRunCommand, WeekReportView
from wwe_game.app.ports.output.career_repository import RunNotFoundError
from wwe_game.app.use_cases.career_interactor import CareerInteractor
from wwe_game.domain.entities.career_run import (
    CareerRun,
    EndReason,
    EventInstance,
    Rivalry,
    RivalryStage,
    Trophy,
)
from wwe_game.domain.services.week_simulation import apply_week, simulate_week
from wwe_game.domain.value_objects.condition import Condition, InjuryGrade
from wwe_game.domain.value_objects.match_kind import MatchKind
from wwe_game.domain.value_objects.title import Brand, Title
from wwe_game.domain.value_objects.week_report import OutcomeKind, WeekKind, WeekReport
from wwe_game.domain.value_objects.wrestler_identity import Gender, PlayStyle
from wwe_game.domain.value_objects.wrestler_stats import WrestlerStats

USER = 1
OTHER_USER = 2


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        # `users`까지 만들어야 FK가 선다 — 세이브는 사용자에 매인다.
        import core.entities.user_model  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as opened:
        yield opened
    await engine.dispose()


@pytest.fixture
def repo(session: AsyncSession) -> CareerPgRepository:
    return CareerPgRepository(session)


def saved_run(**changes: object) -> CareerRun:
    return make_run(**changes).evolve(user_id=USER)  # type: ignore[arg-type]


class TestRoundTrip:
    @pytest.mark.asyncio
    async def test_a_new_run_gets_an_id(self, repo: CareerPgRepository) -> None:
        stored = await repo.save(saved_run())
        assert stored.id is not None

    @pytest.mark.asyncio
    async def test_the_whole_save_survives(self, repo: CareerPgRepository) -> None:
        run = saved_run(
            week=400,
            brand=Brand.RAW,
            titles_won=(Title.INTERCONTINENTAL_CHAMPIONSHIP,) * 2,
            titles_held=frozenset({Title.INTERCONTINENTAL_CHAMPIONSHIP}),
        ).evolve(
            flags=frozenset({"fined", "painkiller_habit"}),
            recent_events=("a", "b", "a"),
            events_fired=42,
            release_weeks=3,
            decline_weeks=5,
            # **협상은 반드시 살아남아야 한다** (§3-D84). 답할 때까지 진행이 막히므로,
            # 이 칸이 안 남으면 새로고침 한 번에 협상이 사라지고 계약 없이 뛴다.
            offer_week=400,
        )
        stored = await repo.save(run)
        loaded = await repo.get(stored.id, USER)
        assert loaded == stored
        assert loaded.offer_week == 400

    @pytest.mark.asyncio
    async def test_a_pending_event_survives(self, repo: CareerPgRepository) -> None:
        # 대기 이벤트가 안 살아남으면 재개했을 때 진행이 막히지 않는다 (§3-D2).
        run = saved_run().evolve(
            pending_event=EventInstance(
                code="ring_time_cut", week=12, body_index=2, rival_name="코디 로즈"
            )
        )
        loaded = await repo.get((await repo.save(run)).id, USER)
        assert loaded.is_blocked
        assert loaded.pending_event == run.pending_event

    @pytest.mark.asyncio
    async def test_the_condition_survives(self, repo: CareerPgRepository) -> None:
        run = saved_run(
            condition=Condition(grade=InjuryGrade.SERIOUS, weeks_left=14, wear=63)
        )
        loaded = await repo.get((await repo.save(run)).id, USER)
        assert loaded.condition == run.condition
        assert loaded.condition.is_injured

    @pytest.mark.asyncio
    async def test_rivalries_survive(self, repo: CareerPgRepository) -> None:
        run = saved_run(
            rivalries=(
                Rivalry("코디 로즈", RivalryStage.NEMESIS, 80, 10),
                Rivalry("건서", RivalryStage.HEATED, 40, 30),
            )
        )
        loaded = await repo.get((await repo.save(run)).id, USER)
        assert {r.rival_name for r in loaded.rivalries} == {"코디 로즈", "건서"}
        assert loaded.rivalries[0].heat == 80  # 뜨거운 쪽이 먼저

    @pytest.mark.asyncio
    async def test_seen_events_and_trophies_survive(
        self, repo: CareerPgRepository
    ) -> None:
        run = saved_run().evolve(
            seen_events=frozenset({"act1_debut_night", "callup_live_hole"}),
            trophies=(Trophy(code="grand_slam", week=800),),
        )
        loaded = await repo.get((await repo.save(run)).id, USER)
        assert loaded.seen_events == run.seen_events
        assert loaded.trophies == run.trophies


class TestActiveSlot:
    @pytest.mark.asyncio
    async def test_the_active_run_is_found(self, repo: CareerPgRepository) -> None:
        stored = await repo.save(saved_run())
        found = await repo.find_active(USER)
        assert found is not None
        assert found.id == stored.id

    @pytest.mark.asyncio
    async def test_a_closed_run_is_not_active(self, repo: CareerPgRepository) -> None:
        await repo.save(saved_run().ended(EndReason.PLAYER))
        assert await repo.find_active(USER) is None

    @pytest.mark.asyncio
    async def test_another_users_run_is_invisible(
        self, repo: CareerPgRepository
    ) -> None:
        stored = await repo.save(saved_run())
        assert await repo.find_active(OTHER_USER) is None
        with pytest.raises(RunNotFoundError):
            await repo.get(stored.id, OTHER_USER)


class TestLog:
    @staticmethod
    def views(count: int) -> tuple[WeekReportView, ...]:
        return tuple(
            WeekReportView(
                report=WeekReport(week=w, kind=WeekKind.PROMO), narration=f"{w}주차"
            )
            for w in range(1, count + 1)
        )

    @pytest.mark.asyncio
    async def test_the_log_is_appended_and_paged(
        self, repo: CareerPgRepository
    ) -> None:
        stored = await repo.save(saved_run(), self.views(30))
        page, total = await repo.read_log(stored.id, USER, offset=10, limit=5)
        assert total == 30
        assert [v.week for v in page] == [11, 12, 13, 14, 15]
        assert page[0].narration == "11주차"

    @pytest.mark.asyncio
    async def test_the_same_week_is_never_written_twice(
        self, repo: CareerPgRepository
    ) -> None:
        # 진행이 재시도되면 같은 주차가 다시 온다. 유니크 제약까지 가면 트랜잭션이 죽는다.
        stored = await repo.save(saved_run(), self.views(5))
        await repo.save(stored, self.views(5))
        _, total = await repo.read_log(stored.id, USER)
        assert total == 5

    @pytest.mark.asyncio
    async def test_the_match_survives_a_round_trip(
        self, repo: CareerPgRepository
    ) -> None:
        """다시 연 로그도 **진행 중인 화면과 같은 줄**을 그린다 (§3-D32·D34).

        상대·형식이 안 남으면 그 밤이 럼블이었는지 싱글이었는지 알 수 없고, 요약이
        안 남으면 30인 경기가 결과 한 글자로 줄어든다.
        """
        view = WeekReportView(
            report=WeekReport(
                week=1,
                kind=WeekKind.PLE,
                result=OutcomeKind.WIN,
                opponent="세스 롤린스",
                match_kind=MatchKind.BATTLE_ROYAL,
            ),
            narration="1주차",
            match_summary="17번으로 입장 · 3명 탈락 · 우승(30인)",
        )
        stored = await repo.save(saved_run(), (view,))
        page, _ = await repo.read_log(stored.id, USER)
        assert page[0].report.match_kind is MatchKind.BATTLE_ROYAL
        assert page[0].report.opponent == "세스 롤린스"
        assert page[0].match_summary == "17번으로 입장 · 3명 탈락 · 우승(30인)"

    @pytest.mark.asyncio
    async def test_each_week_keeps_its_own_alignment(
        self, repo: CareerPgRepository
    ) -> None:
        """뉴스가 **그 주차의** 성향을 봐야 한다 (§3-D39).

        저장하지 않던 시절 호출자는 모든 주차에 최종 스탯을 넘겼고, 그래서 힐턴
        이전의 대관에도 야유가 붙었다 — `compile_feed`의 설명이 경고하던 상황이다.
        """
        views = tuple(
            WeekReportView(
                report=WeekReport(week=w, kind=WeekKind.PROMO),
                narration=f"{w}주차",
                stats=WrestlerStats(popularity=w * 10, alignment=-40 + w * 20),
            )
            for w in (1, 2, 3)
        )
        stored = await repo.save(saved_run(), views)
        page, _ = await repo.read_log(stored.id, USER)
        assert [v.stats.alignment for v in page] == [-20, 0, 20]
        assert [v.stats.popularity for v in page] == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_old_rows_have_no_stats(self, repo: CareerPgRepository) -> None:
        """이 마이그레이션 이전 행은 None이다 — 그때는 최종 스탯으로 되돌아간다."""
        stored = await repo.save(saved_run(), self.views(2))
        page, _ = await repo.read_log(stored.id, USER)
        assert all(v.stats is None for v in page)

    @pytest.mark.asyncio
    async def test_beats_are_not_stored(self, repo: CareerPgRepository) -> None:
        """**비트는 저장하지 않는다** — 럼블 하나가 59줄이다 (2026-08-11 결정).

        요약만 남고 타임라인은 그 '다음'을 누른 화면에서 끝난다.
        """
        stored = await repo.save(saved_run(), self.views(3))
        page, _ = await repo.read_log(stored.id, USER)
        assert all(v.report.sequence is None for v in page)

    @pytest.mark.asyncio
    async def test_the_log_is_not_dragged_into_the_save(
        self, repo: CareerPgRepository
    ) -> None:
        # 30년이면 1560줄이다 — 재개할 때마다 끌고 오면 안 된다.
        stored = await repo.save(saved_run(), self.views(20))
        loaded = await repo.get(stored.id, USER)
        assert loaded == stored


class TestResume:
    @pytest.mark.asyncio
    async def test_a_career_continues_where_it_stopped(
        self, session: AsyncSession
    ) -> None:
        """§10-T9 — 저장하고 다시 불러 이어서 진행한다."""
        interactor = CareerInteractor(
            repository=CareerPgRepository(session),
            narrator=RuleNarrator(),
            seed_factory=lambda: 777,
        )
        started = await interactor.start(
            StartRunCommand(
                user_id=USER,
                name="장상호",
                mode_code="quarterly",
                gender=Gender.MALE,
                country_code="KR",
                play_style=PlayStyle.TECHNICIAN,
            )
        )
        run_id = started.run.id
        assert run_id is not None
        first = await interactor.advance(AdvanceCommand(run_id=run_id, user_id=USER))

        # 새 인터랙터 — 메모리에 남은 상태 없이 DB에서만 이어 간다.
        resumed = CareerInteractor(
            repository=CareerPgRepository(session), narrator=RuleNarrator()
        )
        current = await resumed.current(USER)
        assert current is not None
        assert current.run.week == first.run.week
        assert current.run == first.run

        if current.pending_event is None:
            more = await resumed.advance(AdvanceCommand(run_id=run_id, user_id=USER))
            assert more.run.week > first.run.week

    @pytest.mark.asyncio
    async def test_the_replay_matches_an_uninterrupted_run(
        self, repo: CareerPgRepository
    ) -> None:
        """저장을 거쳐도 시드 재현이 깨지지 않는다 (§11-4)."""
        run = saved_run(seed=31, week=0)
        direct = run
        for _ in range(20):
            direct = apply_week(direct, simulate_week(direct))

        through_db = run
        for _ in range(20):
            through_db = apply_week(through_db, simulate_week(through_db))
            stored = await repo.save(through_db)
            through_db = await repo.get(stored.id, USER)

        assert through_db.week == direct.week
        assert through_db.stats == direct.stats
        assert through_db.condition == direct.condition
