from __future__ import annotations

from abc import ABC, abstractmethod

from lion_king.domain.value_objects.photo_content import PhotoContent


class PhotoStorageUnavailableError(Exception):
    """보관소(S3) 설정이 없거나 접근할 수 없다. 클라이언트에는 503."""


class PhotoRepository(ABC):
    """사진 보관소 출력 포트.

    유스케이스는 S3를 모른다 — 저장소를 로컬 디스크나 다른 클라우드로 바꿔도
    유스케이스는 그대로다.
    """

    @abstractmethod
    async def save(self, *, user_id: str, photo: PhotoContent) -> str:
        """저장하고 보관 키를 돌려준다. 실패 시 `PhotoStorageUnavailableError`."""
