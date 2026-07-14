from typing import Literal

from pydantic import BaseModel, Field


class WrestlerChatMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class WrestlerChatSchema(BaseModel):
    messages: list[WrestlerChatMessageSchema] = Field(
        ..., description="채팅 메시지 히스토리"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [{"role": "user", "text": "로만 레인즈 피니셔가 뭐야?"}],
            }
        }
    }
