from dataclasses import dataclass


@dataclass(frozen=True)
class LangchainChatMessage:
    role: str
    text: str


@dataclass(frozen=True)
class LangchainChatCommand:
    messages: tuple[LangchainChatMessage, ...]


@dataclass(frozen=True)
class LangchainChatResult:
    reply: str
