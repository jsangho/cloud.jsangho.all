from __future__ import annotations

from abc import ABC, abstractmethod

from kayfabe.app.dtos.shop_dto import (
    InventoryItemResponse,
    PurchaseCommand,
    PurchaseReceipt,
    ShopItemResponse,
    WalletResponse,
)


class ShopRepository(ABC):
    """상점 출력 포트 — 카탈로그·잔액·구매·보유."""

    @abstractmethod
    async def list_active_items(self) -> list[ShopItemResponse]:
        """판매 중인 상품 목록."""
        ...

    @abstractmethod
    async def get_wallet(self, user_id: int) -> WalletResponse:
        """획득액·지출·잔액. 잔액은 저장값이 아니라 매번 계산한다."""
        ...

    @abstractmethod
    async def purchase(self, command: PurchaseCommand) -> PurchaseReceipt:
        """구매를 한 트랜잭션으로 처리한다 (사용자 행 잠금 포함).

        실패는 사유별 예외로 구분한다 — `ShopItemNotFoundError` ·
        `ShopItemUnavailableError` · `AlreadyOwnedError` · `InsufficientPointsError`.
        """
        ...

    @abstractmethod
    async def list_inventory(self, user_id: int) -> list[InventoryItemResponse]:
        """보유 아이템과 장착 상태."""
        ...

    @abstractmethod
    async def set_equipped(
        self, *, user_id: int, inventory_id: int, is_equipped: bool
    ) -> InventoryItemResponse:
        """장착·해제. 남의 보유 행은 건드릴 수 없다 (`user_id`로 함께 건다).

        대상이 없거나 남의 것이면 `LookupError`.
        """
        ...
