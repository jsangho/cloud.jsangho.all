from pydantic import BaseModel, Field


class LangchainChatMessageSchema(BaseModel):
    role: str = Field(..., description="user 또는 assistant")
    text: str = Field(..., description="메시지 본문")


class LangchainChatRequestSchema(BaseModel):
    messages: list[LangchainChatMessageSchema] = Field(
        ..., description="대화 이력(마지막 항목이 user 메시지)"
    )


class LangchainChatResponseSchema(BaseModel):
    reply: str = Field(..., description="LangChain이 생성한 응답")
