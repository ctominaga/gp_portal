"""R2Storage — backend Cloudflare R2 (S3-compatible) via boto3."""
from __future__ import annotations

from typing import Any

from .base import ObjectStorage, StorageError


class R2Storage(ObjectStorage):
    def __init__(
        self,
        *,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "auto",
    ) -> None:
        if not (account_id and access_key and secret_key and bucket):
            raise StorageError("R2Storage exige account_id, access_key, secret_key e bucket")
        self._bucket = bucket
        # Lazy import — boto3 não é necessário no LocalStorage e em CI
        import boto3
        from botocore.client import Config

        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def put(
        self,
        content: bytes,
        key: str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        try:
            extra: dict[str, Any] = {}
            if content_type:
                extra["ContentType"] = content_type
            if metadata:
                extra["Metadata"] = metadata
            self._client.put_object(Bucket=self._bucket, Key=key, Body=content, **extra)
        except Exception as exc:
            raise StorageError(f"falha put R2: {exc}") from exc
        return key

    def get(self, key: str) -> bytes:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
            return obj["Body"].read()
        except self._client.exceptions.NoSuchKey as exc:  # type: ignore[union-attr]
            raise StorageError(f"not_found: {key}") from exc
        except Exception as exc:
            raise StorageError(f"falha get R2: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"falha delete R2: {exc}") from exc

    def get_signed_url(self, key: str, *, ttl_seconds: int = 300) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception as exc:
            raise StorageError(f"falha generate_presigned_url R2: {exc}") from exc
