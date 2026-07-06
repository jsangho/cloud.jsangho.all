from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatSchema(BaseModel):
    messages: list[ChatMessageSchema] = Field(..., description="채팅 메시지 히스토리")

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [{"role": "user", "text": "탑승객은 몇 명이야?"}],
            }
        }
    }


class SmithCaptainChatResponseSchema(BaseModel):
    reply: str


class SmithCaptainSchema(BaseModel):
    id: int = Field(0, description="Captain ID")
    name: str = Field("에드워드 스미스", description="Captain's name")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 5,
                "name": "Edward Smith",
            }
        }
    }
