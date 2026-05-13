"""Assinatura HMAC dos callbacks worker → backend.

Espelha `backend/app/core/worker_auth.py` no lado do cliente. Os 3 headers
exigidos pelo backend são montados aqui; testes garantem que o cálculo é
byte-idêntico ao do servidor.

Serialização canônica do body: `json.dumps(sort_keys=True, separators=(",", ":"))`.
Sem espaços, chaves ordenadas — o body assinado pelo worker é byte-igual ao
que o backend recebe via `request.body()` se o worker enviar o mesmo bytes
com `httpx.post(..., content=body)` (NÃO `json=dict`, que reserializa).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any


def serialize_body(payload: dict[str, Any]) -> bytes:
    """Serialização canônica do body — determinística e compacta."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(body: bytes, secret: str) -> str:
    """HMAC-SHA256(secret, body) em hex (espelha _verify_signature do backend)."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_auth_headers(
    body: bytes,
    *,
    token: str,
    secret: str,
    now: datetime | None = None,
) -> dict[str, str]:
    """Monta os 3 headers do worker para o backend."""
    ts = (now or datetime.now(UTC)).isoformat()
    return {
        "X-Worker-Token": token,
        "X-Worker-Timestamp": ts,
        "X-Worker-Signature": sign_payload(body, secret),
        "Content-Type": "application/json",
    }
