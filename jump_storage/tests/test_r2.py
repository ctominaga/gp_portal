"""Testes do R2Storage com mock de boto3 (sem credenciais reais)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jump_storage import R2Storage
from jump_storage.base import StorageError


def _r2_with_mock(client_mock: MagicMock) -> R2Storage:
    with patch("boto3.client", return_value=client_mock):
        return R2Storage(
            account_id="acct",
            access_key="ak",
            secret_key="sk",
            bucket="bkt",
        )


def test_construcao_sem_credenciais_levanta() -> None:
    with pytest.raises(StorageError):
        R2Storage(account_id="", access_key="ak", secret_key="sk", bucket="b")


def test_put_chama_put_object() -> None:
    cli = MagicMock()
    s = _r2_with_mock(cli)
    s.put(b"hello", "k.txt", content_type="text/plain", metadata={"x": "1"})
    cli.put_object.assert_called_once()
    kwargs = cli.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "bkt"
    assert kwargs["Key"] == "k.txt"
    assert kwargs["Body"] == b"hello"
    assert kwargs["ContentType"] == "text/plain"
    assert kwargs["Metadata"] == {"x": "1"}


def test_get_devolve_body_read() -> None:
    cli = MagicMock()
    cli.get_object.return_value = {"Body": MagicMock(read=lambda: b"data")}
    s = _r2_with_mock(cli)
    assert s.get("k") == b"data"


def test_get_inexistente_levanta_storage_error() -> None:
    cli = MagicMock()
    cli.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})

    def _raise(**_: object) -> None:
        raise cli.exceptions.NoSuchKey()

    cli.get_object.side_effect = _raise
    s = _r2_with_mock(cli)
    with pytest.raises(StorageError, match="not_found"):
        s.get("k")


def test_exists_true_quando_head_object_sucesso() -> None:
    cli = MagicMock()
    cli.head_object.return_value = {}
    s = _r2_with_mock(cli)
    assert s.exists("k") is True


def test_exists_false_quando_head_object_falha() -> None:
    cli = MagicMock()
    cli.head_object.side_effect = Exception("404")
    s = _r2_with_mock(cli)
    assert s.exists("k") is False


def test_get_signed_url_chama_generate_presigned_url() -> None:
    cli = MagicMock()
    cli.generate_presigned_url.return_value = "https://signed-url"
    s = _r2_with_mock(cli)
    url = s.get_signed_url("k", ttl_seconds=600)
    assert url == "https://signed-url"
    cli.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "bkt", "Key": "k"},
        ExpiresIn=600,
    )


def test_delete_idempotente_em_erro_genérico() -> None:
    cli = MagicMock()
    cli.delete_object.side_effect = Exception("network glitch")
    s = _r2_with_mock(cli)
    # delete em erro genérico devolve StorageError; chamador trata como quiser
    with pytest.raises(StorageError):
        s.delete("k")
