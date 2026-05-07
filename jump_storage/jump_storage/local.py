"""LocalStorage — backend filesystem para dev e CI.

Signed URL no LocalStorage é uma URL apontando para
`{LOCAL_STORAGE_BASE_URL}/files/signed/{token}/{key}`. O `token` é
um HMAC-SHA256(secret, key + ":" + exp) compactado em hex curto, com
`exp` (epoch segundos) embutido. O backend FastAPI tem uma rota que
valida e serve.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from pathlib import Path
from urllib.parse import quote

from .base import ObjectStorage, StorageError


class LocalStorage(ObjectStorage):
    def __init__(
        self,
        root: Path,
        *,
        signing_secret: str,
        base_url: str = "http://localhost:8000",
    ) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._signing_secret = signing_secret
        self._base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        # Normaliza para evitar path traversal
        clean = key.replace("\\", "/").lstrip("/")
        if ".." in Path(clean).parts:
            raise StorageError(f"key inválido: {key}")
        return self._root / clean

    def put(
        self,
        content: bytes,
        key: str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(content)
        except OSError as exc:
            raise StorageError(f"falha ao gravar {key}: {exc}") from exc
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"not_found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"falha ao remover {key}: {exc}") from exc

    def get_signed_url(self, key: str, *, ttl_seconds: int = 300) -> str:
        exp = int(time.time()) + ttl_seconds
        token = sign_local_url(key, exp=exp, secret=self._signing_secret)
        # `key` precisa ir URL-encodado para preservar barras e nomes
        return f"{self._base_url}/files/signed/{token}/{exp}/{quote(key, safe='/')}"


def sign_local_url(key: str, *, exp: int, secret: str) -> str:
    """Calcula HMAC-SHA256(secret, f'{key}:{exp}') e retorna em hex."""
    payload = f"{key}:{exp}".encode()
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_local_signature(token: str, key: str, exp: int, secret: str) -> bool:
    """Confere se token bate e se exp ainda não passou."""
    if exp < int(time.time()):
        return False
    expected = sign_local_url(key, exp=exp, secret=secret)
    return hmac.compare_digest(token, expected)


def storage_root_from_env(default: Path | None = None) -> Path:
    raw = os.environ.get("LOCAL_STORAGE_ROOT")
    if raw:
        return Path(raw)
    return default or Path.home() / ".jump-storage"
