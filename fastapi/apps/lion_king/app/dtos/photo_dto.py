from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadPhotoCommand:
    """업로드 요청 한 건.

    `user_id`는 **JWT에서 꺼낸 값**이다. 클라이언트가 보낸 값을 쓰면 남의 폴더에
    사진을 넣을 수 있다.
    """

    user_id: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class PhotoDto:
    """저장 결과. 버킷 이름은 담지 않는다 — 클라이언트가 알 필요가 없다."""

    photo_id: str
    key: str
    size_bytes: int
    content_type: str
