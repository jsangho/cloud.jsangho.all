from kayfabe.adapter.inbound.api.schemas.ple_match_pick_schema import (
    RankingRowSchema,
    RankingsResponseSchema,
)
from kayfabe.app.dtos.ple_match_pick_dto import RankingsResponse


def rankings_to_schema(dto: RankingsResponse) -> RankingsResponseSchema:
    return RankingsResponseSchema(
        rows=[
            RankingRowSchema(
                rank=r.rank,
                nickname=r.nickname,
                score=r.score,
                accuracy=r.accuracy,
            )
            for r in dto.rows
        ],
        my_rank=(
            RankingRowSchema(
                rank=dto.my_rank.rank,
                nickname=dto.my_rank.nickname,
                score=dto.my_rank.score,
                accuracy=dto.my_rank.accuracy,
            )
            if dto.my_rank
            else None
        ),
    )
