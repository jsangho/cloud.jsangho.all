from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReceiverCommand:
    from_email: str
    from_name: str = ""
    to_email: str = ""
    subject: str = ""
    body: str = ""
    message_id: str = ""


@dataclass
class ReceiverItem:
    id: int
    from_email: str
    from_name: str
    to_email: str
    subject: str
    body: str
    message_id: str
    receiver_at: datetime
    is_read: bool
    spam_label: str = "ham"
    spam_confidence: float = 1.0
