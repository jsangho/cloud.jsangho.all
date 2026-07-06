from __future__ import annotations

import json as _json
import os

import httpx
from core.lol.t1_mid_faker_orchestrator import FakerOrchestrator

from manager.app.dtos.email_dto import EmailDto
from manager.app.ports.input.email_use_case import EmailUseCase
from manager.app.ports.output.email_gateway import EmailGateway

_FAKER_PROMPT = (
    "T1 미드라이너 이상혁(페이커)의 플레이 스타일, 대표 챔피언, "
    "최근 시즌 활약상을 분석하는 보고서를 한국어로 작성해주세요. "
    "3~4 문단으로 구성해주세요."
)
_SUBJECT = "[T1] 페이커 미드라이너 활약 보고서"

# 개발자 텔레그램 Chat ID (환경변수로 관리)
_DEV_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


async def _report_to_developer(message: str) -> None:
    """오케스트레이터가 개발자에게 업무 보고를 보내는 내부 함수."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not _DEV_CHAT_ID:
        return  # 설정이 없으면 조용히 스킵
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            content=_json.dumps(
                {"chat_id": _DEV_CHAT_ID, "text": message},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10.0,
        )


class EmailInteractor(EmailUseCase):
    def __init__(self, gateway: EmailGateway) -> None:
        self._gateway = gateway
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._orchestrator = FakerOrchestrator(host=ollama_host)

    async def send_faker_report(self, to: str, name: str = "") -> dict:
        body = await self._orchestrator.generate(_FAKER_PROMPT)
        await self._gateway.send(EmailDto(to=to, subject=_SUBJECT, body=body))

        # 수신자 표시: 이름이 있으면 이름, 없으면 이메일 주소
        recipient = name if name else to
        await _report_to_developer(
            f"✅ {recipient}에게 메일을 정상적으로 발송했습니다."
        )

        return {"status": "sent", "to": to}
