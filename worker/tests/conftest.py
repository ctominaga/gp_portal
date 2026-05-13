"""Fixtures compartilhadas dos testes do worker."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from worker.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _worker_env(monkeypatch, tmp_path):
    """Injeta env vars obrigatorias do Settings para qualquer teste."""
    monkeypatch.setenv("WORKER_SHARED_SECRET", "test-shared-secret-32-chars-min!!")
    monkeypatch.setenv("WORKER_HMAC_KEY", "test-hmac-key-32-chars-min!!!!!!!!")
    monkeypatch.setenv("WORKER_ID", "test-worker")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("BACKEND_URL", "http://test-backend.invalid")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("HEARTBEAT_S", "1")
    monkeypatch.setenv("BRPOP_TIMEOUT_S", "1")
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def workspace_root(tmp_path) -> Path:
    p = tmp_path / "workspaces"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
async def fake_redis():
    """Redis async fake. fakeredis 2.x suporta BRPOP/RPUSH em aioredis."""
    from fakeredis import aioredis as fakeaioredis

    redis = fakeaioredis.FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


# Marker para tests que ainda nao foram implementados (smoke real F5.6b)
def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    pending = pytest.mark.skip(reason="Smoke real do agente — F5.6b")
    for item in items:
        if "requires_claude_cli" in item.keywords:
            item.add_marker(pending)


# NOTA: não sobrescrever a fixture event_loop — pytest-asyncio 0.24+ gerencia
# automaticamente via asyncio_default_fixture_loop_scope=function (pyproject).
