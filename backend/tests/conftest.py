"""Fixtures globais dos testes do backend.

Estratégia: SQLite in-memory async para testes unitários puros do modelo
e regras de auth. Postgres real só nos integration tests da F2 em diante,
quando estivermos contra docker-compose.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import *  # noqa: F401,F403  carrega metadata


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _disable_stub_worker_in_tests(monkeypatch):
    """O stub agenda tasks asyncio que podem ficar pendentes ao fim do teste,
    gerando 'Task was destroyed but it is pending'. Desabilita por padrão;
    testes que precisam do stub habilitam explicitamente via monkeypatch.setenv()."""
    monkeypatch.setenv("STUB_WORKER_ENABLED", "false")


@pytest_asyncio.fixture
async def engine_test():
    """SQLite in-memory com StaticPool — todas as conexões compartilham a MESMA
    instância do DB (necessário para in-memory SQLite, que é per-connection)."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine_test) -> AsyncIterator[AsyncSession]:
    Session = async_sessionmaker(engine_test, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        yield s


@pytest_asyncio.fixture
async def client(engine_test) -> AsyncIterator[AsyncClient]:
    """HTTP client testando o app FastAPI com banco SQLite em memória.

    Sobrescreve get_db para usar a sessão do engine_test.
    """
    Session = async_sessionmaker(engine_test, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
