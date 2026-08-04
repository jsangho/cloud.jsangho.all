"""영수증으로 판독할 S3 키. 소유권 규칙이 이 파일 하나에 모여 있다.

**역방향(S3 → 서버) 흐름의 핵심 방어선이다.** 업로드(정방향)는 키를 서버가 만들어
`photos/{jwt.sub}/…`로 고정했기 때문에 안전했지만, 읽기 방향에서는 키를 클라이언트가
보내므로 그 방어가 자동으로 따라오지 않는다. 남의 접두사를 지정하면 서버 자격증명으로
남의 사진을 읽어주는 꼴이 된다.

존재 여부를 알려주지 않기 위해 라우터는 이 예외를 403이 아니라 **404**로 옮긴다 —
남의 키를 찔러 무엇이 있는지 탐색하는 경로를 막는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from lion_king.domain.value_objects.photo_content import ALLOWED_CONTENT_TYPES

# 업로드 어댑터가 쓰는 것과 **같은 상수여야 한다.** 두 곳으로 갈라지는 순간
# 소유권 검사와 실제 저장 경로가 어긋난다.
PHOTO_KEY_PREFIX = "photos"

_ALLOWED_EXTENSIONS = frozenset(ALLOWED_CONTENT_TYPES.values())


class ReceiptKeyNotOwnedError(Exception):
    """키 형식이 틀렸거나 요청자의 접두사가 아니다. 클라이언트에는 404."""


@dataclass(frozen=True)
class ReceiptKey:
    """소유권 검증을 통과한 키.

    이 객체가 만들어졌다는 것은 `photos/{owner_sub}/` 아래의 정상 키라는 뜻이다 —
    이후 단계에서 다시 검사하지 않는다.
    """

    value: str

    @classmethod
    def validated(cls, *, key: str, owner_sub: str) -> ReceiptKey:
        if not owner_sub:
            raise ReceiptKeyNotOwnedError("소유자를 확인할 수 없습니다.")

        prefix = f"{PHOTO_KEY_PREFIX}/{owner_sub}/"
        if not key.startswith(prefix):
            raise ReceiptKeyNotOwnedError(key)

        name = key[len(prefix) :]
        # 하위 경로·상위 이동을 허용하면 접두사 검사를 우회할 수 있다.
        if not name or "/" in name or ".." in name:
            raise ReceiptKeyNotOwnedError(key)

        extension = name[name.rfind(".") :].lower() if "." in name else ""
        if extension not in _ALLOWED_EXTENSIONS:
            raise ReceiptKeyNotOwnedError(key)

        return cls(value=key)
