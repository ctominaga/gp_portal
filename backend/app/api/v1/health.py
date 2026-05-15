"""Endpoints de healthcheck (F5.9a).

3 endpoints com propósitos distintos:

  GET /health         — LIVENESS probe. Sempre 200 enquanto o processo está
                        vivo. NÃO toca DB/Redis. Usado pelo Dockerfile
                        HEALTHCHECK e pelo Railway restart policy.
  GET /health/db      — READINESS probe do Postgres. SELECT 1. 200 se OK,
                        503 caso contrário. Útil para alarmes ops.
  GET /health/redis   — READINESS probe do Redis. PING. 200 se OK, 503 caso
                        contrário.

Por que separar: o liveness não pode falhar quando Redis cai por 5s — se
falhasse, Railway reiniciaria o container e levaria o backend junto. Cada
componente tem seu probe; o agregado (`/health/full`) é informativo, não
controla restart.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import engine

router = APIRouter(tags=["meta"])
log = get_logger("health")
_settings = get_settings()


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ComponentResponse(BaseModel):
    status: Literal["ok", "down"]
    detail: str | None = None


class FullHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
    redis: Literal["ok", "down"]
    version: str


@router.get("/health", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    """Liveness: o processo Python está respondendo. Nunca falha por causa
    de dependência externa — só falha se o ASGI loop estiver travado, e
    aí a request nem chega aqui."""
    return LivenessResponse(status="ok", version=_settings.app_version)


@router.get("/health/db")
async def db_check() -> JSONResponse:
    """Readiness: conexão Postgres + SELECT 1. 503 se qualquer parte falhar."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        log.warning("health.db_down", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "down", "detail": str(exc)},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


@router.get("/health/redis")
async def redis_check(request: Request) -> JSONResponse:
    """Readiness: Redis PING. 503 se conexão não estiver disponível ou se
    o PING falhar.

    `app.state.redis` é setado no lifespan do app. Em testes que usam
    ASGITransport sem lifespan, o atributo não existe — tratamos com
    getattr defensivo (convenção já usada em `operator.py`).
    """
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "down", "detail": "redis client not initialized"},
        )
    try:
        await redis_client.ping()
    except Exception as exc:  # noqa: BLE001
        log.warning("health.redis_down", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "down", "detail": str(exc)},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


@router.get("/health/full", response_model=FullHealthResponse)
async def full_check(request: Request) -> FullHealthResponse:
    """Agregado informativo (status 200 sempre, mas campos podem indicar
    `down`). NÃO usar como probe Kubernetes/Railway — usar /health/db e
    /health/redis individualmente.
    """
    db_status: Literal["ok", "down"] = "ok"
    redis_status: Literal["ok", "down"] = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "down"

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        redis_status = "down"
    else:
        try:
            await redis_client.ping()
        except Exception:  # noqa: BLE001
            redis_status = "down"

    overall: Literal["ok", "degraded"] = (
        "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    )
    return FullHealthResponse(
        status=overall,
        db=db_status,
        redis=redis_status,
        version=_settings.app_version,
    )


__all__ = ["router"]
