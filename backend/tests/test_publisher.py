"""Testes do publisher de jobs Redis."""
from __future__ import annotations

import json
import uuid

import fakeredis.aioredis as fake_aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentRunStatus,
    Project,
    Role,
    TaskType,
    User,
)
from app.queue.publisher import (
    DEAD_LETTER_KEY,
    QUEUE_KEY,
    dead_letter_depth,
    enqueue_agent_job,
    make_run_id,
    queue_depth,
)


@pytest.fixture
async def redis():
    r = fake_aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


def test_make_run_id_inclui_data_e_tipo() -> None:
    run_id = make_run_id(task_type=TaskType.PROPOSAL_EXTRACTION)
    assert run_id.startswith("ext-prop-")
    assert "global" in run_id  # sem project_id


def test_make_run_id_inclui_project_short() -> None:
    pid = uuid.uuid4()
    run_id = make_run_id(task_type=TaskType.REPORT_ANALYSIS, project_id=pid)
    assert run_id.startswith("rep-ana-")
    assert str(pid)[:8] in run_id


@pytest.mark.asyncio
async def test_enqueue_cria_log_e_publica_no_redis(
    db_session: AsyncSession, redis
) -> None:
    gp = User(name="GP", email="g@x.com", password_hash="x", role=Role.GP)
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="Bradesco SAS", client_name="Bradesco", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.flush()

    log = await enqueue_agent_job(
        db=db_session,
        redis=redis,
        task_type=TaskType.PROPOSAL_EXTRACTION,
        project_id=project.id,
        input_files=[{"key": "proposals/x.pdf", "kind": "proposal"}],
        output_path_hint="out.json",
    )

    assert log.status == AgentRunStatus.QUEUED
    assert log.task_type == TaskType.PROPOSAL_EXTRACTION
    assert await queue_depth(redis) == 1
    raw = await redis.lpop(QUEUE_KEY)
    payload = json.loads(raw)
    assert payload["run_id"] == log.run_id
    assert payload["task_type"] == "proposal_extraction"
    assert payload["context"]["project_id"] == str(project.id)
    assert payload["input_files"] == [{"key": "proposals/x.pdf", "kind": "proposal"}]
    assert payload["timeout_hard_s"] == 600
    assert "enqueued_at" in payload


@pytest.mark.asyncio
async def test_enqueue_idempotente_pelo_run_id(
    db_session: AsyncSession, redis
) -> None:
    gp = User(name="GP", email="g2@x.com", password_hash="x", role=Role.GP)
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="P", client_name="C", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.flush()

    fixed_id = "ext-prop-2026-05-07-fixed"
    log1 = await enqueue_agent_job(
        db=db_session,
        redis=redis,
        task_type=TaskType.PROPOSAL_EXTRACTION,
        project_id=project.id,
        run_id=fixed_id,
    )
    log2 = await enqueue_agent_job(
        db=db_session,
        redis=redis,
        task_type=TaskType.PROPOSAL_EXTRACTION,
        project_id=project.id,
        run_id=fixed_id,  # mesmo
    )

    assert log1.run_id == log2.run_id == fixed_id
    # Apenas 1 job no Redis (segunda chamada NÃO publicou)
    assert await queue_depth(redis) == 1


@pytest.mark.asyncio
async def test_queue_depth_e_dead_letter_depth(redis) -> None:
    assert await queue_depth(redis) == 0
    assert await dead_letter_depth(redis) == 0
    await redis.rpush(QUEUE_KEY, "a", "b", "c")
    await redis.rpush(DEAD_LETTER_KEY, "x", "y")
    assert await queue_depth(redis) == 3
    assert await dead_letter_depth(redis) == 2
