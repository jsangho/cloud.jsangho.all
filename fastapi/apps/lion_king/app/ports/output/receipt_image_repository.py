from __future__ import annotations

from abc import ABC, abstractmethod

from lion_king.app.dtos.receipt_dto import ReceiptImage, ReceiptSummaryDto


class ObjectNotFoundError(Exception):
    """보관소에 그 키의 객체가 없다. 클라이언트에는 404."""


class ReceiptImageRepository(ABC):
    """보관된 이미지를 **읽는** 출력 포트.

    쓰기(`PhotoRepository`)와 나누는 이유는 방향마다 필요한 권한과 실패 모드가
    다르기 때문이다 — 읽기는 `s3:GetObject`·`s3:ListBucket`이 필요하고, 없는 키를
    만나는 실패가 정상 경로에 포함된다.
    """

    @abstractmethod
    async def list_by_owner(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        """요청자 접두사 아래 이미지를 최신순으로 돌려준다.

        접두사는 서버가 `user_id`로 만든다 — 클라이언트가 지정할 수 없다.
        실패 시 `PhotoStorageUnavailableError`.
        """

    @abstractmethod
    async def load(self, *, key: str) -> ReceiptImage:
        """이미지 바이트를 꺼낸다.

        없으면 `ObjectNotFoundError`, 보관소를 못 쓰면 `PhotoStorageUnavailableError`.
        """
