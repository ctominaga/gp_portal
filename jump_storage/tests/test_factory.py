"""Testes do factory get_storage()."""
from __future__ import annotations

from pathlib import Path

import pytest

from jump_storage import LocalStorage, R2Storage, get_storage
from jump_storage.base import StorageError
from jump_storage.factory import reset_cache


@pytest.fixture(autouse=True)
def _reset_factory():
    reset_cache()
    yield
    reset_cache()


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "OBJECT_STORAGE_BACKEND",
        "LOCAL_STORAGE_ROOT",
        "LOCAL_STORAGE_BASE_URL",
        "LOCAL_STORAGE_SIGNING_SECRET",
        "JWT_SECRET",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY",
        "R2_SECRET_KEY",
        "R2_BUCKET",
    ):
        monkeypatch.delenv(k, raising=False)


def test_default_backend_e_local_e_pega_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET", "fallback-secret")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))

    s = get_storage()
    assert isinstance(s, LocalStorage)


def test_local_sem_secret_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    with pytest.raises(StorageError, match="SIGNING_SECRET"):
        get_storage()


def test_r2_backend_constroi_com_credenciais(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "r2")
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct")
    monkeypatch.setenv("R2_ACCESS_KEY", "ak")
    monkeypatch.setenv("R2_SECRET_KEY", "sk")
    monkeypatch.setenv("R2_BUCKET", "bkt")
    s = get_storage()
    assert isinstance(s, R2Storage)


def test_r2_backend_sem_credenciais_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "r2")
    with pytest.raises(StorageError):
        get_storage()


def test_backend_invalido_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "azure-blob")
    monkeypatch.setenv("JWT_SECRET", "x")
    with pytest.raises(StorageError, match="OBJECT_STORAGE_BACKEND"):
        get_storage()
