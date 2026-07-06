from __future__ import annotations

import json as _json
import os

import httpx

from manager.app.dtos.receiver_dto import ReceiverCommand, ReceiverItem
from manager.app.ports.input.receiver_use_case import ReceiverUseCase
from manager.app.ports.input.watcher_use_case import WatcherUseCase
from manager.app.ports.output.receiver_repository import ReceiverRepository

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


async def _telegram_notify(subject: str, from_email: str) -> None:
    if not _BOT_TOKEN or not _CHAT_ID:
        return
    msg = f"📬 새 메일 도착\n발신자: {from_email}\n제목: {subject}"
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            content=_json.dumps(
                {"chat_id": _CHAT_ID, "text": msg}, ensure_ascii=False
            ).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10.0,
        )


class ReceiverInteractor(ReceiverUseCase):
    """Holmes 역할. 분류·1차 판단은 Watson(WatcherUseCase)에 위임하고,
    본인은 알림 발송과 받은편지함 조회만 담당한다."""

    def __init__(self, repository: ReceiverRepository, watcher: WatcherUseCase) -> None:
        self._repository = repository
        self._watcher = watcher

    async def receiver(self, cmd: ReceiverCommand) -> dict[str, int | None]:
        result = await self._watcher.filter_and_forward(cmd)
        if result.forwarded:
            await _telegram_notify(subject=cmd.subject, from_email=cmd.from_email)
        return {"id": result.id}

    async def list_receiver(self) -> list[ReceiverItem]:
        return await self._repository.list_all()

    async def mark_read(self, item_id: int) -> None:
        await self._repository.mark_read(item_id)
