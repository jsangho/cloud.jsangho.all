from pydantic import BaseModel


class TelegramMyselfSchema(BaseModel):
    id: int = 3
    name: str = "Telegram Manager"


class TelegramSendRequest(BaseModel):
    chat_id: str
    message: str
