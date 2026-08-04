"""AWS S3 클라이언트 관리 — Keymaker가 관리하는 AWS_* 값으로 boto3 클라이언트를 준비합니다."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config

from core.matrix.vault_keymaker_secret_manager import get_keymaker

DEFAULT_REGION = "ap-northeast-2"

# presigned URL은 **리전 엔드포인트로 서명해야 한다.** 기본 설정에서는 호스트가
# 글로벌 `s3.amazonaws.com`으로 잡혀 ap-northeast-2 서명과 어긋나고, 브라우저가
# 그 URL을 그대로 받으면 403 SignatureDoesNotMatch가 난다. SDK 호출은 botocore가
# 내부에서 리다이렉트를 따라가 티가 나지 않지만, presigned URL은 복구되지 않는다.
_CLIENT_CONFIG = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})


class S3Manager:
    """
    전역 S3 클라이언트 관리자.

    - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `AWS_S3_BUCKET`은
      `Keymaker.get_secret()`으로 조회 (`.env` 로드는 Keymaker가 한곳에서 담당)
    - boto3 S3 클라이언트 보관
    """

    _instance: S3Manager | None = None

    def __init__(self) -> None:
        self._client: Any = None

    @classmethod
    def instance(cls) -> S3Manager:
        """프로세스당 하나의 S3Manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """테스트 등에서 인스턴스를 비울 때만 사용."""
        cls._instance = None

    def _bootstrap_client(self) -> None:
        keymaker = get_keymaker()
        access_key = keymaker.get_secret("AWS_ACCESS_KEY_ID")
        secret_key = keymaker.get_secret("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            self._client = None
            return
        region = keymaker.get_secret("AWS_REGION", DEFAULT_REGION)
        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=_CLIENT_CONFIG,
        )

    def get_client(self) -> Any:
        """설정된 경우 `boto3` S3 클라이언트, 없으면 `None`."""
        if self._client is None:
            self._bootstrap_client()
        return self._client

    def is_ready(self) -> bool:
        return self.get_client() is not None

    def get_bucket_name(self) -> str:
        return get_keymaker().get_secret("AWS_S3_BUCKET")

    def list_buckets(self) -> list[str]:
        client = self.get_client()
        if client is None:
            raise ValueError(
                "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요."
            )
        response = client.list_buckets()
        return [bucket["Name"] for bucket in response["Buckets"]]


def get_s3_manager() -> S3Manager:
    """애플리케이션 전역에서 사용할 S3Manager 싱글톤."""
    return S3Manager.instance()
