from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramQuery:
    id: int
    name: str


@dataclass
class TelegramResponse:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class TelegramSendCommand:
    chat_id: str
    message: str
