"""Testes do LocalStorage."""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

from jump_storage import LocalStorage, sign_local_url, verify_local_signature
from jump_storage.base import StorageError


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(root=tmp_path, signing_secret="testsecret", base_url="http://test")


def test_put_get_round_trip(storage: LocalStorage) -> None:
    storage.put(b"hello", "a/b.txt")
    assert storage.get("a/b.txt") == b"hello"


def test_exists(storage: LocalStorage) -> None:
    assert storage.exists("nada") is False
    storage.put(b"x", "k")
    assert storage.exists("k") is True


def test_delete_idempotente(storage: LocalStorage) -> None:
    storage.put(b"x", "k")
    storage.delete("k")
    storage.delete("k")  # de novo, sem erro
    assert storage.exists("k") is False


def test_get_inexistente_levanta_storage_error(storage: LocalStorage) -> None:
    with pytest.raises(StorageError) as exc:
        storage.get("nao-existe")
    assert "not_found" in str(exc.value)


def test_path_traversal_e_rejeitado(storage: LocalStorage) -> None:
    with pytest.raises(StorageError):
        storage.put(b"x", "../../../etc/passwd")


def test_get_signed_url_formato(storage: LocalStorage) -> None:
    storage.put(b"x", "proposals/1.pdf")
    url = storage.get_signed_url("proposals/1.pdf", ttl_seconds=300)
    parsed = urlparse(url)
    assert parsed.scheme == "http"
    assert parsed.netloc == "test"
    # /files/signed/<token>/<exp>/<key>
    parts = parsed.path.lstrip("/").split("/", 4)
    assert parts[0] == "files"
    assert parts[1] == "signed"
    assert len(parts[2]) == 64  # hex SHA256
    assert int(parts[3]) > int(time.time())
    assert parts[4] == "proposals/1.pdf"


def test_signature_round_trip() -> None:
    exp = int(time.time()) + 60
    token = sign_local_url("proposals/1.pdf", exp=exp, secret="s")
    assert verify_local_signature(token, "proposals/1.pdf", exp, "s") is True


def test_signature_expirada_falha() -> None:
    exp = int(time.time()) - 1
    token = sign_local_url("k", exp=exp, secret="s")
    assert verify_local_signature(token, "k", exp, "s") is False


def test_signature_secret_errado_falha() -> None:
    exp = int(time.time()) + 60
    token = sign_local_url("k", exp=exp, secret="s1")
    assert verify_local_signature(token, "k", exp, "s2") is False


def test_signature_key_errado_falha() -> None:
    exp = int(time.time()) + 60
    token = sign_local_url("k1", exp=exp, secret="s")
    assert verify_local_signature(token, "k2", exp, "s") is False
