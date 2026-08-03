from __future__ import annotations

from lion_king.app.dtos.photo_dto import PhotoDto, UploadPhotoCommand
from lion_king.app.ports.input.photo_use_case import PhotoUseCase
from lion_king.app.ports.output.photo_repository import PhotoRepository
from lion_king.domain.value_objects.photo_content import PhotoContent


class PhotoInteractor(PhotoUseCase):
    def __init__(self, repository: PhotoRepository) -> None:
        self._repository = repository

    async def upload(self, command: UploadPhotoCommand) -> PhotoDto:
        # 검증이 먼저다 — 형식이 틀린 파일을 보관소까지 보내지 않는다.
        photo = PhotoContent.validated(
            data=command.data, content_type=command.content_type
        )
        key = await self._repository.save(user_id=command.user_id, photo=photo)
        return PhotoDto(
            photo_id=key.rsplit("/", 1)[-1].rsplit(".", 1)[0],
            key=key,
            size_bytes=photo.size_bytes,
            content_type=photo.content_type,
        )
