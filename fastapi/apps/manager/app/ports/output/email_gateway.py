from __future__ import annotations

from abc import ABC, abstractmethod

from manager.app.dtos.email_dto import EmailDto


class EmailGateway(ABC):
    """n8n 등 외부 알림 서비스를 향한 아웃바운드 포트."""

    @abstractmethod
    async def send(self, dto: EmailDto) -> None: ...
