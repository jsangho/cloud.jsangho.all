from pydantic import BaseModel


class DiscordMyselfSchema(BaseModel):
    id: int = 1
    name: str = "Discord Manager"
