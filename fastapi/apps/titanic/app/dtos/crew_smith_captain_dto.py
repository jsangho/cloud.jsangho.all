from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class SmithCaptainQuery:
    id: int
    name: str


@dataclass(frozen=True)
class SmithCaptainResponse:
    id: int
    name: str


@dataclass(frozen=True)
class SmithCaptainChatTurnDto:
    role: str
    text: str


@dataclass(frozen=True)
class SmithCaptainChatCommand:
    messages: tuple[SmithCaptainChatTurnDto, ...]
    stream: bool = False


@dataclass(frozen=True)
class ChatResponse(BaseModel):
    text: str
