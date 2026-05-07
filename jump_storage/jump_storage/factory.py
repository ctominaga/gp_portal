"""Factory: lê env e devolve a instância correta de ObjectStorage.

Env:
  OBJECT_STORAGE_BACKEND = local | r2
  Para local:
    LOCAL_STORAGE_ROOT (default ~/.jump-storage)
    LOCAL_STORAGE_BASE_URL (default http://localhost:8000)
    LOCAL_STORAGE_SIGNING_SECRET (obrigatório, herdado de JWT_SECRET por convenção)
  Para r2:
    R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET
    R2_ENDPOINT_URL (opcional)
"""
from __future__ import annotations

import os
from functools import lru_cache

from .base import ObjectStorage, StorageError
from .local import LocalStorage, storage_root_from_env
from .r2 import R2Storage


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    backend = os.environ.get("OBJECT_STORAGE_BACKEND", "local").lower().strip()
    if backend == "local":
        secret = os.environ.get("LOCAL_STORAGE_SIGNING_SECRET") or os.environ.get(
            "JWT_SECRET", ""
        )
        if not secret:
            raise StorageError(
                "LOCAL_STORAGE_SIGNING_SECRET ou JWT_SECRET deve estar definido"
            )
        return LocalStorage(
            root=storage_root_from_env(),
            signing_secret=secret,
            base_url=os.environ.get("LOCAL_STORAGE_BASE_URL", "http://localhost:8000"),
        )
    if backend == "r2":
        return R2Storage(
            account_id=os.environ.get("R2_ACCOUNT_ID", ""),
            access_key=os.environ.get("R2_ACCESS_KEY", ""),
            secret_key=os.environ.get("R2_SECRET_KEY", ""),
            bucket=os.environ.get("R2_BUCKET", ""),
            endpoint_url=os.environ.get("R2_ENDPOINT_URL") or None,
        )
    raise StorageError(f"OBJECT_STORAGE_BACKEND inválido: {backend!r}")


def reset_cache() -> None:
    """Permite testes resetarem a fábrica."""
    get_storage.cache_clear()
