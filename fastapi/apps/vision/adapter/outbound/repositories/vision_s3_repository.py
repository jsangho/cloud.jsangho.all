from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import boto3
from vision.app.dtos.vision_dto import (
    VisionImageUploadResult,
    VisionQuery,
    VisionResponse,
)
from vision.app.ports.output.vision_repository import VisionRepository

_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET", "")
_AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
_UPLOAD_PREFIX = "vision-uploads"


class VisionS3Repository(VisionRepository):
    """Vision 서비스 자기소개 · 이미지 업로드(AWS S3) 어댑터."""

    def __init__(self) -> None:
        self._client = boto3.client("s3", region_name=_AWS_REGION)

    async def introduce_myself(self, query: VisionQuery) -> VisionResponse:
        return VisionResponse(
            id=query.id,
            name=query.name,
            description="이미지·영상을 분석하는 비전 서비스입니다.",
        )

    async def save_image(
        self, filename: str, content_type: str, content: bytes
    ) -> VisionImageUploadResult:
        if not _BUCKET_NAME:
            raise RuntimeError(
                "AWS_S3_BUCKET 환경변수가 설정되지 않았습니다. .env에 버킷 이름을 추가해 주세요."
            )
        suffix = Path(filename).suffix
        key = f"{_UPLOAD_PREFIX}/{uuid.uuid4().hex}{suffix}"

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

        return VisionImageUploadResult(
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            saved_path=f"s3://{_BUCKET_NAME}/{key}",
        )
