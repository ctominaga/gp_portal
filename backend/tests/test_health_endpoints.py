"""F5.9a — healthchecks /health, /health/db, /health/redis.

Os 3 probes têm responsabilidades distintas (vide docstring de
app/api/v1/health.py). Aqui validamos:

  - /health é liveness puro: sempre 200, NÃO depende de DB/Redis.
  - /health/db responde 200 quando o engine SQLite/Postgres está OK,
    e 503 quando dispatcher falha (mock).
  - /health/redis responde 503 quando o lifespan não foi triggado
    (caso do ASGITransport dos testes — app.state.redis = None).

CORS prod guard tem seu próprio teste em test_settings_cors_guard.py.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.asyncio
async def test_liveness_sempre_200(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_db_check_200_quando_db_ok(
    client: AsyncClient, engine_test, monkeypatch
) -> None:
    """O healthcheck usa `engine` global (app.db.session) que aponta para
    Postgres prod. Em testes, redireciona para o engine SQLite do conftest."""
    from app.api.v1 import health as health_module

    monkeypatch.setattr(health_module, "engine", engine_test)

    r = await client.get("/health/db")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_db_check_503_quando_db_falha(
    client: AsyncClient, monkeypatch
) -> None:
    """Substitui o engine inteiro por um stub que estoura em connect();
    espera 503 com detail."""
    from app.api.v1 import health as health_module

    class _BoomConn:
        async def __aenter__(self):
            raise RuntimeError("simulated db outage")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _BoomEngine:
        def connect(self):
            return _BoomConn()

    monkeypatch.setattr(health_module, "engine", _BoomEngine())

    r = await client.get("/health/db")
    assert r.status_code == 503, r.text
    body = r.json()
    assert body["status"] == "down"
    assert "simulated db outage" in body["detail"]


@pytest.mark.asyncio
async def test_redis_check_503_sem_lifespan(client: AsyncClient) -> None:
    """Em testes (ASGITransport sem lifespan), app.state.redis não existe;
    o handler responde 503 — mesmo comportamento de produção se o cliente
    Redis tiver crashado."""
    r = await client.get("/health/redis")
    assert r.status_code == 503, r.text
    body = r.json()
    assert body["status"] == "down"
    assert "redis" in body["detail"].lower()


@pytest.mark.asyncio
async def test_full_check_agrega_componentes(
    client: AsyncClient, engine_test, monkeypatch
) -> None:
    """/health/full sempre retorna 200 (informativo). DB ok (engine SQLite
    do conftest) mas Redis ausente — agregado fica 'degraded'."""
    from app.api.v1 import health as health_module

    monkeypatch.setattr(health_module, "engine", engine_test)

    r = await client.get("/health/full")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["db"] == "ok"
    assert body["redis"] == "down"
    assert body["status"] == "degraded"
