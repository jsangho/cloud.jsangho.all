"""순위 집계 어댑터 테스트 — 적중률 정렬과 내 순위 조회.

SQLite 인메모리에서 실제 쿼리를 실행한다. ORM이 이식 가능한 타입만 쓰고
SQLite 3.25+ 가 윈도우 함수를 지원하므로 `rank() OVER` 동작을 그대로 검증할 수 있다.

실행 (반드시 `fastapi/` 안에서, importlib 임포트 모드로):

    cd fastapi
    PYTHONUTF8=1 PYTHONPATH=apps:. uv run pytest apps/kayfabe/tests --import-mode=importlib

저장소 루트에서 실행하거나 기본 임포트 모드를 쓰면 루트의 `fastapi/` 디렉터리가 실제
FastAPI 패키지를 가려 수집 단계에서 ImportError가 난다. 자세한 배경은 `tests/conftest.py`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

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
    ShopItemCategory,
    ShopItemModel,
    UserShopItemModel,
)
from kayfabe.adapter.outbound.pg.ple_match_pick_pg_repository import (
    PleMatchPickPgRepository,
)

_TABLES = [
    UserModel.__table__,
    PleEventModel.__table__,
    PleMatchModel.__table__,
    PlePredictionModel.__table__,
    # 순위 행에 장착 아이템을 붙이느라 상점 테이블도 읽는다.
    ShopItemModel.__table__,
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


def _match(mid: int, *, winner: str | None, point_value: int = 1) -> PleMatchModel:
    """winner=None 이면 미채점 경기(status=SCHEDULED)."""
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
        id=pid,
        match_id=match_id,
        client_id=f"c{pid}",
        user_id=user_id,
        pick=pick,
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


def _fixture_objects() -> list[object]:
    """A: 2전 2적중(100%, 2점) · B: 5전 4적중(80%, 4점) · C: 미채점만(집계 제외).

    점수만 보면 B(4점) > A(2점)이지만, 적중률로는 A(100%) > B(80%)다.
    이 데이터가 두 정렬 기준을 구분한다.
    """
    objects: list[object] = [_user(1, "alice"), _user(2, "bob"), _user(3, "carol")]

    # 채점 완료 경기 5개 — 정답은 모두 "sideA"
    objects += [_match(mid, winner="sideA") for mid in range(1, 6)]
    # 미채점 경기 1개
    objects.append(_match(6, winner=None))

    pid = 0
    # alice: 1·2번 경기 적중 (2전 2적중)
    for mid in (1, 2):
        pid += 1
        objects.append(_pick(pid, match_id=mid, user_id=1, pick="sideA"))
    # alice: 미채점 경기에도 예측 — graded 에 포함되면 안 된다
    pid += 1
    objects.append(_pick(pid, match_id=6, user_id=1, pick="sideB"))

    # bob: 1~4번 적중, 5번 오답 (5전 4적중)
    for mid in (1, 2, 3, 4):
        pid += 1
        objects.append(_pick(pid, match_id=mid, user_id=2, pick="sideA"))
    pid += 1
    objects.append(_pick(pid, match_id=5, user_id=2, pick="sideB"))

    # carol: 미채점 경기에만 예측 — HAVING graded > 0 으로 집계에서 빠진다
    pid += 1
    objects.append(_pick(pid, match_id=6, user_id=3, pick="sideA"))

    return objects


class TestListRanked:
    def test_higher_accuracy_outranks_higher_score(self):
        """적중률이 높으면 배점 합계가 낮아도 1위다 — 정렬 기준 변경의 핵심."""

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())

        # 점수 기준이었다면 bob(4점)이 1위였다.
        assert [r.nickname for r in rows] == ["alice", "bob"]
        assert rows[0].rank == 1
        assert rows[0].score == 2
        assert rows[0].correct == 2
        assert rows[0].graded == 2
        assert rows[1].rank == 2
        assert rows[1].score == 4

    def test_ungraded_picks_do_not_count_toward_graded(self):
        """미채점 경기 예측은 graded에 포함되지 않는다."""

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())
        alice = next(r for r in rows if r.nickname == "alice")
        # 미채점 경기 1건에도 예측했지만 graded 는 2로 유지된다.
        assert alice.graded == 2

    def test_user_without_graded_picks_is_excluded(self):
        """채점된 예측이 없는 사용자는 HAVING graded > 0 으로 순위에서 빠진다."""

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())
        assert "carol" not in [r.nickname for r in rows]

    def test_score_breaks_accuracy_ties(self):
        """적중률 동률이면 배점 합계가 높은 쪽이 앞선다.

        둘 다 1전 1적중(100%)이고 배점만 다르다 — 로열럼블 5점 vs 단일 1점.
        """

        async def run():
            objects: list[object] = [_user(1, "alice"), _user(2, "bob")]
            objects.append(_match(1, winner="sideA", point_value=1))
            objects.append(_match(2, winner="sideA", point_value=5))
            objects.append(_pick(1, match_id=1, user_id=1, pick="sideA"))
            objects.append(_pick(2, match_id=2, user_id=2, pick="sideA"))
            session = await _seed_session(objects)
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())
        assert [(r.nickname, r.score) for r in rows] == [("bob", 5), ("alice", 1)]


class TestGetRankedByNickname:
    def test_returns_true_rank_for_lower_ranked_user(self):
        """회귀 테스트 — 하위 순위 사용자에게 실제 순위를 반환한다.

        윈도우 함수가 같은 SELECT의 WHERE보다 나중에 평가되던 탓에, 닉네임 필터가
        순위 계산 범위를 한 행으로 좁혀 누구에게나 1위가 나왔다.
        """

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                repo = PleMatchPickPgRepository(session)
                return await repo.get_ranked_by_nickname("bob")
            finally:
                await session.close()

        row = asyncio.run(run())

        assert row is not None
        assert row.nickname == "bob"
        assert row.rank == 2, "닉네임 필터가 순위 계산 범위를 좁히면 1이 된다"
        assert row.score == 4
        assert row.correct == 4
        assert row.graded == 5

    def test_top_user_stays_rank_one(self):
        """1위 사용자는 그대로 1위로 조회된다."""

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                repo = PleMatchPickPgRepository(session)
                return await repo.get_ranked_by_nickname("alice")
            finally:
                await session.close()

        row = asyncio.run(run())
        assert row is not None
        assert row.rank == 1

    def test_returns_none_without_graded_picks(self):
        """채점된 예측이 없으면 None — 프론트가 이때 보유 포인트를 0으로 표시한다."""

        async def run():
            session = await _seed_session(_fixture_objects())
            try:
                repo = PleMatchPickPgRepository(session)
                return await repo.get_ranked_by_nickname("carol")
            finally:
                await session.close()

        assert asyncio.run(run()) is None


def _shop_item(iid: int, code: str, category: str) -> ShopItemModel:
    return ShopItemModel(
        id=iid,
        code=code,
        name=f"상품 {code}",
        description="",
        price=10,
        category=category,
        is_consumable=False,
        is_active=True,
    )


def _owned(
    oid: int, *, user_id: int, shop_item_id: int, equipped: bool
) -> UserShopItemModel:
    return UserShopItemModel(
        id=oid,
        user_id=user_id,
        shop_item_id=shop_item_id,
        context_key="",
        is_equipped=equipped,
    )


class TestEquippedCosmetics:
    """순위 행에 장착 아이템이 붙는다 (상점 7번)."""

    @staticmethod
    def _objects() -> list[object]:
        return [
            *_fixture_objects(),
            _shop_item(101, "title_master", ShopItemCategory.TITLE),
            _shop_item(102, "nickname_color_gold", ShopItemCategory.NICKNAME_COLOR),
            _shop_item(103, "badge_rookie", ShopItemCategory.BADGE),
            _shop_item(104, "report_match", ShopItemCategory.REPORT),
            # alice: 칭호·색상 장착, 뱃지는 보유만
            _owned(201, user_id=1, shop_item_id=101, equipped=True),
            _owned(202, user_id=1, shop_item_id=102, equipped=True),
            _owned(203, user_id=1, shop_item_id=103, equipped=False),
            # alice: 치장 카테고리가 아닌 소모품은 장착돼 있어도 노출되지 않는다
            _owned(204, user_id=1, shop_item_id=104, equipped=True),
        ]

    def test_equipped_items_are_attached(self):
        async def run():
            session = await _seed_session(self._objects())
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())
        alice = next(r for r in rows if r.nickname == "alice")
        assert alice.cosmetics.title is not None
        assert alice.cosmetics.title.code == "title_master"
        assert alice.cosmetics.nickname_color is not None
        assert alice.cosmetics.nickname_color.code == "nickname_color_gold"
        # 보유만 하고 장착하지 않은 뱃지는 붙지 않는다.
        assert alice.cosmetics.badge is None

    def test_user_without_items_gets_empty_cosmetics(self):
        """아이템이 없는 사용자도 None이 아니라 빈 값이 온다."""

        async def run():
            session = await _seed_session(self._objects())
            try:
                return await PleMatchPickPgRepository(session).list_ranked(10)
            finally:
                await session.close()

        rows = asyncio.run(run())
        bob = next(r for r in rows if r.nickname == "bob")
        assert bob.cosmetics.title is None
        assert bob.cosmetics.nickname_color is None
        assert bob.cosmetics.badge is None

    def test_my_rank_lookup_also_carries_cosmetics(self):
        async def run():
            session = await _seed_session(self._objects())
            try:
                repo = PleMatchPickPgRepository(session)
                return await repo.get_ranked_by_nickname("alice")
            finally:
                await session.close()

        row = asyncio.run(run())
        assert row is not None
        assert row.cosmetics.title is not None
        assert row.cosmetics.title.name == "상품 title_master"
