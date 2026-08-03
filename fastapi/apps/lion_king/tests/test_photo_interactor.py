"""사진 보관 유스케이스 회귀 테스트. S3는 fake로 대체한다."""

from __future__ import annotations

import pytest
from lion_king.app.dtos.photo_dto import UploadPhotoCommand
from lion_king.app.ports.output.photo_repository import (
    PhotoRepository,
    PhotoStorageUnavailableError,
)
from lion_king.app.use_cases.photo_interactor import PhotoInteractor
from lion_king.domain.value_objects.photo_content import (
    MAX_PHOTO_BYTES,
    PhotoContent,
    PhotoTooLargeError,
    UnsupportedPhotoFormatError,
)


class FakeStorage(PhotoRepository):
    def __init__(self, *, broken: bool = False) -> None:
        self.saved: list[tuple[str, PhotoContent]] = []
        self._broken = broken

    async def save(self, *, user_id: str, photo: PhotoContent) -> str:
        if self._broken:
            raise PhotoStorageUnavailableError("bucket missing")
        self.saved.append((user_id, photo))
        return f"photos/{user_id}/deadbeef{photo.extension}"


def _command(**overrides) -> UploadPhotoCommand:
    base = {"user_id": "7", "data": b"\xff\xd8\xff", "content_type": "image/jpeg"}
    return UploadPhotoCommand(**{**base, **overrides})


@pytest.mark.asyncio
async def test_jpeg_is_stored_under_the_users_prefix() -> None:
    """유저별 접두사가 갈려야 남의 사진과 섞이지 않는다."""
    storage = FakeStorage()

    result = await PhotoInteractor(storage).upload(_command())

    assert result.key.startswith("photos/7/")
    assert result.key.endswith(".jpg")
    assert result.size_bytes == 3
    assert result.content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_png_is_accepted() -> None:
    result = await PhotoInteractor(FakeStorage()).upload(
        _command(content_type="image/png")
    )
    assert result.key.endswith(".png")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content_type",
    ["image/gif", "application/pdf", "text/plain", "", "image/jpeg; charset=utf-8"],
)
async def test_other_formats_are_rejected(content_type: str) -> None:
    """허용 목록 방식이라 모르는 형식은 전부 거부된다."""
    storage = FakeStorage()

    with pytest.raises(UnsupportedPhotoFormatError):
        await PhotoInteractor(storage).upload(_command(content_type=content_type))

    assert storage.saved == []


@pytest.mark.asyncio
async def test_oversized_photo_never_reaches_storage() -> None:
    """상한 초과분이 보관소까지 가면 대역폭·비용이 그대로 나간다."""
    storage = FakeStorage()

    with pytest.raises(PhotoTooLargeError):
        await PhotoInteractor(storage).upload(
            _command(data=b"x" * (MAX_PHOTO_BYTES + 1))
        )

    assert storage.saved == []


@pytest.mark.asyncio
async def test_photo_exactly_at_the_limit_is_accepted() -> None:
    """경계값은 통과해야 한다 — 상한은 '초과'부터 거부다."""
    result = await PhotoInteractor(FakeStorage()).upload(
        _command(data=b"x" * MAX_PHOTO_BYTES)
    )
    assert result.size_bytes == MAX_PHOTO_BYTES


@pytest.mark.asyncio
async def test_user_id_comes_from_the_command_not_the_file() -> None:
    """호출부가 JWT에서 꺼낸 값이 그대로 경로가 된다."""
    storage = FakeStorage()

    await PhotoInteractor(storage).upload(_command(user_id="42"))

    assert storage.saved[0][0] == "42"
    assert storage.saved[0][1].content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_storage_failure_propagates() -> None:
    """보관소 장애를 성공으로 둔갑시키지 않는다."""
    with pytest.raises(PhotoStorageUnavailableError):
        await PhotoInteractor(FakeStorage(broken=True)).upload(_command())


@pytest.mark.asyncio
async def test_photo_id_is_derived_from_the_key() -> None:
    result = await PhotoInteractor(FakeStorage()).upload(_command())
    assert result.photo_id == "deadbeef"
