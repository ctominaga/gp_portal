"""Testes do callback `/internal/agent-results/{run_id}` com autenticação HMAC.

Cobre os 5 cenários explícitos pedidos pelo product owner:
1. timestamp velho (>5min): 401
2. timestamp futuro (>30s à frente): 401
3. assinatura inválida: 401
4. token sem assinatura (falta header): 401
5. replay do mesmo run_id com payload diferente: idempotente — não 500,
   não sobrescreve estado consolidado, retorna duplicated=True.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.worker_auth import sign_worker_payload
from app.models import (
    AgentRunLog,
    AgentRunStatus,
    Project,
    Role,
    TaskType,
    User,
)

_TOKEN = "ci-worker-token"
_HMAC = "ci-worker-hmac-key-test"


@pytest.fixture(autouse=True)
def _isolated_secrets(monkeypatch: pytest.MonkeyPatch):
    from app.core.config import get_settings as _gs

    monkeypatch.setenv("WORKER_SHARED_SECRET", _TOKEN)
    monkeypatch.setenv("WORKER_HMAC_KEY", _HMAC)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret")
    _gs.cache_clear()
    yield
    _gs.cache_clear()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _headers(body_bytes: bytes, *, ts: str | None = None, signature: str | None = None) -> dict[str, str]:
    return {
        "X-Worker-Token": _TOKEN,
        "X-Worker-Timestamp": ts or _now_iso(),
        "X-Worker-Signature": signature or sign_worker_payload(body_bytes, secret=_HMAC),
        "Content-Type": "application/json",
    }


async def _seed_run(db, *, run_id: str, project_id: uuid.UUID | None = None,
                    status: AgentRunStatus = AgentRunStatus.QUEUED) -> AgentRunLog:
    log = AgentRunLog(
        run_id=run_id,
        task_type=TaskType.PROPOSAL_EXTRACTION,
        project_id=project_id,
        status=status,
        attempts=[],
    )
    db.add(log)
    await db.commit()
    return log


async def _seed_project(db) -> uuid.UUID:
    gp = User(name="GP", email=f"gp-{uuid.uuid4().hex[:6]}@x.com", password_hash="x", role=Role.GP)
    db.add(gp)
    await db.flush()
    p = Project(name="P", client_name="C", gp_user_id=gp.id)
    db.add(p)
    await db.commit()
    return p.id


# ---------- 1) timestamp velho ----------


@pytest.mark.asyncio
async def test_callback_timestamp_velho_401(client: AsyncClient, db_session) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-old", project_id=pid)

    body = json.dumps({"success": True, "engine_used": "claude"}).encode()
    old_ts = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    r = await client.post(
        "/internal/agent-results/run-old",
        content=body,
        headers=_headers(body, ts=old_ts),
    )
    assert r.status_code == 401, r.text
    assert "velho" in r.text.lower() or "skew" in r.text.lower()


# ---------- 2) timestamp futuro ----------


@pytest.mark.asyncio
async def test_callback_timestamp_futuro_401(client: AsyncClient, db_session) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-fut", project_id=pid)

    body = json.dumps({"success": True}).encode()
    future = (datetime.now(UTC) + timedelta(seconds=120)).isoformat()
    r = await client.post(
        "/internal/agent-results/run-fut",
        content=body,
        headers=_headers(body, ts=future),
    )
    assert r.status_code == 401
    assert "futuro" in r.text.lower() or "skew" in r.text.lower()


# ---------- 3) assinatura inválida ----------


@pytest.mark.asyncio
async def test_callback_signature_invalida_401(client: AsyncClient, db_session) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-bad-sig", project_id=pid)

    body = json.dumps({"success": True}).encode()
    bogus = "0" * 64
    r = await client.post(
        "/internal/agent-results/run-bad-sig",
        content=body,
        headers=_headers(body, signature=bogus),
    )
    assert r.status_code == 401
    assert "assinatura" in r.text.lower() or "invalid" in r.text.lower()


# ---------- 4) token sem assinatura (header faltando) ----------


@pytest.mark.asyncio
async def test_callback_sem_signature_header_401(
    client: AsyncClient, db_session
) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-no-sig", project_id=pid)

    body = json.dumps({"success": True}).encode()
    r = await client.post(
        "/internal/agent-results/run-no-sig",
        content=body,
        headers={
            "X-Worker-Token": _TOKEN,
            "X-Worker-Timestamp": _now_iso(),
            # sem X-Worker-Signature
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 401
    assert "faltando" in r.text.lower() or "missing" in r.text.lower()


# ---------- 5) replay com payload diferente é idempotente ----------


@pytest.mark.asyncio
async def test_callback_replay_payload_diferente_e_idempotente(
    client: AsyncClient, db_session
) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-replay", project_id=pid)

    # Primeira chamada: success=True
    body1 = json.dumps({
        "success": True,
        "engine_used": "claude",
        "route_used": "headless",
        "duration_s": 12.5,
        "worker_id": "worker-1",
        "attempts": [{"engine": "claude", "route": "headless", "success": True}],
    }).encode()
    r1 = await client.post(
        "/internal/agent-results/run-replay",
        content=body1,
        headers=_headers(body1),
    )
    assert r1.status_code == 200, r1.text
    body_json = r1.json()
    assert body_json["accepted"] is True
    assert body_json["duplicated"] is False
    assert body_json["status"] == "done"

    # Replay com payload DIFERENTE (success=False, outro engine)
    body2 = json.dumps({
        "success": False,
        "engine_used": "codex",
        "failure_reason": "quota_exceeded",
        "worker_id": "worker-2",
    }).encode()
    r2 = await client.post(
        "/internal/agent-results/run-replay",
        content=body2,
        headers=_headers(body2),
    )

    # Deve aceitar o request (não 500), mas marcar duplicated=True
    # e NÃO sobrescrever o estado.
    assert r2.status_code == 200, r2.text
    ack = r2.json()
    assert ack["accepted"] is False
    assert ack["duplicated"] is True
    assert ack["status"] == "done"  # mantém o original

    # Confirma no DB que o estado é o do PRIMEIRO callback
    log = (
        await db_session.execute(
            select(AgentRunLog).where(AgentRunLog.run_id == "run-replay")
        )
    ).scalar_one()
    assert log.status == AgentRunStatus.DONE
    assert log.engine_used == "claude"  # não virou codex
    assert log.failure_reason is None
    assert log.worker_id == "worker-1"


# ---------- happy path para sanity ----------


@pytest.mark.asyncio
async def test_callback_success_atualiza_log(client: AsyncClient, db_session) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-happy", project_id=pid)

    body = json.dumps({
        "success": True,
        "engine_used": "claude",
        "route_used": "headless",
        "duration_s": 4.2,
        "worker_id": "w1",
        "artifact_path": "/tmp/out.json",
        "artifact_data": {"ok": True},
        "attempts": [{"engine": "claude", "route": "headless", "success": True}],
    }).encode()
    r = await client.post(
        "/internal/agent-results/run-happy",
        content=body,
        headers=_headers(body),
    )
    assert r.status_code == 200

    log = (
        await db_session.execute(select(AgentRunLog).where(AgentRunLog.run_id == "run-happy"))
    ).scalar_one()
    assert log.status == AgentRunStatus.DONE
    assert log.engine_used == "claude"
    assert log.duration_s == 4.2
    assert log.completed_at is not None


@pytest.mark.asyncio
async def test_callback_failure_grava_failure_reason(client: AsyncClient, db_session) -> None:
    pid = await _seed_project(db_session)
    await _seed_run(db_session, run_id="run-fail", project_id=pid)

    body = json.dumps({
        "success": False,
        "failure_reason": "sentinel_not_observed",
        "failure_detail": "claude não retornou em 600s",
        "attempts": [{"engine": "claude", "route": "headless", "success": False}],
    }).encode()
    r = await client.post(
        "/internal/agent-results/run-fail",
        content=body,
        headers=_headers(body),
    )
    assert r.status_code == 200
    log = (
        await db_session.execute(select(AgentRunLog).where(AgentRunLog.run_id == "run-fail"))
    ).scalar_one()
    assert log.status == AgentRunStatus.FAILED
    assert log.failure_reason == "sentinel_not_observed"


@pytest.mark.asyncio
async def test_callback_run_id_inexistente_404(
    client: AsyncClient, db_session
) -> None:
    body = json.dumps({"success": True}).encode()
    r = await client.post(
        "/internal/agent-results/inexistente",
        content=body,
        headers=_headers(body),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_worker_heartbeat_aceita_e_atualiza(client: AsyncClient, db_session) -> None:
    body = json.dumps({
        "worker_id": "worker-jump-01",
        "status": "ok",
        "jobs_processed_today": 5,
        "sessions_status": {"claude": "logged_in"},
    }).encode()
    r = await client.post(
        "/internal/worker-heartbeat",
        content=body,
        headers=_headers(body),
    )
    assert r.status_code == 200, r.text
    assert r.json()["ack"] == "ok"

    # Segundo heartbeat upserta
    body2 = json.dumps({"worker_id": "worker-jump-01", "status": "degraded"}).encode()
    r2 = await client.post(
        "/internal/worker-heartbeat",
        content=body2,
        headers=_headers(body2),
    )
    assert r2.status_code == 200
