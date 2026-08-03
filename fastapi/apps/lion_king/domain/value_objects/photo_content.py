"""사진 파일 자체에 대한 규칙. 프레임워크·인프라를 모르는 순수 파이썬이다."""

from __future__ import annotations

from dataclasses import dataclass

# 서버가 받아주는 형식. Flutter 쪽 `_allowedExtensions`와 **같은 집합이어야 한다** —
# 한쪽만 넓히면 앱은 보내는데 서버가 거절하는 상태가 된다.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

# 사진 한 장의 상한. 앱도 같은 값으로 미리 거르지만, 앱을 우회한 요청이 있으므로
# 서버가 최종 판단을 한다.
MAX_PHOTO_BYTES = 10 * 1024 * 1024


class UnsupportedPhotoFormatError(Exception):
    """jpeg/png가 아니다."""


class PhotoTooLargeError(Exception):
    """상한을 넘었다."""


@dataclass(frozen=True)
class PhotoContent:
    """검증을 통과한 사진 한 장.

    이 객체가 만들어졌다는 것은 형식·용량이 이미 확인됐다는 뜻이다 —
    이후 단계에서 다시 검사하지 않는다.
    """

    data: bytes
    content_type: str
    extension: str

    @classmethod
    def validated(cls, *, data: bytes, content_type: str) -> PhotoContent:
        extension = ALLOWED_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise UnsupportedPhotoFormatError(content_type)
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoTooLargeError(len(data))
        return cls(data=data, content_type=content_type, extension=extension)

    @property
    def size_bytes(self) -> int:
        return len(self.data)
