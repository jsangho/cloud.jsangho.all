"""세이브 저장소 — PostgreSQL 구현 (하네스 §6 · T9).

`CareerRepository`의 두 구현 중 하나다. 다른 하나는 체험판의 메모리 어댑터로, **같은
유스케이스가 둘을 갈아 낀다**(§3-D8 · §11-25).

## 저장은 진행 단위로 한 번 (§3-D6)

`save()` 한 번이 세이브 갱신 · 대립 교체 · 1회성 이벤트 · 트로피 · 주차 로그를 **한
트랜잭션**으로 처리한다. 커밋은 하지 않는다 — 세션의 수명은 요청이 쥐고 있고(FastAPI
`Depends`), 중간에 커밋하면 라우터가 롤백할 여지가 사라진다.

## 대립만 지웠다 다시 넣는다

로그·1회성 이벤트·트로피는 **쌓이기만 하므로** 없는 것만 덧붙인다. 대립은 사라지기도
하고 열기가 바뀌기도 해서(§3-D2), 두 줄짜리 목록을 비교하느니 지우고 다시 넣는 쪽이
짧고 틀릴 여지가 없다 — 동시에 살아 있는 대립은 최대 두 개다.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from wwe_game.adapter.outbound.mappers.career_mapper import CareerMapper
from wwe_game.adapter.outbound.orm.career_orm import (
    CareerLogEntryModel,
    CareerRivalryModel,
    CareerRunModel,
    CareerSeenEventModel,
    CareerTrophyModel,
)
from wwe_game.app.dtos.career_dto import WeekReportView
from wwe_game.app.ports.output.career_repository import (
    CareerRepository,
    RunNotFoundError,
)
from wwe_game.domain.entities.career_run import CareerRun, RunStatus, Trophy


class CareerPgRepository(CareerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 조회 ──────────────────────────────────────────────────

    async def find_active(self, user_id: int) -> CareerRun | None:
        row = await self.session.scalar(
            select(CareerRunModel).where(
                CareerRunModel.user_id == user_id,
                CareerRunModel.status == RunStatus.ACTIVE.value,
            )
        )
        return await self._hydrate(row) if row is not None else None

    async def get(self, run_id: int, user_id: int) -> CareerRun:
        row = await self._row_or_raise(run_id, user_id)
        return await self._hydrate(row)

    async def _row_or_raise(self, run_id: int, user_id: int) -> CareerRunModel:
        """없는 것과 남의 것을 **구분하지 않는다** — 존재 여부가 새면 안 된다(§11-12)."""
        row = await self.session.scalar(
            select(CareerRunModel).where(
                CareerRunModel.id == run_id, CareerRunModel.user_id == user_id
            )
        )
        if row is None:
            raise RunNotFoundError("커리어를 찾을 수 없습니다.")
        return row

    async def _hydrate(self, row: CareerRunModel) -> CareerRun:
        """세이브에 자식 표를 붙인다. **로그는 붙이지 않는다** — 30년이면 1560줄이다."""
        rivalries = (
            await self.session.scalars(
                select(CareerRivalryModel)
                .where(CareerRivalryModel.run_id == row.id)
                .order_by(CareerRivalryModel.heat.desc())
            )
        ).all()
        seen = (
            await self.session.scalars(
                select(CareerSeenEventModel.code).where(
                    CareerSeenEventModel.run_id == row.id
                )
            )
        ).all()
        trophies = (
            await self.session.scalars(
                select(CareerTrophyModel)
                .where(CareerTrophyModel.run_id == row.id)
                .order_by(CareerTrophyModel.week)
            )
        ).all()
        return CareerMapper.to_domain(
            row,
            rivalries=tuple(rivalries),
            seen_events=frozenset(seen),
            trophies=tuple(Trophy(code=t.code, week=t.week) for t in trophies),
        )

    # ── 저장 ──────────────────────────────────────────────────

    async def save(
        self, run: CareerRun, weeks: tuple[WeekReportView, ...] = ()
    ) -> CareerRun:
        row = (
            await self._row_or_raise(run.id, run.user_id)  # type: ignore[arg-type]
            if run.id is not None
            else CareerRunModel()
        )
        CareerMapper.apply_to_row(row, run)
        if run.id is None:
            self.session.add(row)
            await self.session.flush()  # id가 있어야 자식 표를 붙인다

        run_id = row.id
        await self._replace_rivalries(run_id, run)
        await self._append_codes(CareerSeenEventModel, run_id, set(run.seen_events))
        await self._append_trophies(run_id, run)
        await self._append_log(run_id, weeks)
        await self.session.flush()
        return run.evolve(id=run_id)

    async def _replace_rivalries(self, run_id: int, run: CareerRun) -> None:
        await self.session.execute(
            delete(CareerRivalryModel).where(CareerRivalryModel.run_id == run_id)
        )
        for rivalry in run.rivalries:
            self.session.add(
                CareerRivalryModel(
                    run_id=run_id,
                    rival_name=rivalry.rival_name,
                    stage=rivalry.stage.value,
                    heat=rivalry.heat,
                    started_week=rivalry.started_week,
                )
            )

    async def _append_codes(
        self,
        model: type[CareerSeenEventModel],
        run_id: int,
        codes: set[str],
    ) -> None:
        """이미 있는 코드는 건너뛴다. 유니크 제약이 마지막 방어선이다."""
        existing = set(
            (
                await self.session.scalars(
                    select(model.code).where(model.run_id == run_id)
                )
            ).all()
        )
        for code in sorted(codes - existing):
            self.session.add(model(run_id=run_id, code=code))

    async def _append_trophies(self, run_id: int, run: CareerRun) -> None:
        existing = set(
            (
                await self.session.scalars(
                    select(CareerTrophyModel.code).where(
                        CareerTrophyModel.run_id == run_id
                    )
                )
            ).all()
        )
        for trophy in run.trophies:
            if trophy.code not in existing:
                self.session.add(
                    CareerTrophyModel(run_id=run_id, code=trophy.code, week=trophy.week)
                )

    async def _append_log(self, run_id: int, weeks: tuple[WeekReportView, ...]) -> None:
        """주차 로그를 이어 붙인다. **같은 주차를 두 번 쓰지 않는다.**

        진행이 실패해 재시도되면 같은 주차가 다시 올 수 있다. 유니크 제약이 막지만,
        거기까지 가면 트랜잭션 전체가 죽는다 — 먼저 걸러 낸다.
        """
        if not weeks:
            return
        written = set(
            (
                await self.session.scalars(
                    select(CareerLogEntryModel.week).where(
                        CareerLogEntryModel.run_id == run_id
                    )
                )
            ).all()
        )
        for view in weeks:
            if view.week not in written:
                self.session.add(CareerMapper.log_row(run_id, view))

    # ── 로그 ──────────────────────────────────────────────────

    async def read_log(
        self, run_id: int, user_id: int, *, offset: int = 0, limit: int = 50
    ) -> tuple[tuple[WeekReportView, ...], int]:
        await self._row_or_raise(run_id, user_id)
        total = await self.session.scalar(
            select(func.count())
            .select_from(CareerLogEntryModel)
            .where(CareerLogEntryModel.run_id == run_id)
        )
        rows = (
            await self.session.scalars(
                select(CareerLogEntryModel)
                .where(CareerLogEntryModel.run_id == run_id)
                .order_by(CareerLogEntryModel.week)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return tuple(CareerMapper.log_view(row) for row in rows), int(total or 0)
