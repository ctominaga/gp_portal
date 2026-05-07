"""Endpoint SSE /events/stream — apenas para o usuário autenticado."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models import User
from app.notifications.sse import subscribe

router = APIRouter(tags=["events"])


@router.get("/events/stream")
async def stream_events(user: User = Depends(get_current_user)) -> StreamingResponse:
    """Conexão SSE long-lived. Cada chamada cria uma fila dedicada para o usuário.

    O cliente JS deve conectar com `EventSource("/events/stream")` ou via
    fetch + ReadableStream se precisar passar Authorization no header.
    """
    return StreamingResponse(
        subscribe(user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Cloudflare/nginx não bufferizar
        },
    )
