from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReceiverRequest(BaseModel):
    from_email: str
    from_name: str = ""
    to_email: str = ""
    subject: str = ""
    body: str = ""
    message_id: str = ""


class ReceiverResponse(BaseModel):
    id: int
    from_email: str
    from_name: str
    to_email: str
    subject: str
    body: str
    message_id: str
    receiver_at: datetime
    is_read: bool
    spam_label: str
    spam_confidence: float
