"""사진 보관소 — AWS S3 어댑터.

키 구조: `photos/{user_id}/{uuid}{ext}`

유저별로 접두사를 나누는 이유는 ① 남의 사진과 섞이지 않고 ② 나중에 유저 단위
조회·삭제·수명 정책(lifecycle rule)을 접두사만으로 걸 수 있어서다.

`user_id`는 호출부가 JWT에서 꺼낸 값이라 클라이언트가 조작할 수 없다.
"""

from __future__ import annotations

import asyncio
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from core.matrix.s3_manager import get_s3_manager
from lion_king.app.ports.output.photo_repository import (
    PhotoRepository,
    PhotoStorageUnavailableError,
)
from lion_king.domain.value_objects.photo_content import PhotoContent

_KEY_PREFIX = "photos"


class PhotoS3Repository(PhotoRepository):
    async def save(self, *, user_id: str, photo: PhotoContent) -> str:
        manager = get_s3_manager()
        client = manager.get_client()
        bucket = manager.get_bucket_name()
        if client is None or not bucket:
            raise PhotoStorageUnavailableError(
                "AWS 자격증명 또는 AWS_S3_BUCKET이 설정되지 않았습니다."
            )

        key = f"{_KEY_PREFIX}/{user_id}/{uuid.uuid4().hex}{photo.extension}"
        try:
            # boto3는 동기 라이브러리다. 그대로 부르면 이벤트 루프가 업로드 내내
            # 멈춰 다른 요청을 처리하지 못한다.
            await asyncio.to_thread(
                client.put_object,
                Bucket=bucket,
                Key=key,
                Body=photo.data,
                ContentType=photo.content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            raise PhotoStorageUnavailableError(str(exc)) from exc

        return key
