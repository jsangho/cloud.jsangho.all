from dataclasses import dataclass


@dataclass
class EmailDto:
    to: str
    subject: str
    body: str
