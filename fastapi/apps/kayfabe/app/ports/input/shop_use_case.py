from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.shop_dto import (
    InventoryItemResponse,
    PurchaseCommand,
    PurchaseReceipt,
    ShopItemResponse,
    WalletResponse,
)


class ShopUseCase(ABC):
    """`/shop` inbound(shop_router) 입력 포트."""

    @abstractmethod
    async def list_items(self) -> list[ShopItemResponse]:
        """판매 중인 상품 카탈로그."""
        ...

    @abstractmethod
    async def get_wallet(self, user_id: int) -> WalletResponse:
        """획득액·지출·잔액."""
        ...

    @abstractmethod
    async def purchase(self, command: PurchaseCommand) -> PurchaseReceipt:
        """상품 구매."""
        ...

    @abstractmethod
    async def list_inventory(self, user_id: int) -> list[InventoryItemResponse]:
        """보유 아이템 목록."""
        ...

    @abstractmethod
    async def set_equipped(
        self, *, user_id: int, inventory_id: int, is_equipped: bool
    ) -> InventoryItemResponse:
        """보유 아이템 장착·해제."""
        ...
