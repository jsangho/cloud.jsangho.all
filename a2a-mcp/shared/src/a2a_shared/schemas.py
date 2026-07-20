from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentName(StrEnum):
    EXAONE = "exaone"
    QWEN = "qwen"
    AWS_ROUTER = "aws_router"


class A2AMessage(BaseModel):
    """에이전트 간 표준 메시지. 모든 A2A 호출은 이 스키마를 사용한다."""

    sender: AgentName
    receiver: AgentName
    task: str
    payload: dict = Field(default_factory=dict)
    trace_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class A2AResult(BaseModel):
    trace_id: str
    responder: AgentName
    success: bool
    output: dict = Field(default_factory=dict)
    error: str | None = None
