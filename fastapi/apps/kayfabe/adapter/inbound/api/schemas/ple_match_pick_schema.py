from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kayfabe.adapter.inbound.api.schemas.ple_events_schema import (
    PleBoardSchema,  # noqa: F401
)

__all__ = [
    "PleBoardSchema",
    "PredictionItemSchema",
    "PredictionRequestSchema",
    "LinkPredictionsSchema",
    "BatchPredictionRequestSchema",
    "RankingRowSchema",
    "RankingsResponseSchema",
]


class PredictionItemSchema(BaseModel):
    match_key: str = Field(..., alias="matchKey")
    pick: str = Field(..., min_length=1, max_length=20)

    model_config = ConfigDict(populate_by_name=True)


class PredictionRequestSchema(BaseModel):
    pick: str = Field(..., description="left | right | multi index as string")
    client_id: str = Field(..., alias="clientId", min_length=8, max_length=64)
    user_id: int = Field(..., alias="userId", ge=1, description="로그인 회원 id (필수)")

    model_config = ConfigDict(populate_by_name=True)


class LinkPredictionsSchema(BaseModel):
    client_id: str = Field(..., alias="clientId", min_length=8, max_length=64)
    user_id: int = Field(..., alias="userId", ge=1)

    model_config = ConfigDict(populate_by_name=True)


class BatchPredictionRequestSchema(BaseModel):
    client_id: str = Field(..., alias="clientId", min_length=8, max_length=64)
    user_id: int = Field(..., alias="userId", ge=1)
    predictions: list[PredictionItemSchema] = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class RankingRowSchema(BaseModel):
    rank: int
    nickname: str
    score: int
    accuracy: float = Field(..., ge=0.0, le=1.0, description="적중률 0~1")

    model_config = ConfigDict(populate_by_name=True)


class RankingsResponseSchema(BaseModel):
    rows: list[RankingRowSchema]
    my_rank: RankingRowSchema | None = Field(default=None, alias="myRank")

    model_config = ConfigDict(populate_by_name=True)
