"""Testes unitários — hmac_signer, prompt_builder, heartbeat."""
from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from worker.heartbeat import HeartbeatTask
from worker.hmac_signer import build_auth_headers, serialize_body, sign_payload
from worker.prompt_builder import build_prompt, supported_task_types


# ---------- hmac_signer ----------


def test_serialize_body_is_canonical_sorted_compact():
    body = serialize_body({"b": 1, "a": [3, 2]})
    # Chaves ordenadas, sem espaços.
    assert body == b'{"a":[3,2],"b":1}'


def test_sign_payload_matches_manual_hmac():
    secret = "abc-secret"
    body = b'{"x":1}'
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert sign_payload(body, secret) == expected


def test_sign_payload_constant_time_compare_friendly():
    # Mesma chave + mesmo body = mesmo hex. Repetir chama é deterministico.
    body = b"hello"
    s1 = sign_payload(body, "k")
    s2 = sign_payload(body, "k")
    assert s1 == s2
    assert sign_payload(body, "k2") != s1


def test_build_auth_headers_includes_three_headers_and_signature_matches():
    body = serialize_body({"hello": "world"})
    fixed_now = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
    headers = build_auth_headers(
        body, token="tok", secret="key-abcdef", now=fixed_now
    )
    assert headers["X-Worker-Token"] == "tok"
    assert headers["X-Worker-Timestamp"] == "2026-05-13T12:00:00+00:00"
    assert headers["X-Worker-Signature"] == sign_payload(body, "key-abcdef")
    assert headers["Content-Type"] == "application/json"


def test_signature_replicates_backend_verify_signature():
    """Garante que o worker produz o mesmo hex que o backend valida.

    Backend (app/core/worker_auth.py:_verify_signature) faz:
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    Nosso sign_payload deve produzir o mesmo. Falhar aqui = HMAC quebra em prod.
    """
    secret = "test-hmac-key-32-chars-min!!!!!!!!"
    body = b'{"success":true,"engine_used":"claude","worker_id":"w1"}'
    backend_calc = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    worker_calc = sign_payload(body, secret)
    assert backend_calc == worker_calc


# ---------- prompt_builder ----------


@pytest.mark.parametrize("tt", ["proposal_extraction", "report_analysis", "portfolio_pattern"])
def test_build_prompt_known_task_types_returns_nonempty(tt):
    prompt = build_prompt(tt)
    assert isinstance(prompt, str)
    assert len(prompt) > 30


def test_build_prompt_unknown_task_type_raises():
    with pytest.raises(ValueError, match="task_type desconhecido"):
        build_prompt("nope")


def test_supported_task_types_listed():
    assert set(supported_task_types()) == {
        "proposal_extraction",
        "report_analysis",
        "portfolio_pattern",
    }


# ---------- heartbeat ----------


def test_heartbeat_record_job_counts_success_and_failure():
    hb = HeartbeatTask(client=AsyncMock())
    assert hb.jobs_processed_today == 0
    hb.record_job(success=True)
    hb.record_job(success=True)
    hb.record_job(success=False)
    assert hb.jobs_processed_today == 3
    assert hb.jobs_failed_today == 1


async def test_heartbeat_send_once_posts_with_counters():
    client = AsyncMock()
    hb = HeartbeatTask(client=client)
    hb.record_job(success=True)
    hb.record_job(success=False)
    await hb.send_once()
    assert client.post_signed.await_count == 1
    path, payload = client.post_signed.await_args.args
    assert path == "/internal/worker-heartbeat"
    assert payload["worker_id"] == "test-worker"
    assert payload["jobs_processed_today"] == 2
    assert payload["jobs_failed_today"] == 1
    assert payload["status"] == "ok"


async def test_heartbeat_send_once_swallows_exception():
    client = AsyncMock()
    client.post_signed.side_effect = RuntimeError("backend down")
    hb = HeartbeatTask(client=client)
    # Falha de heartbeat não deve subir — apenas warning.
    await hb.send_once()
