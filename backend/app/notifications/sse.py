"""Server-Sent Events para notificações em tempo real (F3.3, F4).

Cada usuário tem uma fila in-memory. emit_to_user(user_id, event) envia
para todas as conexões ativas daquele usuário. Em produção com múltiplas
réplicas Railway, isso seria um Redis pub/sub — mas para o piloto
single-replica é suficiente.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Any

# user_id (str) → set de Queue[str]
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


async def subscribe(user_id: uuid.UUID) -> AsyncIterator[str]:
    """Async iterator que produz frames SSE em formato `event: ... \\ndata: ...\\n\\n`."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[str(user_id)].add(q)
    # Saudação imediata para o cliente saber que conectou
    yield _sse_frame("connected", {"ts": _now_iso()})
    try:
        while True:
            try:
                # Heartbeat a cada 25s para manter a conexão viva e evitar
                # timeouts de proxies como Cloudflare/Railway (default ~30s).
                msg = await asyncio.wait_for(q.get(), timeout=25)
                yield msg
            except TimeoutError:
                yield _sse_frame("ping", {"ts": _now_iso()})
    finally:
        _subscribers[str(user_id)].discard(q)


def _sse_frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def emit_to_user(user_id: uuid.UUID | str, event: str, payload: dict[str, Any]) -> None:
    """Envia evento para todas as conexões ativas do usuário."""
    full = {**payload, "ts": _now_iso()}
    frame = _sse_frame(event, full)
    for q in _subscribers.get(str(user_id), set()):
        try:
            q.put_nowait(frame)
        except asyncio.QueueFull:
            # cliente lento — drop do mais antigo e tenta de novo
            try:
                q.get_nowait()
                q.put_nowait(frame)
            except Exception:  # noqa: BLE001
                pass


def emit_to_users(user_ids: list[uuid.UUID | str], event: str, payload: dict[str, Any]) -> None:
    for uid in user_ids:
        emit_to_user(uid, event, payload)


def active_subscribers_count() -> int:
    return sum(len(qs) for qs in _subscribers.values())
