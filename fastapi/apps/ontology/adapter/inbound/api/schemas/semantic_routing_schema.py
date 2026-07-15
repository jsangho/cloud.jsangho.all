from pydantic import BaseModel, Field


class SemanticRoutingSchema(BaseModel):
    question: str = Field(..., description="라우팅할 질문")

    model_config = {
        "json_schema_extra": {
            "example": {"question": "로만 레인즈 정보 좀 지워줘"},
        }
    }


class RoutingDecisionResponse(BaseModel):
    destination: str
    entities: list[str]
