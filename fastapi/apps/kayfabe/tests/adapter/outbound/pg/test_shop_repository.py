"""상점 어댑터 테스트 — 잔액 계산 · 구매 · 보유 조회.

SQLite 인메모리에서 실제 쿼리를 실행한다. `with_for_update()`는 SQLite 방언이
빈 문자열로 컴파일해 무시하므로 잠금 자체는 여기서 검증되지 않는다 —
검증 대상은 잔액 산술, 실패 사유 구분, 유니크 제약에 의한 중복 보유 차단이다.

실행 (반드시 `fastapi/` 안에서, importlib 임포트 모드로):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run pytest apps/kayfabe/tests --import-mode=importlib

배경은 `tests/conftest.py` 및 `fastapi/_docs/shop-point-ledger.md`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest
from core.entities.user_model import UserModel
from core.matrix.grid_oracle_database_manager import Base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from kayfabe.adapter.outbound.orm.ple_orm import (
    PleEventModel,
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.adapter.outbound.orm.shop_orm import (
    PointLedgerEntryModel,
    PointLedgerEntryType,
    ShopItemCategory,
    ShopItemModel,
    UserShopItemModel,
)
from kayfabe.adapter.outbound.pg.shop_pg_repository import ShopPgRepository
from kayfabe.app.dtos.shop_dto import PurchaseCommand
from kayfabe.app.exceptions import (
    AlreadyOwnedError,
    InsufficientPointsError,
    ShopItemNotFoundError,
    ShopItemUnavailableError,
)

_TABLES = [
    UserModel.__table__,
    PleEventModel.__table__,
    PleMatchModel.__table__,
    PlePredictionModel.__table__,
    ShopItemModel.__table__,
    PointLedgerEntryModel.__table__,
    UserShopItemModel.__table__,
]


def _user(uid: int, nickname: str) -> UserModel:
    return UserModel(
        id=uid,
        login_id=f"login{uid}",
        nickname=nickname,
        email=f"user{uid}@example.com",
        password_hash="x",
        role="user",
    )


def _match(mid: int, *, winner: str | None, point_value: int) -> PleMatchModel:
    finished = winner is not None
    return PleMatchModel(
        id=mid,
        event_id=1,
        match_key=f"m{mid}",
        title=f"Match {mid}",
        format="singles",
        card_json="{}",
        status=PleMatchStatus.FINISHED if finished else PleMatchStatus.SCHEDULED,
        winner_pick=winner,
        point_value=point_value,
    )


def _pick(pid: int, *, match_id: int, user_id: int, pick: str) -> PlePredictionModel:
    return PlePredictionModel(
        id=pid, match_id=match_id, client_id=f"c{pid}", user_id=user_id, pick=pick
    )


def _item(
    iid: int,
    code: str,
    *,
    price: int,
    category: ShopItemCategory = ShopItemCategory.BADGE,
    is_consumable: bool = False,
    is_active: bool = True,
) -> ShopItemModel:
    return ShopItemModel(
        id=iid,
        code=code,
        name=f"상품 {code}",
        description="",
        price=price,
        category=category,
        is_consumable=is_consumable,
        is_active=is_active,
    )


async def _seed_session(objects: Sequence[object]) -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=_TABLES))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    session.add(PleEventModel(id=1, slug="ev", label="Event", year=2026))
    session.add_all(list(objects))
    await session.commit()
    return session


def _base_objects() -> list[object]:
    """alice는 30점짜리 경기 2건을 적중 → 획득 60점. 상품은 뱃지(50)·칭호(100)."""
    return [
        _user(1, "alice"),
        _match(1, winner="sideA", point_value=30),
        _match(2, winner="sideA", point_value=30),
        _match(3, winner="sideA", point_value=30),
        _pick(1, match_id=1, user_id=1, pick="sideA"),
        _pick(2, match_id=2, user_id=1, pick="sideA"),
        _pick(3, match_id=3, user_id=1, pick="sideB"),  # 오답 — 획득 없음
        _item(10, "badge_basic", price=50),
        _item(11, "title_master", price=100, category=ShopItemCategory.TITLE),
        _item(
            12,
            "report_match",
            price=20,
            category=ShopItemCategory.REPORT,
            is_consumable=True,
        ),
        _item(13, "badge_retired", price=10, is_active=False),
        # 중복 보유 검증용 — 두 번 사도 잔액이 남아야 유니크 제약까지 도달한다.
        _item(14, "badge_cheap", price=10),
    ]


def _run(coro_factory, objects: Sequence[object] | None = None):
    """세션을 열고 넘겨받은 코루틴 팩토리를 실행한 뒤 정리한다."""

    async def run():
        session = await _seed_session(
            list(objects) if objects is not None else _base_objects()
        )
        try:
            return await coro_factory(ShopPgRepository(session), session)
        finally:
            await session.close()

    return asyncio.run(run())


class TestGetWallet:
    def test_balance_is_earned_when_ledger_is_empty(self):
        """지출이 없으면 잔액 = 획득액. 오답 예측은 획득에 들어가지 않는다."""
        wallet = _run(lambda repo, _s: repo.get_wallet(1))
        assert wallet.earned == 60
        assert wallet.spent == 0
        assert wallet.balance == 60

    def test_ledger_entries_reduce_balance(self):
        """원장의 음수 항목이 잔액을 깎는다."""

        async def scenario(repo, session):
            session.add(
                PointLedgerEntryModel(
                    user_id=1,
                    amount=-50,
                    entry_type=PointLedgerEntryType.PURCHASE,
                    shop_item_id=10,
                    memo="",
                )
            )
            await session.flush()
            return await repo.get_wallet(1)

        wallet = _run(scenario)
        assert wallet.earned == 60
        assert wallet.spent == 50
        assert wallet.balance == 10

    def test_refund_offsets_spending(self):
        """환급은 양수 항목으로 들어가 지출을 상쇄한다 (원장은 추가 전용)."""

        async def scenario(repo, session):
            session.add_all(
                [
                    PointLedgerEntryModel(
                        user_id=1,
                        amount=-50,
                        entry_type=PointLedgerEntryType.PURCHASE,
                        shop_item_id=10,
                        memo="",
                    ),
                    PointLedgerEntryModel(
                        user_id=1,
                        amount=50,
                        entry_type=PointLedgerEntryType.REFUND,
                        shop_item_id=10,
                        memo="구매 취소",
                    ),
                ]
            )
            await session.flush()
            return await repo.get_wallet(1)

        wallet = _run(scenario)
        assert wallet.spent == 0
        assert wallet.balance == 60

    def test_user_without_picks_has_zero_balance(self):
        """예측이 없는 사용자도 0으로 조회된다 (행 없음이 아니라 0)."""
        objects = [*_base_objects(), _user(2, "bob")]
        wallet = _run(lambda repo, _s: repo.get_wallet(2), objects)
        assert (wallet.earned, wallet.spent, wallet.balance) == (0, 0, 0)


class TestPurchase:
    def test_purchase_writes_ledger_and_inventory(self):
        """구매 한 건이 원장 1행 + 보유 1행을 만든다."""

        async def scenario(repo, session):
            receipt = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_basic")
            )
            wallet = await repo.get_wallet(1)
            inventory = await repo.list_inventory(1)
            return receipt, wallet, inventory

        receipt, wallet, inventory = _run(scenario)

        assert receipt.item_code == "badge_basic"
        assert receipt.price == 50
        assert receipt.balance_after == 10
        assert wallet.balance == 10
        assert wallet.spent == 50
        assert [i.item_code for i in inventory] == ["badge_basic"]
        assert inventory[0].context_key == ""
        assert inventory[0].is_equipped is False

    def test_insufficient_points_is_rejected(self):
        """잔액(60)보다 비싼 상품(100)은 거절된다."""

        async def scenario(repo, _s):
            with pytest.raises(InsufficientPointsError) as exc:
                await repo.purchase(
                    PurchaseCommand(user_id=1, item_code="title_master")
                )
            return exc.value

        error = _run(scenario)
        assert error.price == 100
        assert error.balance == 60

    def test_insufficient_points_leaves_no_ledger_row(self):
        """실패한 구매는 원장에 흔적을 남기지 않는다."""

        async def scenario(repo, _s):
            with pytest.raises(InsufficientPointsError):
                await repo.purchase(
                    PurchaseCommand(user_id=1, item_code="title_master")
                )
            return await repo.get_wallet(1)

        wallet = _run(scenario)
        assert wallet.balance == 60
        assert wallet.spent == 0

    def test_duplicate_purchase_is_rejected(self):
        """같은 영구 아이템을 두 번 사면 유니크 제약이 막는다.

        잔액이 넉넉한 상품을 쓴다 — 잔액 검사가 먼저 걸리면 중복 여부를 못 본다.
        """

        async def scenario(repo, _s):
            await repo.purchase(PurchaseCommand(user_id=1, item_code="badge_cheap"))
            with pytest.raises(AlreadyOwnedError):
                await repo.purchase(PurchaseCommand(user_id=1, item_code="badge_cheap"))

        _run(scenario)

    def test_consumable_can_be_bought_for_different_contexts(self):
        """소모성 아이템은 사용 대상이 다르면 다시 살 수 있다."""

        async def scenario(repo, _s):
            await repo.purchase(
                PurchaseCommand(
                    user_id=1, item_code="report_match", context_key="match:1"
                )
            )
            await repo.purchase(
                PurchaseCommand(
                    user_id=1, item_code="report_match", context_key="match:2"
                )
            )
            return await repo.list_inventory(1)

        inventory = _run(scenario)
        assert sorted(i.context_key for i in inventory) == ["match:1", "match:2"]

    def test_consumable_same_context_is_rejected(self):
        """같은 대상으로 두 번 결제하는 것은 막힌다."""

        async def scenario(repo, _s):
            await repo.purchase(
                PurchaseCommand(
                    user_id=1, item_code="report_match", context_key="match:1"
                )
            )
            with pytest.raises(AlreadyOwnedError):
                await repo.purchase(
                    PurchaseCommand(
                        user_id=1, item_code="report_match", context_key="match:1"
                    )
                )

        _run(scenario)

    def test_consumable_requires_context_key(self):
        """소모성인데 사용 대상이 없으면 도메인 규칙이 거절한다."""

        async def scenario(repo, _s):
            with pytest.raises(ValueError):
                await repo.purchase(
                    PurchaseCommand(user_id=1, item_code="report_match")
                )

        _run(scenario)

    def test_inactive_item_is_rejected(self):
        """판매 중단 상품은 사유가 구분되는 예외로 거절된다."""

        async def scenario(repo, _s):
            with pytest.raises(ShopItemUnavailableError):
                await repo.purchase(
                    PurchaseCommand(user_id=1, item_code="badge_retired")
                )

        _run(scenario)

    def test_unknown_item_is_rejected(self):
        async def scenario(repo, _s):
            with pytest.raises(ShopItemNotFoundError):
                await repo.purchase(PurchaseCommand(user_id=1, item_code="nope"))

        _run(scenario)

    def test_unknown_user_is_rejected(self):
        async def scenario(repo, _s):
            with pytest.raises(LookupError):
                await repo.purchase(
                    PurchaseCommand(user_id=999, item_code="badge_basic")
                )

        _run(scenario)


class TestSetEquipped:
    def test_equip_and_unequip(self):
        """장착 상태는 토글된다."""

        async def scenario(repo, _s):
            receipt = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_basic")
            )
            equipped = await repo.set_equipped(
                user_id=1, inventory_id=receipt.inventory_id, is_equipped=True
            )
            unequipped = await repo.set_equipped(
                user_id=1, inventory_id=receipt.inventory_id, is_equipped=False
            )
            return equipped, unequipped

        equipped, unequipped = _run(scenario)
        assert equipped.is_equipped is True
        assert equipped.item_code == "badge_basic"
        assert unequipped.is_equipped is False

    def test_equipping_replaces_the_same_category(self):
        """순위표의 카테고리 자리는 하나뿐이다 — 새로 장착하면 이전 것이 내려온다."""

        async def scenario(repo, _s):
            cheap = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_cheap")
            )
            basic = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_basic")
            )
            await repo.set_equipped(
                user_id=1, inventory_id=cheap.inventory_id, is_equipped=True
            )
            await repo.set_equipped(
                user_id=1, inventory_id=basic.inventory_id, is_equipped=True
            )
            return await repo.list_inventory(1)

        inventory = _run(scenario)
        assert {i.item_code for i in inventory if i.is_equipped} == {"badge_basic"}

    def test_equipping_leaves_other_categories_alone(self):
        """뱃지를 바꿔도 칭호는 그대로다 — 자리가 서로 다르기 때문이다."""
        objects = [
            *_base_objects(),
            _item(15, "title_cheap", price=10, category=ShopItemCategory.TITLE),
        ]

        async def scenario(repo, _s):
            badge = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_cheap")
            )
            title = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="title_cheap")
            )
            await repo.set_equipped(
                user_id=1, inventory_id=badge.inventory_id, is_equipped=True
            )
            await repo.set_equipped(
                user_id=1, inventory_id=title.inventory_id, is_equipped=True
            )
            return await repo.list_inventory(1)

        inventory = _run(scenario, objects)
        assert {i.item_code for i in inventory if i.is_equipped} == {
            "badge_cheap",
            "title_cheap",
        }

    def test_consumable_category_is_not_exclusive(self):
        """리포트는 순위표에 자리가 없다 — 경기별로 여러 건이 동시에 유효하다."""

        async def scenario(repo, _s):
            first = await repo.purchase(
                PurchaseCommand(
                    user_id=1, item_code="report_match", context_key="match:1"
                )
            )
            second = await repo.purchase(
                PurchaseCommand(
                    user_id=1, item_code="report_match", context_key="match:2"
                )
            )
            await repo.set_equipped(
                user_id=1, inventory_id=first.inventory_id, is_equipped=True
            )
            await repo.set_equipped(
                user_id=1, inventory_id=second.inventory_id, is_equipped=True
            )
            return await repo.list_inventory(1)

        inventory = _run(scenario)
        assert len([i for i in inventory if i.is_equipped]) == 2

    def test_cannot_equip_another_users_item(self):
        """남의 보유 행은 id를 알아도 건드릴 수 없다."""

        async def scenario(repo, _s):
            receipt = await repo.purchase(
                PurchaseCommand(user_id=1, item_code="badge_basic")
            )
            with pytest.raises(LookupError):
                await repo.set_equipped(
                    user_id=2, inventory_id=receipt.inventory_id, is_equipped=True
                )
            # alice의 아이템은 그대로여야 한다.
            return await repo.list_inventory(1)

        inventory = _run(scenario, [*_base_objects(), _user(2, "bob")])
        assert inventory[0].is_equipped is False

    def test_unknown_inventory_id_is_rejected(self):
        async def scenario(repo, _s):
            with pytest.raises(LookupError):
                await repo.set_equipped(user_id=1, inventory_id=9999, is_equipped=True)

        _run(scenario)


class TestListActiveItems:
    def test_inactive_items_are_hidden(self):
        """판매 중단 상품은 카탈로그에서 빠진다 — 삭제하지 않고 감춘다."""
        items = _run(lambda repo, _s: repo.list_active_items())
        codes = [i.code for i in items]
        assert "badge_retired" not in codes
        assert sorted(codes) == [
            "badge_basic",
            "badge_cheap",
            "report_match",
            "title_master",
        ]
