from kayfabe.adapter.inbound.api.schemas.ple_match_pick_schema import (
    CosmeticItemSchema,
    RankingRowSchema,
    RankingsResponseSchema,
)
from kayfabe.app.dtos.ple_match_pick_dto import (
    CosmeticItem,
    RankingRowResponse,
    RankingsResponse,
)


def _cosmetic_to_schema(item: CosmeticItem | None) -> CosmeticItemSchema | None:
    if item is None:
        return None
    return CosmeticItemSchema(code=item.code, name=item.name)


def _row_to_schema(row: RankingRowResponse) -> RankingRowSchema:
    return RankingRowSchema(
        rank=row.rank,
        nickname=row.nickname,
        score=row.score,
        accuracy=row.accuracy,
        title=_cosmetic_to_schema(row.cosmetics.title),
        nickname_color=_cosmetic_to_schema(row.cosmetics.nickname_color),
        badge=_cosmetic_to_schema(row.cosmetics.badge),
    )


def rankings_to_schema(dto: RankingsResponse) -> RankingsResponseSchema:
    return RankingsResponseSchema(
        rows=[_row_to_schema(r) for r in dto.rows],
        my_rank=_row_to_schema(dto.my_rank) if dto.my_rank else None,
    )
