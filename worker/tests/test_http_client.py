"""Testes do WorkerHttpClient — política de retry, HMAC, 4xx vs 5xx."""
from __future__ import annotations

import httpx
import pytest

from worker.hmac_signer import sign_payload
from worker.http_client import RetryableHttpError, WorkerHttpClient


def _mock_transport(*responses_or_callables):
    """Constrói um httpx.MockTransport que devolve `responses` em ordem.

    Cada item pode ser:
      - httpx.Response — devolvido como está
      - exception subclasse de Exception — `raise`
    """
    iterator = iter(responses_or_callables)

    def handler(request: httpx.Request) -> httpx.Response:
        nxt = next(iterator)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    return httpx.MockTransport(handler)


def _client_with_transport(transport: httpx.MockTransport) -> WorkerHttpClient:
    client = WorkerHttpClient()
    # Substitui o AsyncClient real por um com MockTransport.
    client._client = httpx.AsyncClient(
        base_url="http://test-backend.invalid",
        transport=transport,
    )
    return client


async def test_post_signed_attaches_three_auth_headers():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = _client_with_transport(transport)
    try:
        resp = await client.post_signed("/internal/agent-results/run-1", {"a": 1})
        assert resp.status_code == 200
        assert len(captured) == 1
        req = captured[0]
        assert req.headers.get("X-Worker-Token") == "test-shared-secret-32-chars-min!!"
        assert req.headers.get("X-Worker-Timestamp")
        assert req.headers.get("X-Worker-Signature")
        # A signature do header deve bater com o body raw enviado.
        expected_sig = sign_payload(req.content, "test-hmac-key-32-chars-min!!!!!!!!")
        assert req.headers["X-Worker-Signature"] == expected_sig
    finally:
        await client.aclose()


async def test_post_signed_retries_on_503_then_succeeds():
    responses = [
        httpx.Response(503, json={"err": "down"}),
        httpx.Response(503, json={"err": "still"}),
        httpx.Response(200, json={"ok": True}),
    ]
    transport = _mock_transport(*responses)
    client = _client_with_transport(transport)
    try:
        resp = await client.post_signed("/internal/worker-heartbeat", {"x": 1})
        assert resp.status_code == 200
    finally:
        await client.aclose()


async def test_post_signed_exhausts_retry_raises_retryable():
    responses = [httpx.Response(503), httpx.Response(503), httpx.Response(503)]
    transport = _mock_transport(*responses)
    client = _client_with_transport(transport)
    try:
        with pytest.raises(RetryableHttpError):
            await client.post_signed("/p", {"a": 1})
    finally:
        await client.aclose()


async def test_post_signed_no_retry_on_400():
    """4xx (exceto 408) = falha definitiva, sem retry."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"err": "bad request"})

    transport = httpx.MockTransport(handler)
    client = _client_with_transport(transport)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await client.post_signed("/p", {"a": 1})
        assert calls["n"] == 1, "4xx não deve disparar retry"
    finally:
        await client.aclose()


async def test_post_signed_retries_on_408():
    """408 (request timeout) é a única 4xx que vale retry."""
    responses = [httpx.Response(408), httpx.Response(200, json={"ok": True})]
    transport = _mock_transport(*responses)
    client = _client_with_transport(transport)
    try:
        resp = await client.post_signed("/p", {"a": 1})
        assert resp.status_code == 200
    finally:
        await client.aclose()


async def test_post_signed_retries_on_network_error():
    transport = _mock_transport(
        httpx.ConnectError("DNS"),
        httpx.Response(200, json={"ok": True}),
    )
    client = _client_with_transport(transport)
    try:
        resp = await client.post_signed("/p", {"a": 1})
        assert resp.status_code == 200
    finally:
        await client.aclose()
