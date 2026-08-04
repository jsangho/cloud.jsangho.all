"""보관된 사진을 **읽는** S3 어댑터 (역방향: S3 → 서버).

정방향 업로드(`photo_s3_repository.py`)와 같은 버킷·같은 키 구조(`photos/{sub}/…`)를
쓰지만 필요한 IAM 권한이 다르다 — 이쪽은 `s3:GetObject`와 `s3:ListBucket`이 있어야
동작한다. 정방향은 `s3:PutObject`만 썼다.

목록의 `thumbnail_url`은 **단명 presigned URL**이다. 버킷을 공개로 열지 않고도
브라우저가 이미지를 직접 받아갈 수 있게 하기 위한 것이고, 그래서 응답에 버킷 이름이
들어가지 않는다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from core.matrix.s3_manager import get_s3_manager
from lion_king.app.dtos.receipt_dto import ReceiptImage, ReceiptSummaryDto
from lion_king.app.ports.output.photo_repository import PhotoStorageUnavailableError
from lion_king.app.ports.output.receipt_image_repository import (
    ObjectNotFoundError,
    ReceiptImageRepository,
)
from lion_king.domain.value_objects.photo_content import ALLOWED_CONTENT_TYPES
from lion_king.domain.value_objects.receipt_key import PHOTO_KEY_PREFIX

# 썸네일 URL 수명. 화면을 열어 두고 훑는 시간은 덮되, 링크가 유출돼도 오래
# 살아 있지 않을 만큼 짧게 잡는다.
_THUMBNAIL_URL_TTL_SECONDS = 300

# 한 번에 돌려주는 최대 장수. 페이지네이션은 아직 계약에 없으므로 상한으로 막는다 —
# 없으면 사진이 쌓인 계정에서 목록 응답이 무한정 커진다.
_MAX_LIST_KEYS = 100

_ALLOWED_EXTENSIONS = tuple(ALLOWED_CONTENT_TYPES.values())

# S3가 "없다"고 말하는 방식은 API마다 다르다.
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "404", "NotFound"})


class ReceiptImageS3Repository(ReceiptImageRepository):
    async def list_by_owner(self, *, user_id: str) -> list[ReceiptSummaryDto]:
        client, bucket = _require_storage()
        prefix = f"{PHOTO_KEY_PREFIX}/{user_id}/"

        try:
            # boto3는 동기다. 그대로 부르면 목록 조회 내내 이벤트 루프가 멈춘다.
            response = await asyncio.to_thread(
                client.list_objects_v2,
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=_MAX_LIST_KEYS,
            )
        except (BotoCoreError, ClientError) as exc:
            raise PhotoStorageUnavailableError(str(exc)) from exc

        contents = [
            item
            for item in response.get("Contents", [])
            if str(item.get("Key", "")).lower().endswith(_ALLOWED_EXTENSIONS)
        ]
        # 최근에 찍은 것이 위로 온다.
        contents.sort(key=lambda item: item.get("LastModified") or _EPOCH, reverse=True)

        return [
            ReceiptSummaryDto(
                key=item["Key"],
                thumbnail_url=_presigned_url(client, bucket, item["Key"]),
                captured_at=_to_datetime(item.get("LastModified")),
            )
            for item in contents
        ]

    async def load(self, *, key: str) -> ReceiptImage:
        client, bucket = _require_storage()

        try:
            response = await asyncio.to_thread(
                client.get_object, Bucket=bucket, Key=key
            )
            data = await asyncio.to_thread(response["Body"].read)
        except ClientError as exc:
            if _is_not_found(exc):
                raise ObjectNotFoundError(key) from exc
            raise PhotoStorageUnavailableError(str(exc)) from exc
        except BotoCoreError as exc:
            raise PhotoStorageUnavailableError(str(exc)) from exc

        return ReceiptImage(
            data=data,
            content_type=response.get("ContentType") or "image/jpeg",
        )


_EPOCH = datetime.fromtimestamp(0)


def _require_storage() -> tuple[Any, str]:
    manager = get_s3_manager()
    client = manager.get_client()
    bucket = manager.get_bucket_name()
    if client is None or not bucket:
        raise PhotoStorageUnavailableError(
            "AWS 자격증명 또는 AWS_S3_BUCKET이 설정되지 않았습니다."
        )
    return client, bucket


def _presigned_url(client: Any, bucket: str, key: str) -> str:
    """서명은 로컬 계산이라 네트워크를 타지 않는다 — 스레드로 넘길 이유가 없다."""
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=_THUMBNAIL_URL_TTL_SECONDS,
    )


def _is_not_found(exc: ClientError) -> bool:
    error = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
    return str(error.get("Code", "")) in _NOT_FOUND_CODES


def _to_datetime(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None
