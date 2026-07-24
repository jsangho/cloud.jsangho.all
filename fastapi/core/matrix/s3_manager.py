"""AWS S3 클라이언트 관리 — Keymaker가 관리하는 AWS_* 값으로 boto3 클라이언트를 준비합니다."""

from __future__ import annotations

from typing import Any

import boto3
from core.matrix.vault_keymaker_secret_manager import get_keymaker

DEFAULT_REGION = "ap-northeast-2"


class S3Manager:
    """
    전역 S3 클라이언트 관리자.

    - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` / `AWS_S3_BUCKET`은
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
        region = keymaker.get_secret("AWS_DEFAULT_REGION", DEFAULT_REGION)
        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
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
