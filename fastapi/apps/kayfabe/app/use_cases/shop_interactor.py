"""상점 유스케이스.

구매의 원자성(사용자 행 잠금 → 잔액 확인 → 원장·보유 삽입)은 트랜잭션 경계를 쥔
`ShopPgRepository`가 책임진다. 여기서는 흐름만 잇고 실패 사유는 예외 그대로 흘린다 —
HTTP 상태 코드로의 변환은 라우터가 한다.
"""

from __future__ import annotations

import logging

from kayfabe.app.dtos.shop_dto import (
    InventoryItemResponse,
    PurchaseCommand,
    PurchaseReceipt,
    ShopItemResponse,
    WalletResponse,
)
from kayfabe.app.ports.input.shop_use_case import ShopUseCase
from kayfabe.app.ports.output.shop_repository import ShopRepository

logger = logging.getLogger("uvicorn.error")


class ShopInteractor(ShopUseCase):
    def __init__(self, *, repository: ShopRepository) -> None:
        self._repository = repository

    async def list_items(self) -> list[ShopItemResponse]:
        logger.info("[ShopInteractor] list_items")
        return await self._repository.list_active_items()

    async def get_wallet(self, user_id: int) -> WalletResponse:
        logger.info("[ShopInteractor] get_wallet | user=%d", user_id)
        return await self._repository.get_wallet(user_id)

    async def purchase(self, command: PurchaseCommand) -> PurchaseReceipt:
        logger.info(
            "[ShopInteractor] purchase | user=%d item=%s",
            command.user_id,
            command.item_code,
        )
        return await self._repository.purchase(command)

    async def list_inventory(self, user_id: int) -> list[InventoryItemResponse]:
        logger.info("[ShopInteractor] list_inventory | user=%d", user_id)
        return await self._repository.list_inventory(user_id)

    async def set_equipped(
        self, *, user_id: int, inventory_id: int, is_equipped: bool
    ) -> InventoryItemResponse:
        logger.info(
            "[ShopInteractor] set_equipped | user=%d inventory=%d equipped=%s",
            user_id,
            inventory_id,
            is_equipped,
        )
        return await self._repository.set_equipped(
            user_id=user_id, inventory_id=inventory_id, is_equipped=is_equipped
        )
