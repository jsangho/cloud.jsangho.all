"""상점 API.

**사용자 식별은 토큰에서만 얻는다.** 요청 본문·쿼리의 `userId`를 신뢰하면
남의 포인트를 쓸 수 있다 (`fastapi/_docs/shop-point-ledger.md` §7).
"""

from __future__ import annotations

import logging

from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload

from fastapi import APIRouter, Depends, HTTPException
from kayfabe.adapter.inbound.api.schemas.shop_schema import (
    EquipRequestSchema,
    InventoryItemSchema,
    PurchaseReceiptSchema,
    PurchaseRequestSchema,
    ShopItemSchema,
    WalletSchema,
)
from kayfabe.adapter.outbound.mappers.shop_schema_mapper import (
    inventory_item_to_schema,
    purchase_receipt_to_schema,
    shop_item_to_schema,
    wallet_to_schema,
)
from kayfabe.app.dtos.shop_dto import PurchaseCommand
from kayfabe.app.exceptions import (
    AlreadyOwnedError,
    InsufficientPointsError,
    ShopItemNotFoundError,
    ShopItemUnavailableError,
)
from kayfabe.app.ports.input.shop_use_case import ShopUseCase
from kayfabe.dependencies.shop_provider import get_shop_use_case

logger = logging.getLogger("uvicorn.error")

shop_router = APIRouter(prefix="/shop", tags=["shop"])


def _user_id(claims: TokenPayload) -> int:
    """토큰 `sub`에서 회원 id를 얻는다."""
    try:
        return int(claims.sub)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=401, detail="토큰의 회원 정보가 올바르지 않습니다."
        ) from e


def _shop_http_error(exc: Exception) -> HTTPException:
    """구매 실패 사유를 프론트가 구분할 수 있게 상태 코드를 갈라 준다."""
    if isinstance(exc, InsufficientPointsError):
        return HTTPException(status_code=402, detail=str(exc))
    if isinstance(exc, AlreadyOwnedError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ShopItemUnavailableError):
        return HTTPException(status_code=410, detail=str(exc))
    if isinstance(exc, ShopItemNotFoundError | LookupError):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc) or "잘못된 요청입니다.")
    raise exc


@shop_router.get(
    "/items",
    response_model=list[ShopItemSchema],
    response_model_by_alias=True,
)
async def list_shop_items(use_case: ShopUseCase = Depends(get_shop_use_case)):
    """카탈로그는 로그인 없이도 볼 수 있다."""
    logger.info("[ShopRouter] list_shop_items")
    return [shop_item_to_schema(i) for i in await use_case.list_items()]


@shop_router.get(
    "/wallet",
    response_model=WalletSchema,
    response_model_by_alias=True,
)
async def get_shop_wallet(
    claims: TokenPayload = Depends(get_current_user),
    use_case: ShopUseCase = Depends(get_shop_use_case),
):
    user_id = _user_id(claims)
    logger.info("[ShopRouter] get_shop_wallet | user=%d", user_id)
    return wallet_to_schema(await use_case.get_wallet(user_id))


@shop_router.post(
    "/purchases",
    response_model=PurchaseReceiptSchema,
    response_model_by_alias=True,
    status_code=201,
)
async def purchase_shop_item(
    body: PurchaseRequestSchema,
    claims: TokenPayload = Depends(get_current_user),
    use_case: ShopUseCase = Depends(get_shop_use_case),
):
    user_id = _user_id(claims)
    logger.info(
        "[ShopRouter] purchase_shop_item | user=%d item=%s", user_id, body.item_code
    )
    try:
        receipt = await use_case.purchase(
            PurchaseCommand(
                user_id=user_id,
                item_code=body.item_code,
                context_key=body.context_key,
            )
        )
        return purchase_receipt_to_schema(receipt)
    except (
        InsufficientPointsError,
        AlreadyOwnedError,
        ShopItemUnavailableError,
        ShopItemNotFoundError,
        LookupError,
        ValueError,
    ) as e:
        raise _shop_http_error(e) from e


@shop_router.get(
    "/inventory",
    response_model=list[InventoryItemSchema],
    response_model_by_alias=True,
)
async def list_shop_inventory(
    claims: TokenPayload = Depends(get_current_user),
    use_case: ShopUseCase = Depends(get_shop_use_case),
):
    user_id = _user_id(claims)
    logger.info("[ShopRouter] list_shop_inventory | user=%d", user_id)
    return [inventory_item_to_schema(i) for i in await use_case.list_inventory(user_id)]


@shop_router.patch(
    "/inventory/{inventory_id}",
    response_model=InventoryItemSchema,
    response_model_by_alias=True,
)
async def set_shop_item_equipped(
    inventory_id: int,
    body: EquipRequestSchema,
    claims: TokenPayload = Depends(get_current_user),
    use_case: ShopUseCase = Depends(get_shop_use_case),
):
    user_id = _user_id(claims)
    logger.info(
        "[ShopRouter] set_shop_item_equipped | user=%d inventory=%d equipped=%s",
        user_id,
        inventory_id,
        body.is_equipped,
    )
    try:
        updated = await use_case.set_equipped(
            user_id=user_id,
            inventory_id=inventory_id,
            is_equipped=body.is_equipped,
        )
        return inventory_item_to_schema(updated)
    except LookupError as e:
        raise _shop_http_error(e) from e
