"""상점 Postgres 어댑터 — 잔액 조회 · 구매 · 보유 조회.

설계 배경은 `fastapi/_docs/shop-point-ledger.md` §4·§5.
"""

from __future__ import annotations

from core.entities.user_model import UserModel
from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.shop_orm import (
    COSMETIC_CATEGORIES,
    PointLedgerEntryModel,
    PointLedgerEntryType,
    ShopItemModel,
    UserShopItemModel,
)
from kayfabe.adapter.outbound.pg.point_aggregation import earned_points_subquery
from kayfabe.app.dtos.shop_dto import (
    InventoryItemResponse,
    PurchaseCommand,
    PurchaseReceipt,
    ShopItemResponse,
    WalletResponse,
)
from kayfabe.app.exceptions import (
    AlreadyOwnedError,
    InsufficientPointsError,
    ShopItemNotFoundError,
    ShopItemUnavailableError,
)
from kayfabe.app.ports.output.shop_repository import ShopRepository
from kayfabe.domain.value_objects.point_balance import PointBalance, resolve_context_key

logger = LAYER_LOG


class ShopPgRepository(ShopRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _to_item_dto(row: ShopItemModel) -> ShopItemResponse:
        return ShopItemResponse(
            code=row.code,
            name=row.name,
            # ORM에서 nullable이라 화면용 DTO에서는 빈 문자열로 굳힌다.
            description=row.description or "",
            price=row.price,
            category=row.category,
            is_consumable=row.is_consumable,
        )

    async def list_active_items(self) -> list[ShopItemResponse]:
        stmt = (
            select(ShopItemModel)
            .where(ShopItemModel.is_active.is_(True))
            .order_by(ShopItemModel.category, ShopItemModel.price, ShopItemModel.code)
        )
        result = await self.db.execute(stmt)
        rows = [self._to_item_dto(r) for r in result.scalars().all()]
        logger.info("[ShopPgRepository] list_active_items <- Neon count=%d", len(rows))
        return rows

    async def _load_balance(self, user_id: int) -> PointBalance:
        """획득액과 원장 합계를 각각 집계해 잔액을 만든다.

        획득액 집계는 순위표와 같은 정의를 쓴다 — `point_aggregation`.
        한 쿼리로 합치지 않는 이유는 예측 행과 원장 행을 조인하면 카티션 곱이 생겨
        양쪽이 서로의 행 수만큼 부풀기 때문이다.

        `earned_points_subquery`는 `HAVING graded > 0`이라 채점된 예측이 없는
        사용자는 **행 자체가 없다**. 그 경우 획득액을 0으로 본다.
        """
        agg = earned_points_subquery(user_id=user_id)
        earned = (await self.db.execute(select(agg.c.score))).scalar_one_or_none()

        ledger_stmt = select(
            func.coalesce(func.sum(PointLedgerEntryModel.amount), 0)
        ).where(PointLedgerEntryModel.user_id == user_id)
        ledger_total = (await self.db.execute(ledger_stmt)).scalar_one()

        return PointBalance(
            earned=int(earned or 0), ledger_total=int(ledger_total or 0)
        )

    async def get_wallet(self, user_id: int) -> WalletResponse:
        balance = await self._load_balance(user_id)
        logger.info(
            "[ShopPgRepository] get_wallet <- Neon user=%d balance=%d",
            user_id,
            balance.balance,
        )
        return WalletResponse(
            earned=balance.earned,
            spent=balance.spent,
            balance=balance.balance,
        )

    async def purchase(self, command: PurchaseCommand) -> PurchaseReceipt:
        # 1. 사용자 행을 잠근다. 잔액 확인과 원장 삽입 사이에 같은 사용자의 다른
        #    구매가 끼어들면 잔액을 초과해 쓸 수 있다. 유니크 제약은 같은 아이템
        #    중복만 막지 서로 다른 아이템 두 개의 동시 구매는 막지 못한다.
        #    사용자별 잠금이라 다른 사용자의 구매는 막지 않는다.
        lock_stmt = (
            select(UserModel.id)
            .where(UserModel.id == command.user_id)
            .with_for_update()
        )
        locked = (await self.db.execute(lock_stmt)).scalar_one_or_none()
        if locked is None:
            raise LookupError(f"회원 {command.user_id}를 찾을 수 없습니다.")

        # 2. 가격의 유일한 출처는 이 행이다. 요청 본문의 가격은 쓰지 않는다.
        item_stmt = select(ShopItemModel).where(ShopItemModel.code == command.item_code)
        item = (await self.db.execute(item_stmt)).scalar_one_or_none()
        if item is None:
            raise ShopItemNotFoundError(
                f"상품 '{command.item_code}'를 찾을 수 없습니다."
            )
        if not item.is_active:
            raise ShopItemUnavailableError(f"'{item.name}'은(는) 판매 중이 아닙니다.")

        # 상품 값을 여기서 스칼라로 뽑아 둔다. 플러시가 실패하면 세션이 죽어서
        # ORM 속성 접근이 PendingRollbackError를 던지고, 그러면 실패 사유를
        # 알려 주려던 자리에서 엉뚱한 500이 나간다.
        item_id, item_code, item_name = item.id, item.code, item.name
        price, is_consumable = item.price, item.is_consumable

        context_key = resolve_context_key(
            is_consumable=is_consumable, context_key=command.context_key
        )

        # 3. 잔액 확인. 잠금 이후에 읽어야 최신 값이다.
        balance = await self._load_balance(command.user_id)
        if not balance.can_afford(price):
            raise InsufficientPointsError(price=price, balance=balance.balance)

        # 4. 원장은 추가 전용이다. 지출은 음수로 넣는다.
        self.db.add(
            PointLedgerEntryModel(
                user_id=command.user_id,
                amount=-price,
                entry_type=PointLedgerEntryType.PURCHASE,
                shop_item_id=item_id,
                memo="",
            )
        )
        owned = UserShopItemModel(
            user_id=command.user_id,
            shop_item_id=item_id,
            context_key=context_key,
        )
        self.db.add(owned)

        try:
            await self.db.flush()
        except IntegrityError as e:
            # 중복 보유의 최종 방어선은 uq_user_shop_item 제약이다.
            # 사전 조회로 걸러도 동시 요청은 여기까지 온다.
            raise AlreadyOwnedError(f"이미 보유한 아이템입니다: {item_name}") from e

        logger.info(
            "[ShopPgRepository] purchase -> Neon user=%d item=%s price=%d",
            command.user_id,
            item_code,
            price,
        )
        return PurchaseReceipt(
            inventory_id=owned.id,
            item_code=item_code,
            price=price,
            balance_after=balance.balance - price,
        )

    @staticmethod
    def _to_inventory_dto(
        owned: UserShopItemModel, item: ShopItemModel
    ) -> InventoryItemResponse:
        return InventoryItemResponse(
            id=owned.id,
            item_code=item.code,
            item_name=item.name,
            category=item.category,
            context_key=owned.context_key,
            is_equipped=owned.is_equipped,
            acquired_at=owned.acquired_at,
        )

    async def list_inventory(self, user_id: int) -> list[InventoryItemResponse]:
        stmt = (
            select(UserShopItemModel, ShopItemModel)
            .join(ShopItemModel, UserShopItemModel.shop_item_id == ShopItemModel.id)
            .where(UserShopItemModel.user_id == user_id)
            .order_by(UserShopItemModel.acquired_at.desc(), UserShopItemModel.id.desc())
        )
        result = await self.db.execute(stmt)
        rows = [self._to_inventory_dto(owned, item) for owned, item in result.all()]
        logger.info(
            "[ShopPgRepository] list_inventory <- Neon user=%d count=%d",
            user_id,
            len(rows),
        )
        return rows

    async def _unequip_same_category(
        self, *, user_id: int, category: str, keep_inventory_id: int
    ) -> None:
        """같은 카테고리의 다른 장착을 내린다 — 순위표 자리가 하나뿐이기 때문이다.

        해제를 사용자에게 시키지 않고 장착 쪽에서 처리하는 이유는, 그러지 않으면
        둘 다 "장착 중"으로 보이는데 순위표에는 하나만 나오는 상태가 되기 때문이다.
        """
        stmt = (
            update(UserShopItemModel)
            .where(
                UserShopItemModel.user_id == user_id,
                UserShopItemModel.id != keep_inventory_id,
                UserShopItemModel.is_equipped.is_(True),
                UserShopItemModel.shop_item_id.in_(
                    select(ShopItemModel.id).where(ShopItemModel.category == category)
                ),
            )
            .values(is_equipped=False)
        )
        result = await self.db.execute(stmt)
        if result.rowcount:
            logger.info(
                "[ShopPgRepository] unequip_same_category -> Neon user=%d category=%s count=%d",
                user_id,
                category,
                result.rowcount,
            )

    async def set_equipped(
        self, *, user_id: int, inventory_id: int, is_equipped: bool
    ) -> InventoryItemResponse:
        # user_id를 조건에 함께 건다. id만으로 찾으면 남의 아이템을 장착·해제할 수 있다.
        stmt = (
            select(UserShopItemModel, ShopItemModel)
            .join(ShopItemModel, UserShopItemModel.shop_item_id == ShopItemModel.id)
            .where(
                UserShopItemModel.id == inventory_id,
                UserShopItemModel.user_id == user_id,
            )
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            raise LookupError(f"보유 아이템 {inventory_id}를 찾을 수 없습니다.")

        owned, item = row
        if is_equipped and item.category in COSMETIC_CATEGORIES:
            await self._unequip_same_category(
                user_id=user_id, category=item.category, keep_inventory_id=inventory_id
            )
        owned.is_equipped = is_equipped
        await self.db.flush()
        logger.info(
            "[ShopPgRepository] set_equipped -> Neon user=%d inventory=%d equipped=%s",
            user_id,
            inventory_id,
            is_equipped,
        )
        return self._to_inventory_dto(owned, item)
