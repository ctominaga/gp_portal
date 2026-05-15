from contextlib import asynccontextmanager
from typing import Literal

import redis.asyncio as redis_async
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from app.api.internal.agent_results import router as internal_results_router
from app.api.internal.heartbeats import router as internal_heartbeats_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.auth import router as auth_router
from app.api.v1.baselines import router as baselines_router
from app.api.v1.client_portal import router as client_router
from app.api.v1.events import router as events_router
from app.api.v1.files import router as files_router
from app.api.v1.me import router as me_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.operator import router as operator_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.projects import router as projects_router
from app.api.v1.reports import router as reports_router
from app.api.v1.scope_changes import router as scope_changes_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, new_request_id, request_id_ctx
from app.db.session import engine

settings = get_settings()
configure_logging()
log = get_logger("app")

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("app.startup", environment=settings.environment, version=settings.app_version)
    app.state.redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await engine.dispose()
        log.info("app.shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or new_request_id()
    request_id_ctx.set(rid)
    log.info("http.request", method=request.method, path=request.url.path)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    log.info("http.response", method=request.method, path=request.url.path, status=response.status_code)
    return response


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    db: Literal["ok", "down"]
    redis: Literal["ok", "down"]
    version: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    db_status: Literal["ok", "down"] = "ok"
    redis_status: Literal["ok", "down"] = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("health.db_down", error=str(exc))
        db_status = "down"

    try:
        await app.state.redis.ping()
    except Exception as exc:
        log.warning("health.redis_down", error=str(exc))
        redis_status = "down"

    overall: Literal["ok", "degraded"] = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=overall, db=db_status, redis=redis_status, version=settings.app_version)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(baselines_router)
app.include_router(reports_router)
app.include_router(approvals_router)
app.include_router(scope_changes_router)
app.include_router(client_router)
app.include_router(portfolio_router)
app.include_router(notifications_router)
app.include_router(files_router)
app.include_router(me_router)
app.include_router(operator_router)
app.include_router(events_router)
app.include_router(internal_results_router)
app.include_router(internal_heartbeats_router)
