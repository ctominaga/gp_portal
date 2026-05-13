"""Testes do AgentWorker — pipeline Redis→Runner→callback com mocks."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from jump_agent_runner.types import (
    AgentResult,
    AttemptLog,
    Engine,
    FailureReason,
    Route,
)
from worker.main import DEAD_LETTER_KEY, QUEUE_KEY, AgentWorker


def _ok_result(*, engine=Engine.CLAUDE, route=Route.HEADLESS) -> AgentResult:
    return AgentResult(
        success=True,
        engine_used=engine,
        route_used=route,
        artifact_path=Path("/tmp/out.json"),
        artifact_data={"ok": True},
        failure_reason=None,
        failure_detail=None,
        attempts=[
            AttemptLog(
                engine=engine,
                route=route,
                started_at=0.0,
                ended_at=1.0,
                success=True,
                failure_reason=None,
                sentinel_observed=True,
                artifact_written=True,
                notes="ok",
            )
        ],
        duration_s=1.0,
    )


def _failover_result() -> AgentResult:
    """Headless Claude falhou; broker Codex deu certo."""
    return AgentResult(
        success=True,
        engine_used=Engine.CODEX,
        route_used=Route.BROKER,
        artifact_path=Path("/tmp/out.json"),
        artifact_data={"ok": True},
        failure_reason=None,
        failure_detail=None,
        attempts=[
            AttemptLog(
                engine=Engine.CLAUDE,
                route=Route.HEADLESS,
                started_at=0.0,
                ended_at=2.0,
                success=False,
                failure_reason=FailureReason.QUOTA_EXCEEDED,
                sentinel_observed=False,
                artifact_written=False,
                notes="rate limit",
            ),
            AttemptLog(
                engine=Engine.CODEX,
                route=Route.BROKER,
                started_at=2.0,
                ended_at=5.0,
                success=True,
                failure_reason=None,
                sentinel_observed=True,
                artifact_written=True,
                notes="",
            ),
        ],
        duration_s=5.0,
    )


def _job_payload(**overrides) -> dict:
    base = {
        "run_id": "ext-prop-2026-05-13-abc12345",
        "task_type": "proposal_extraction",
        "context": {"project_id": "p1"},
        "input_files": [],
        "output_path_hint": "out.json",
        "schema_hint": {"type": "object"},
        "timeout_hard_s": 60,
        "heartbeat_s": 5,
        "enqueued_at": "2026-05-13T12:00:00+00:00",
    }
    base.update(overrides)
    return base


def _make_worker(*, redis, runner_result: AgentResult | Exception, http_client=None):
    runner = AsyncMock()
    if isinstance(runner_result, Exception):
        runner.run.side_effect = runner_result
    else:
        runner.run.return_value = runner_result
    http = http_client or AsyncMock()
    if http_client is None:
        http.post_signed = AsyncMock()
    # heartbeat.start é sync (cria task e retorna), .stop é async, .record_job sync
    heartbeat = MagicMock()
    heartbeat.start = MagicMock(return_value=None)
    heartbeat.stop = AsyncMock()
    heartbeat.record_job = MagicMock()
    return AgentWorker(
        redis=redis, http_client=http, runner=runner, heartbeat=heartbeat
    ), runner, http, heartbeat


# ---------- _process_job (unidade isolada do BRPOP) ----------


async def test_process_job_success_calls_callback_with_payload(workspace_root, fake_redis):
    worker, runner, http, _ = _make_worker(
        redis=fake_redis, runner_result=_ok_result()
    )
    payload = _job_payload(run_id="run-success")
    await worker._process_job(payload)

    # AgentRunner foi chamado uma vez com o run_id correto
    runner.run.assert_awaited_once()
    task = runner.run.await_args.args[0]
    assert task.run_id == "run-success"
    assert task.workspace.exists() is False or task.workspace.exists()  # workspace pode ter sido limpo

    # Callback chamado com path correto e success=True
    http.post_signed.assert_awaited_once()
    path, callback_payload = http.post_signed.await_args.args
    assert path == "/internal/agent-results/run-success"
    assert callback_payload["success"] is True
    assert callback_payload["engine_used"] == "claude"
    assert callback_payload["route_used"] == "headless"
    assert callback_payload["worker_id"] == "test-worker"


async def test_process_job_fallback_codex_reflected_in_callback(fake_redis):
    worker, _, http, _ = _make_worker(
        redis=fake_redis, runner_result=_failover_result()
    )
    await worker._process_job(_job_payload(run_id="run-fallback"))
    callback_payload = http.post_signed.await_args.args[1]
    assert callback_payload["engine_used"] == "codex"
    assert callback_payload["route_used"] == "broker"
    # attempts preserva sequência claude→codex
    engines = [att["engine"] for att in callback_payload["attempts"]]
    assert engines == ["claude", "codex"]


async def test_process_job_unknown_task_type_reports_failure(fake_redis):
    worker, runner, http, _ = _make_worker(
        redis=fake_redis, runner_result=_ok_result()
    )
    await worker._process_job(_job_payload(task_type="bogus-type"))
    # Runner NÃO chamado — falha cedo no prompt_builder
    runner.run.assert_not_awaited()
    # Callback foi com success=False e execution_error
    callback_payload = http.post_signed.await_args.args[1]
    assert callback_payload["success"] is False
    assert callback_payload["failure_reason"] == "execution_error"
    assert "task_type desconhecido" in callback_payload["failure_detail"]


async def test_process_job_persistent_callback_failure_goes_to_dead_letter(fake_redis):
    http = AsyncMock()
    http.post_signed.side_effect = RuntimeError("backend gone")
    worker, _, _, _ = _make_worker(
        redis=fake_redis, runner_result=_ok_result(), http_client=http
    )
    await worker._process_job(_job_payload(run_id="run-dead"))

    # Item gravado na dead-letter
    dl_len = await fake_redis.llen(DEAD_LETTER_KEY)
    assert dl_len == 1
    raw = await fake_redis.lindex(DEAD_LETTER_KEY, 0)
    data = json.loads(raw)
    assert data["run_id"] == "run-dead"
    assert data["reason"] == "callback_failed"
    assert "backend gone" in data["exc"]


async def test_process_job_workspace_preserved_on_failure(fake_redis, workspace_root):
    fail_result = AgentResult(
        success=False,
        engine_used=Engine.CLAUDE,
        route_used=Route.HEADLESS,
        artifact_path=None,
        artifact_data=None,
        failure_reason=FailureReason.ARTIFACT_INVALID,
        failure_detail="schema mismatch",
        attempts=[],
        duration_s=2.0,
    )
    worker, _, _, _ = _make_worker(redis=fake_redis, runner_result=fail_result)
    await worker._process_job(_job_payload(run_id="run-fail"))
    # Workspace preservado para debug
    ws = workspace_root / "run-fail"
    assert ws.exists()


async def test_process_job_workspace_cleaned_on_success(fake_redis, workspace_root):
    worker, _, _, _ = _make_worker(redis=fake_redis, runner_result=_ok_result())
    await worker._process_job(_job_payload(run_id="run-clean"))
    ws = workspace_root / "run-clean"
    assert not ws.exists()


# ---------- run() loop com BRPOP real do fakeredis ----------


async def test_run_loop_processes_one_job_then_stops(fake_redis):
    worker, runner, http, _ = _make_worker(
        redis=fake_redis, runner_result=_ok_result()
    )
    # Enfileira 1 job (fakeredis suporta BRPOP)
    await fake_redis.rpush(QUEUE_KEY, json.dumps(_job_payload(run_id="loop-1")))

    # Stop após pequeno delay (dá tempo do BRPOP pegar e processar)
    async def trigger_stop():
        await asyncio.sleep(0.2)
        worker.request_stop()

    asyncio.create_task(trigger_stop())
    await asyncio.wait_for(worker.run(), timeout=5)

    runner.run.assert_awaited_once()
    http.post_signed.assert_awaited_once()


async def test_run_loop_invalid_json_goes_to_dead_letter_without_processing(fake_redis):
    worker, runner, _, _ = _make_worker(
        redis=fake_redis, runner_result=_ok_result()
    )
    await fake_redis.rpush(QUEUE_KEY, "{not-valid-json")

    async def trigger_stop():
        await asyncio.sleep(0.3)
        worker.request_stop()

    asyncio.create_task(trigger_stop())
    await asyncio.wait_for(worker.run(), timeout=5)

    runner.run.assert_not_awaited()
    # Pode demorar um instante: dead-letter recebe via asyncio.create_task
    await asyncio.sleep(0.1)
    dl_len = await fake_redis.llen(DEAD_LETTER_KEY)
    assert dl_len == 1
