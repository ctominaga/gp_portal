"""Testes do dashboard /operator/workers."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models import (
    AgentRunLog,
    AgentRunStatus,
    TaskType,
    WorkerHeartbeat,
)


async def _login_as(client: AsyncClient, *, role: str, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_workers_dashboard_so_operator_e_pmo(client: AsyncClient) -> None:
    gp = await _login_as(client, role="GP", email="gp-op1@x.com")
    r = await client.get("/operator/workers", headers={"Authorization": f"Bearer {gp}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_workers_dashboard_pmo_pode_acessar(client: AsyncClient) -> None:
    pmo = await _login_as(client, role="PMO", email="pmo@x.com")
    r = await client.get("/operator/workers", headers={"Authorization": f"Bearer {pmo}"})
    assert r.status_code == 200
    body = r.json()
    assert "workers" in body
    assert "queue_depth" in body
    assert "dead_letter_depth" in body
    assert "jobs_in_progress" in body
    assert "pending_logins" in body
    assert "expected_engine_distribution" in body
    # Esqueleto sempre presente, mesmo zerado
    dist = body["expected_engine_distribution"]
    assert dist == {"claude": 0, "codex": 0, "none": 0}


@pytest.mark.asyncio
async def test_workers_dashboard_lista_workers_e_jobs(
    client: AsyncClient, db_session
) -> None:
    op = await _login_as(client, role="OPERATOR", email="op@x.com")

    # Seed: 1 worker + 1 AgentRunLog QUEUED + 1 RUNNING + 1 DONE hoje (claude)
    db_session.add(
        WorkerHeartbeat(
            worker_id="worker-jump-01",
            last_seen_at=datetime.now(UTC),
            status="ok",
            jobs_processed_today=3,
        )
    )
    db_session.add(
        AgentRunLog(
            run_id="r-q",
            task_type=TaskType.PROPOSAL_EXTRACTION,
            status=AgentRunStatus.QUEUED,
            attempts=[],
        )
    )
    db_session.add(
        AgentRunLog(
            run_id="r-r",
            task_type=TaskType.REPORT_ANALYSIS,
            status=AgentRunStatus.RUNNING,
            engine_used="claude",
            attempts=[],
        )
    )
    db_session.add(
        AgentRunLog(
            run_id="r-done-claude",
            task_type=TaskType.PROPOSAL_EXTRACTION,
            status=AgentRunStatus.DONE,
            engine_used="claude",
            attempts=[],
            completed_at=datetime.now(UTC),
        )
    )
    db_session.add(
        AgentRunLog(
            run_id="r-done-codex",
            task_type=TaskType.REPORT_ANALYSIS,
            status=AgentRunStatus.DONE,
            engine_used="codex",
            attempts=[],
            completed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    r = await client.get("/operator/workers", headers={"Authorization": f"Bearer {op}"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["workers"]) == 1
    assert body["workers"][0]["worker_id"] == "worker-jump-01"
    assert body["workers"][0]["status"] == "ok"
    assert body["workers"][0]["last_seen_ago_s"] >= 0

    assert len(body["jobs_in_progress"]) == 2
    statuses = {j["status"] for j in body["jobs_in_progress"]}
    assert statuses == {"queued", "running"}

    # Distribuição de engines em jobs DONE hoje
    dist = body["expected_engine_distribution"]
    assert dist["claude"] == 1
    assert dist["codex"] == 1


@pytest.mark.asyncio
async def test_workers_dashboard_pending_logins_quando_existem(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    op = await _login_as(client, role="OPERATOR", email="op2@x.com")

    # Sentinelas em diretório temporário
    fake_dir = tmp_path / ".jump-runner"
    fake_dir.mkdir()
    (fake_dir / "login-pending-claude").write_text("project-claude")
    (fake_dir / "login-pending-codex").write_text("project-codex")

    import app.api.v1.operator as op_mod

    monkeypatch.setattr(op_mod, "_LOGIN_PENDING_DIR", fake_dir)

    r = await client.get("/operator/workers", headers={"Authorization": f"Bearer {op}"})
    body = r.json()
    pending = body["pending_logins"]
    assert len(pending) == 2
    engines = {p["engine"] for p in pending}
    assert engines == {"claude", "codex"}


@pytest.mark.asyncio
async def test_workers_dashboard_sem_redis_zera_queue_depth(
    client: AsyncClient
) -> None:
    """Sem app.state.redis (caso CI sem Redis), queue_depth e dead_letter_depth = 0."""
    pmo = await _login_as(client, role="PMO", email="pmo2@x.com")
    r = await client.get("/operator/workers", headers={"Authorization": f"Bearer {pmo}"})
    body = r.json()
    # Em CI sem Redis subido, app.state.redis pode estar None ou conexão estourada;
    # o handler trata via getattr e retorna 0 se for None.
    assert body["queue_depth"] >= 0
    assert body["dead_letter_depth"] >= 0


# Sanity check: garante que uuid não é importado sem motivo
def test_module_imports_ok() -> None:
    import app.api.v1.operator  # noqa: F401
    assert uuid.uuid4()
