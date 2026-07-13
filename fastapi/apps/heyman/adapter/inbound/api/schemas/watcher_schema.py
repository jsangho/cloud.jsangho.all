from pydantic import BaseModel


class WatcherMyselfSchema(BaseModel):
    id: int = 1
    name: str = "Watson"


class WatcherFilterRequest(BaseModel):
    from_email: str
    from_name: str = ""
    to_email: str = ""
    subject: str = ""
    body: str = ""
    message_id: str = ""


class WatcherFilterResponse(BaseModel):
    id: int | None
    label: str
    confidence: float
    forwarded: bool
