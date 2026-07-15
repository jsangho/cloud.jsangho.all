from pydantic import BaseModel, Field


class GeminiAskSchema(BaseModel):
    question: str = Field(..., description="Gemini에게 보낼 질문")

    model_config = {
        "json_schema_extra": {
            "example": {"question": "3 곱하기 7은 얼마야?"},
        }
    }
