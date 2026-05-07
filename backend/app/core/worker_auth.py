"""Autenticação dupla do worker → backend.

Spec v3 §7.5/8.x: callbacks do worker carregam:
  X-Worker-Token       Bearer-like, valor de WORKER_SHARED_SECRET
  X-Worker-Timestamp   ISO 8601 UTC. Anti-replay: rejeita se diferença com
                       agora > MAX_TIMESTAMP_SKEW_PAST (5 min) ou
                       MAX_TIMESTAMP_SKEW_FUTURE (30 s)
  X-Worker-Signature   HMAC-SHA256(WORKER_HMAC_KEY, body) em hex

Uma falha em qualquer um → 401.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings

# Tolerâncias do clock skew
MAX_TIMESTAMP_SKEW_PAST = timedelta(minutes=5)
MAX_TIMESTAMP_SKEW_FUTURE = timedelta(seconds=30)


def _verify_timestamp(ts_str: str, *, now: datetime) -> None:
    try:
        ts = datetime.fromisoformat(ts_str)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, f"timestamp inválido: {exc}"
        ) from exc
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    skew = now - ts
    if skew > MAX_TIMESTAMP_SKEW_PAST:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"timestamp velho (skew {skew.total_seconds():.0f}s > {MAX_TIMESTAMP_SKEW_PAST.total_seconds():.0f}s)",
        )
    if -skew > MAX_TIMESTAMP_SKEW_FUTURE:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            f"timestamp futuro (skew {-skew.total_seconds():.0f}s à frente)",
        )


def _verify_signature(*, body: bytes, signature_hex: str, secret: str) -> None:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature_hex, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "assinatura inválida"
        )


async def require_worker_auth(
    request: Request,
    x_worker_token: Annotated[str | None, Header(alias="X-Worker-Token")] = None,
    x_worker_timestamp: Annotated[
        str | None, Header(alias="X-Worker-Timestamp")
    ] = None,
    x_worker_signature: Annotated[
        str | None, Header(alias="X-Worker-Signature")
    ] = None,
    *,
    now: datetime | None = None,
) -> bytes:
    """Dependência FastAPI que valida os 3 headers e devolve o body bruto."""
    if not x_worker_token or not x_worker_timestamp or not x_worker_signature:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "headers de worker faltando"
        )

    settings = get_settings()
    if x_worker_token != settings.worker_shared_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de worker inválido")

    body = await request.body()
    _verify_signature(
        body=body,
        signature_hex=x_worker_signature,
        secret=settings.worker_hmac_key,
    )
    _verify_timestamp(x_worker_timestamp, now=now or datetime.now(UTC))
    return body


def sign_worker_payload(body: bytes, *, secret: str) -> str:
    """Helper para o worker (Python) assinar payloads. Mesma função em backend e worker."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
