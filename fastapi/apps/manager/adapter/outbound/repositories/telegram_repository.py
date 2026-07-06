from __future__ import annotations

import json as _json
import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from manager.app.dtos.telegram_dto import (
    TelegramQuery,
    TelegramResponse,
    TelegramSendCommand,
)
from manager.app.ports.output.telegram_repository import TelegramRepository


class TelegramPgRepository(TelegramRepository):
    """Neon(Postgres) Telegram 메시지 로그 어댑터."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def introduce_myself(self, query: TelegramQuery) -> TelegramResponse:
        return TelegramResponse(
            id=query.id,
            name=query.name,
            description="Telegram 채널에 알림·보고서를 전송하는 봇 서비스입니다.",
        )

    async def send_message(self, cmd: TelegramSendCommand) -> dict[str, str]:
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=_json.dumps(
                    {"chat_id": cmd.chat_id, "text": cmd.message, "parse_mode": "HTML"},
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=15.0,
            )
            response.raise_for_status()
        return {"status": "sent", "chat_id": cmd.chat_id}
