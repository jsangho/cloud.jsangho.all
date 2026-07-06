from __future__ import annotations

import os

import httpx

from manager.app.dtos.email_dto import EmailDto
from manager.app.ports.output.email_gateway import EmailGateway


class N8nEmailGateway(EmailGateway):
    """n8n Webhook을 통해 Gmail로 이메일을 발송하는 아웃바운드 어댑터."""

    def __init__(self) -> None:
        self._webhook_url = os.environ["N8N_WEBHOOK_URL"]

    async def send(self, dto: EmailDto) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._webhook_url,
                json={"to": dto.to, "subject": dto.subject, "body": dto.body},
                timeout=30.0,
            )
            response.raise_for_status()
