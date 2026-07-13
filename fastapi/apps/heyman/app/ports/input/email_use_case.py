from __future__ import annotations

from abc import ABC, abstractmethod


class EmailUseCase(ABC):
    """`/manager/v1/email/*` inbound 입력 포트."""

    @abstractmethod
    async def send_faker_report(self, to: str, name: str = "") -> dict:
        """페이커 보고서를 생성해 지정 주소로 발송한다."""
        ...
