"""라우터 계층 계약 테스트 — Flutter가 실제로 받는 JSON과 인증 가드를 고정한다."""

from __future__ import annotations

import pytest
from core.security.dependencies import get_current_user
from core.security.token_verifier import TokenPayload
from fastapi.testclient import TestClient
from lion_king.adapter.inbound.api.v1.photo_router import photo_router
from lion_king.app.dtos.photo_dto import PhotoDto, UploadPhotoCommand
from lion_king.app.ports.input.photo_use_case import PhotoUseCase
from lion_king.app.ports.output.photo_repository import PhotoStorageUnavailableError
from lion_king.dependencies.photo_provider import get_photo_use_case
from lion_king.domain.value_objects.photo_content import (
    PhotoTooLargeError,
    UnsupportedPhotoFormatError,
)

from fastapi import FastAPI


class FakeUseCase(PhotoUseCase):
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.seen: list[UploadPhotoCommand] = []

    async def upload(self, command: UploadPhotoCommand) -> PhotoDto:
        if self.error is not None:
            raise self.error
        self.seen.append(command)
        return PhotoDto(
            photo_id="abc123",
            key=f"photos/{command.user_id}/abc123.jpg",
            size_bytes=len(command.data),
            content_type=command.content_type,
        )


def _claims(sub: str = "7") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        aud="jsangho-api",
        exp=9999999999,
        iat=0,
        jti="jti",
        roles=["user"],
        platform="mobile",
        device_id="d1",
    )


def _client(use_case: FakeUseCase, *, authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(photo_router, prefix="/api")
    app.dependency_overrides[get_photo_use_case] = lambda: use_case
    if authenticated:
        app.dependency_overrides[get_current_user] = _claims
    return TestClient(app)


_FILE = {"file": ("shot.jpg", b"\xff\xd8\xff", "image/jpeg")}


def test_upload_returns_camel_case_fields() -> None:
    """Flutter의 `UploadedPhoto.fromJson`이 읽는 키 이름 그대로여야 한다."""
    response = _client(FakeUseCase()).post("/api/photos", files=_FILE)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"photoId", "key", "sizeBytes", "contentType"}
    assert body["photoId"] == "abc123"
    assert body["sizeBytes"] == 3


def test_user_id_comes_from_the_token_not_the_request() -> None:
    """클라이언트가 user_id를 지정할 수 없어야 남의 폴더에 못 넣는다."""
    use_case = FakeUseCase()

    _client(use_case).post(
        "/api/photos", files=_FILE, data={"user_id": "999", "userId": "999"}
    )

    assert use_case.seen[0].user_id == "7"


def test_unauthenticated_upload_is_rejected() -> None:
    """무인증 업로드는 곧 남의 S3에 파일을 넣는 일이다."""
    use_case = FakeUseCase()

    response = _client(use_case, authenticated=False).post("/api/photos", files=_FILE)

    assert response.status_code == 401
    assert use_case.seen == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (UnsupportedPhotoFormatError("image/gif"), 400),
        (PhotoTooLargeError(999), 413),
        (PhotoStorageUnavailableError("no bucket"), 503),
    ],
)
def test_domain_errors_map_to_status_codes(error: Exception, status: int) -> None:
    response = _client(FakeUseCase(error=error)).post("/api/photos", files=_FILE)

    assert response.status_code == status
    # 내부 사정(버킷 이름·예외 원문)이 새어 나가면 안 된다.
    assert "bucket" not in response.text


def test_missing_file_is_rejected() -> None:
    assert _client(FakeUseCase()).post("/api/photos").status_code == 422
