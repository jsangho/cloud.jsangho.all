from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GeneratePredictionsRequest(BaseModel):
    """생성 요청. 비용이 드는 경로라 관리자만 호출한다."""

    model_config = ConfigDict(populate_by_name=True)

    #: 비우면 아직 예측이 없는 경기 전부.
    match_keys: list[str] = Field(default_factory=list, alias="matchKeys")
    #: 이미 있는 예측도 다시 만든다.
    force: bool = False


class AgentReportSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent: str
    #: 의견 없음은 null이다.
    pick: str | None = None
    weight: float
    summary: str
    sources: list[str] = Field(default_factory=list)


class AgentPredictionSchema(BaseModel):
    """예측 한 건. `source`로 북메이커 폴백 여부가 드러난다."""

    model_config = ConfigDict(populate_by_name=True)

    match_key: str = Field(alias="matchKey")
    pick: str
    pick_name: str = Field(alias="pickName")
    #: 0.0~1.0. %로 바꾸는 것은 화면의 몫이다.
    win_probability: float = Field(alias="winProbability")
    confidence: float
    rationale: str
    source: str
    generated_at: datetime = Field(alias="generatedAt")
    reports: list[AgentReportSchema] = Field(default_factory=list)


class AgentPredictionListSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AgentPredictionSchema]


class GenerationSummarySchema(BaseModel):
    """개별 경기의 실패가 전체를 실패시키지 않으므로 건수로 돌려준다."""

    model_config = ConfigDict(populate_by_name=True)

    requested: int
    generated: int
    skipped: int
    failed: int
