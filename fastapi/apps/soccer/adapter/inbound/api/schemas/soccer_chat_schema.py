from typing import Literal

from pydantic import BaseModel, Field


class SoccerChatMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class SoccerChatSchema(BaseModel):
    messages: list[SoccerChatMessageSchema] = Field(
        ..., description="채팅 메시지 히스토리"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [{"role": "user", "text": "가장 최근에 데뷔한 선수는?"}],
            }
        }
    }
