"""PLE 예측 순위 Postgres 어댑터."""

from __future__ import annotations

from core.matrix.grid_oracle_database_manager import LAYER_LOG
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.adapter.outbound.orm.shop_orm import (
    COSMETIC_CATEGORIES,
    ShopItemCategory,
    ShopItemModel,
    UserShopItemModel,
)
from kayfabe.adapter.outbound.pg.point_aggregation import earned_points_subquery
from kayfabe.app.dtos.ple_events_dto import MyselfQuery, MyselfResponse
from kayfabe.app.dtos.ple_match_pick_dto import (
    CosmeticItem,
    EquippedCosmetics,
    LeaderboardQuery,
)
from kayfabe.app.ports.output.ple_match_pick_repository import PleMatchPickRepository

logger = LAYER_LOG


class PleMatchPickPgRepository(PleMatchPickRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _aggregated_subquery():
        return earned_points_subquery()

    @staticmethod
    def _rank_order(agg):
        """순위 정렬 기준 — 적중률 내림차순.

        적중률은 인터랙터의 `correct / graded`와 같은 정의다. `_aggregated_subquery`가
        `HAVING graded > 0`으로 걸러 주므로 0으로 나눌 일은 없다.
        동률은 배점 합계 → 적중 수 → 닉네임 순으로 갈라 순서를 결정적으로 만든다.
        """
        accuracy_expr = cast(agg.c.correct, Float) / agg.c.graded
        return (
            accuracy_expr.desc(),
            agg.c.score.desc(),
            agg.c.correct.desc(),
            agg.c.nickname.asc(),
        )

    async def _load_cosmetics(
        self, user_ids: list[int]
    ) -> dict[int, EquippedCosmetics]:
        """순위에 오른 사용자들의 장착 아이템을 한 번에 읽는다 (N+1 방지).

        집계 쿼리에 조인하지 않는 이유는 사용자당 아이템이 여러 개라 행이 불어나
        점수 합계가 아이템 수만큼 부풀기 때문이다.

        장착은 카테고리당 하나로 제한되지만(`ShopPgRepository.set_equipped`), 그 규칙이
        생기기 전에 둘 이상 장착해 둔 행이 남아 있을 수 있다. 최근에 얻은 것이 이기도록
        정렬해 두고 카테고리별 첫 행만 취한다.
        """
        if not user_ids:
            return {}

        stmt = (
            select(
                UserShopItemModel.user_id,
                ShopItemModel.category,
                ShopItemModel.code,
                ShopItemModel.name,
            )
            .join(ShopItemModel, UserShopItemModel.shop_item_id == ShopItemModel.id)
            .where(
                UserShopItemModel.user_id.in_(user_ids),
                UserShopItemModel.is_equipped.is_(True),
                ShopItemModel.category.in_(COSMETIC_CATEGORIES),
            )
            .order_by(UserShopItemModel.acquired_at.desc(), UserShopItemModel.id.desc())
        )
        result = await self.db.execute(stmt)

        picked: dict[int, dict[str, CosmeticItem]] = {}
        for user_id, category, code, name in result.all():
            per_user = picked.setdefault(int(user_id), {})
            per_user.setdefault(str(category), CosmeticItem(code=code, name=name))

        return {
            user_id: EquippedCosmetics(
                title=items.get(ShopItemCategory.TITLE),
                nickname_color=items.get(ShopItemCategory.NICKNAME_COLOR),
                badge=items.get(ShopItemCategory.BADGE),
            )
            for user_id, items in picked.items()
        }

    async def list_ranked(self, limit: int) -> list[LeaderboardQuery]:
        agg = self._aggregated_subquery()
        rank_col = func.rank().over(order_by=self._rank_order(agg)).label("rank")

        stmt = (
            select(
                rank_col,
                agg.c.user_id,
                agg.c.nickname,
                agg.c.score,
                agg.c.correct,
                agg.c.graded,
            )
            .select_from(agg)
            .order_by(rank_col)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        raw = result.all()
        cosmetics = await self._load_cosmetics([int(r[1]) for r in raw])
        rows = [
            LeaderboardQuery(
                rank=int(rank),
                nickname=str(nickname),
                score=int(score or 0),
                correct=int(correct or 0),
                graded=int(graded or 0),
                cosmetics=cosmetics.get(int(user_id), EquippedCosmetics()),
            )
            for rank, user_id, nickname, score, correct, graded in raw
        ]
        logger.info(
            "[PleMatchPickPgRepository] list_ranked <- Neon count=%d", len(rows)
        )
        return rows

    async def get_ranked_by_nickname(self, nickname: str) -> LeaderboardQuery | None:
        agg = self._aggregated_subquery()
        # 윈도우 함수는 같은 SELECT의 WHERE보다 나중에 평가된다. 닉네임 필터를
        # rank()와 같은 SELECT에 두면 필터로 남은 한 행만 보고 순위를 매겨 항상
        # 1위가 나온다. 그래서 전체 집합에 순위를 매긴 서브쿼리를 만든 뒤 바깥에서 거른다.
        ranked = (
            select(
                func.rank().over(order_by=self._rank_order(agg)).label("rank"),
                agg.c.user_id,
                agg.c.nickname,
                agg.c.score,
                agg.c.correct,
                agg.c.graded,
            )
            .select_from(agg)
            .subquery()
        )

        stmt = select(
            ranked.c.rank,
            ranked.c.user_id,
            ranked.c.nickname,
            ranked.c.score,
            ranked.c.correct,
            ranked.c.graded,
        ).where(ranked.c.nickname == nickname)

        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            return None
        rank, user_id, nick, score, correct, graded = row
        cosmetics = await self._load_cosmetics([int(user_id)])
        return LeaderboardQuery(
            rank=int(rank),
            nickname=str(nick),
            score=int(score or 0),
            correct=int(correct or 0),
            graded=int(graded or 0),
            cosmetics=cosmetics.get(int(user_id), EquippedCosmetics()),
        )

    async def introduce_myself(self, query: MyselfQuery) -> MyselfResponse:
        return MyselfResponse(
            id=query.id * 10000,
            name=query.name + "이 레포지토리에 다녀옴",
        )
