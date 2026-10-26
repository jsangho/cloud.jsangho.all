"""커리어 세이브 Postgres 어댑터. **규칙을 모른다.**

하는 일은 JSON 한 칸을 읽고 쓰는 것뿐이고, 모양은 `career_world_codec` 이 정한다.
그래서 게임 규칙이 늘어도 이 파일은 그대로다 — 지난번에 저장 계층이 규칙을 따라
불어난(마이그레이션 열두 개) 경로를 막는 자리다.

## 소유권은 쿼리가 지킨다

모든 조회·수정에 `user_id` 를 **함께** 건다. `career_id` 만으로 찾은 뒤 파이썬에서
소유자를 비교하는 방식은 한 줄을 빼먹으면 조용히 뚫린다. `shop_pg_repository` 가
같은 규칙을 쓴다.

**남의 것은 `None` 이다** — "있지만 네 것이 아니다" 를 구별해 주지 않는다. 구별하면
id 의 존재가 새어 나간다.

## 커밋이 한 번이다

`save` 가 세이브와 영수증을 **같은 커밋**에 넣는다. 둘로 쪼개면 그 틈에 프로세스가
죽었을 때 상태가 갈린다 — 세이브만 넘어갔으면 재시도가 또 적용되고, 영수증만
남았으면 하지 않은 일을 했다고 답한다.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.matrix.grid_oracle_database_manager import LAYER_LOG
from kayfabe.adapter.outbound.orm.career_sandbox_orm import (
    SandboxCareerModel,
    SandboxCareerRequestModel,
)
from kayfabe.adapter.outbound.pg.career_world_codec import dump, load
from kayfabe.app.ports.output.sandbox_career_repository import (
    RECEIPT_KEEP,
    CareerRow,
    DuplicateRequestError,
    RequestReceipt,
    SandboxCareerRepository,
)
from kayfabe.domain.services.career_world import WorldState

logger = LAYER_LOG


class SandboxCareerPgRepository(SandboxCareerRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, *, user_id: int, player_name: str, seed: int, state: WorldState
    ) -> int:
        row = SandboxCareerModel(
            user_id=user_id,
            player_name=player_name,
            seed=seed,
            season=state.season,
            week=state.week,
            phase=str(state.phase),
            world=dump(state),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.commit()
        logger.info("[SandboxCareerPg] created id=%s user=%s", row.id, user_id)
        return row.id

    async def list_for_user(self, user_id: int) -> list[CareerRow]:
        stmt = (
            select(SandboxCareerModel)
            .where(SandboxCareerModel.user_id == user_id)
            .order_by(SandboxCareerModel.updated_at.desc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            CareerRow(
                id=r.id,
                player_name=r.player_name,
                season=r.season,
                week=r.week,
                phase=r.phase,
                seed=r.seed,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def load(self, *, user_id: int, career_id: int) -> WorldState | None:
        row = await self._row(user_id=user_id, career_id=career_id, lock=False)
        return None if row is None else load(row.world)

    async def load_for_update(
        self, *, user_id: int, career_id: int
    ) -> WorldState | None:
        """**행을 잠그고** 읽는다. 같은 트랜잭션의 `save` 까지가 한 덩이다.

        잠그지 않으면 동시 요청 둘이 같은 주차를 읽고 둘 다 쓴다 — 멱등 키는
        같은 연산의 재시도를 막을 뿐, 서로 다른 두 연산의 경쟁은 막지 못한다.
        """
        row = await self._row(user_id=user_id, career_id=career_id, lock=True)
        return None if row is None else load(row.world)

    async def find_receipt(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> RequestReceipt | None:
        stmt = select(SandboxCareerRequestModel).where(
            SandboxCareerRequestModel.user_id == user_id,
            SandboxCareerRequestModel.career_id == career_id,
            SandboxCareerRequestModel.request_id == request_id,
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return RequestReceipt(
            request_id=row.request_id,
            fingerprint=row.fingerprint,
            response=row.response,
        )

    async def save(
        self,
        *,
        user_id: int,
        career_id: int,
        state: WorldState,
        receipt: RequestReceipt | None = None,
    ) -> None:
        row = await self._row(user_id=user_id, career_id=career_id, lock=False)
        if row is None:
            raise LookupError("커리어를 찾을 수 없습니다")
        row.world = dump(state)
        # 목록용 거울 칼럼. **정본은 JSON 이고 여기서만 복사한다.**
        row.season = state.season
        row.week = state.week
        row.phase = str(state.phase)
        if receipt is not None:
            self.db.add(
                SandboxCareerRequestModel(
                    user_id=user_id,
                    career_id=career_id,
                    request_id=receipt.request_id,
                    fingerprint=receipt.fingerprint,
                    response=receipt.response,
                )
            )
            try:
                await self.db.flush()
            except IntegrityError as e:
                # 고유 제약이 잡았다. **세이브 변경도 함께 되돌린다** — 커밋 전이라
                # flush 한 것까지가 전부다.
                await self.db.rollback()
                raise DuplicateRequestError(receipt.request_id) from e
            await self._prune_receipts(career_id)
        await self.db.commit()

    async def _prune_receipts(self, career_id: int) -> None:
        """이 커리어의 영수증을 최신 `RECEIPT_KEEP` 개로 자른다.

        **`id` 로 자른다.** `created_at` 은 `func.now()` 가 트랜잭션 시각이라 한
        트랜잭션 안의 여러 행이 같은 값을 갖는다 — 정렬이 흔들려 어느 것이 최신인지
        못 가린다. `id` 는 시퀀스라 단조 증가다.
        """
        keep = select(SandboxCareerRequestModel.id).where(
            SandboxCareerRequestModel.career_id == career_id
        )
        keep = keep.order_by(SandboxCareerRequestModel.id.desc()).limit(RECEIPT_KEEP)
        await self.db.execute(
            delete(SandboxCareerRequestModel).where(
                SandboxCareerRequestModel.career_id == career_id,
                SandboxCareerRequestModel.id.notin_(keep.scalar_subquery()),
            )
        )

    async def _row(
        self, *, user_id: int, career_id: int, lock: bool
    ) -> SandboxCareerModel | None:
        stmt = select(SandboxCareerModel).where(
            SandboxCareerModel.id == career_id,
            SandboxCareerModel.user_id == user_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()
