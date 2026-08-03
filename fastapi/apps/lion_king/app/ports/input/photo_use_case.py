from __future__ import annotations

from abc import ABC, abstractmethod

from lion_king.app.dtos.photo_dto import PhotoDto, UploadPhotoCommand


class PhotoUseCase(ABC):
    """사진 보관 입력 포트."""

    @abstractmethod
    async def upload(self, command: UploadPhotoCommand) -> PhotoDto:
        """형식·용량을 검증하고 보관소에 저장한다.

        형식이 맞지 않으면 `UnsupportedPhotoFormatError`,
        상한을 넘으면 `PhotoTooLargeError`를 던진다.
        """
