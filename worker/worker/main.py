"""Entrypoint do processo `jump-worker` — consome jobs.agent do Redis.

Pipeline:

    BRPOP jobs.agent
       │
       ▼
    parse payload (schema v3 §7.4)
       │
       ▼
    cria workspace tmp + AgentTask
       │
       ▼
    AgentRunner.run(task)   ← jump_agent_runner (Claude → Codex fallback)
       │
       ▼
    callback HMAC para POST /internal/agent-results/{run_id}
       │
       ▼
    cleanup workspace + record_job (heartbeat)

Heartbeat roda em task asyncio paralela, batendo `/internal/worker-heartbeat`
a cada `HEARTBEAT_S`.

**Não implementado em F5.6a** (registrado como débito + decisão B-α/β/γ):

- Status RUNNING intermediário entre QUEUED e DONE/FAILED — B-α (a).
- Carregamento de prompt versionado real — B-β (a), F5.6b.
- Download de `input_files` do R2 antes de invocar runner — B-γ (a), F5.6b.

**Nota sobre execução (F5.6b decidirá):** `ClaudeHeadlessRoute` invoca o
binário `claude` via `resolve_executable("claude")` do PATH do processo
Python. Se o jump-worker rodar no Windows host, o `claude` resolvido será o
do mount `/mnt/c/...` (bug do ADR 2026-05-11). Soluções candidatas para
F5.6b: (a) rodar o próprio jump-worker dentro do WSL Linux com claude
nativo no PATH; (b) injetar em `ClaudeHeadlessRoute` um executable wrapper
que invoca `wsl.exe -d Ubuntu-22.04 -- claude ...`. Ambas as alternativas
exigem decisão de produto sobre onde o processo Python vive. Testes F5.6a
mockam `AgentRunner` integralmente — essa decisão não bloqueia F5.6a.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import signal
import time
import uuid
from pathlib import Path
from typing import Any

import redis.asyncio as redis_async
import structlog

from jump_agent_runner.broker.wsl_tmux import WSLTmuxBroker
from jump_agent_runner.observer import Observer
from jump_agent_runner.providers.claude_provider import ClaudeProvider
from jump_agent_runner.providers.codex_provider import CodexProvider
from jump_agent_runner.runner import AgentRunner
from jump_agent_runner.types import AgentResult, AgentTask

from .config import get_settings
from .heartbeat import HeartbeatTask
from .http_client import WorkerHttpClient
from .prompt_builder import build_prompt

QUEUE_KEY = "jobs.agent"
DEAD_LETTER_KEY = "jobs.agent.dead"

log = structlog.get_logger("worker.main")


class AgentWorker:
    """Loop principal — BRPOP, processa, callback."""

    def __init__(
        self,
        *,
        redis: redis_async.Redis,
        http_client: WorkerHttpClient,
        runner: AgentRunner,
        heartbeat: HeartbeatTask,
    ) -> None:
        self.redis = redis
        self.http = http_client
        self.runner = runner
        self.heartbeat = heartbeat
        self._stop = asyncio.Event()
        self._current_run_id: str | None = None

    def request_stop(self) -> None:
        log.info("worker.stop_requested", current_run=self._current_run_id)
        self._stop.set()

    async def run(self) -> None:
        settings = get_settings()
        settings.workspace_root.mkdir(parents=True, exist_ok=True)
        log.info(
            "worker.started",
            worker_id=settings.worker_id,
            redis_url=settings.redis_url,
            backend_url=settings.backend_url,
            workspace_root=str(settings.workspace_root),
        )

        self.heartbeat.start()
        try:
            while not self._stop.is_set():
                raw = await self._brpop_safe()
                if raw is None:
                    continue
                _key, payload_raw = raw
                payload = self._parse_payload(payload_raw)
                if payload is None:
                    continue
                await self._process_job(payload)
        finally:
            log.info("worker.stopping")
            await self.heartbeat.stop()
            await self.http.aclose()
            await self.redis.aclose()
            log.info("worker.stopped")

    async def _brpop_safe(self) -> tuple[str, str] | None:
        settings = get_settings()
        try:
            return await self.redis.brpop(
                QUEUE_KEY, timeout=settings.brpop_timeout_s
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("brpop.failed", exc=str(exc))
            await asyncio.sleep(1)
            return None

    def _parse_payload(self, payload_raw: str) -> dict[str, Any] | None:
        try:
            return json.loads(payload_raw)
        except json.JSONDecodeError as exc:
            log.error("job.invalid_json", exc=str(exc))
            # Job corrompido — guarda na dead-letter, não bloqueia o loop
            asyncio.create_task(self.redis.rpush(DEAD_LETTER_KEY, payload_raw))
            return None

    async def _process_job(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        run_id = payload.get("run_id") or f"unknown-{uuid.uuid4().hex[:8]}"
        task_type = payload.get("task_type") or "proposal_extraction"
        self._current_run_id = run_id

        workspace = settings.workspace_root / run_id
        workspace.mkdir(parents=True, exist_ok=True)
        output_filename = payload.get("output_path_hint") or "out.json"
        output_path = workspace / output_filename

        try:
            prompt = build_prompt(task_type, payload.get("context"))
        except ValueError as exc:
            log.error("job.unknown_task_type", run_id=run_id, exc=str(exc))
            await self._report_failure(run_id, str(exc), worker_id=settings.worker_id)
            self.heartbeat.record_job(success=False)
            self._current_run_id = None
            return

        input_files = payload.get("input_files") or []
        if input_files:
            # B-γ — F5.6a não baixa input do R2. Smoke real entra em F5.6b.
            log.info("job.input_files_skipped_f56a", run_id=run_id, n=len(input_files))

        task = AgentTask(
            run_id=run_id,
            prompt=prompt,
            output_path=output_path,
            schema_hint=payload.get("schema_hint"),
            workspace=workspace,
            timeout_hard_s=int(payload.get("timeout_hard_s") or 600),
            heartbeat_s=int(payload.get("heartbeat_s") or 30),
            metadata={"task_type": task_type, "worker_id": settings.worker_id},
        )

        log.info(
            "job.starting",
            run_id=run_id,
            task_type=task_type,
            timeout_hard_s=task.timeout_hard_s,
        )
        started = time.monotonic()
        result = await self.runner.run(task)
        elapsed = time.monotonic() - started

        callback_payload = self._build_callback_payload(
            result, worker_id=settings.worker_id
        )
        try:
            resp = await self.http.post_signed(
                f"/internal/agent-results/{run_id}", callback_payload
            )
            log.info(
                "job.completed",
                run_id=run_id,
                success=result.success,
                duration_s=round(elapsed, 1),
                callback_status=resp.status_code,
            )
        except Exception as exc:  # noqa: BLE001
            # Tenacity esgotou. Backend não recebeu — guarda na dead-letter.
            log.error("callback.failed_persistent", run_id=run_id, exc=str(exc))
            await self._push_dead_letter(
                run_id=run_id,
                original_payload=payload,
                result_attempted=callback_payload,
                reason="callback_failed",
                exc=str(exc),
            )

        self.heartbeat.record_job(success=result.success)
        self._cleanup_workspace(workspace, keep=not result.success, run_id=run_id)
        self._current_run_id = None

    async def _push_dead_letter(self, **fields: Any) -> None:
        await self.redis.rpush(DEAD_LETTER_KEY, json.dumps(fields, default=str))

    async def _report_failure(
        self, run_id: str, detail: str, *, worker_id: str
    ) -> None:
        payload = {
            "success": False,
            "engine_used": None,
            "route_used": None,
            "artifact_data": None,
            "artifact_path": None,
            "attempts": [],
            "duration_s": 0.0,
            "failure_reason": "execution_error",
            "failure_detail": detail,
            "worker_id": worker_id,
        }
        try:
            await self.http.post_signed(
                f"/internal/agent-results/{run_id}", payload
            )
        except Exception as exc:  # noqa: BLE001
            log.error("failure_callback.failed", run_id=run_id, exc=str(exc))
            await self._push_dead_letter(
                run_id=run_id,
                reason="failure_callback_failed",
                detail=detail,
                exc=str(exc),
            )

    @staticmethod
    def _build_callback_payload(result: AgentResult, *, worker_id: str) -> dict[str, Any]:
        return {
            "success": result.success,
            "engine_used": result.engine_used.value if result.engine_used else None,
            "route_used": result.route_used.value if result.route_used else None,
            "artifact_data": result.artifact_data,
            "artifact_path": str(result.artifact_path) if result.artifact_path else None,
            "attempts": [
                {
                    "engine": att.engine.value,
                    "route": att.route.value,
                    "success": att.success,
                    "failure_reason": att.failure_reason.value if att.failure_reason else None,
                    "duration_s": round(att.duration_s, 2),
                    "sentinel_observed": att.sentinel_observed,
                    "artifact_written": att.artifact_written,
                    "notes": att.notes,
                }
                for att in result.attempts
            ],
            "duration_s": round(result.duration_s, 2),
            "failure_reason": result.failure_reason.value if result.failure_reason else None,
            "failure_detail": result.failure_detail,
            "worker_id": worker_id,
        }

    @staticmethod
    def _cleanup_workspace(path: Path, *, keep: bool, run_id: str) -> None:
        if keep:
            log.info("workspace.preserved_for_debug", run_id=run_id, path=str(path))
            return
        try:
            shutil.rmtree(path, ignore_errors=False)
        except OSError as exc:
            log.warning("workspace.cleanup_failed", run_id=run_id, exc=str(exc))


async def _amain() -> int:
    settings = get_settings()
    _configure_logging()

    observer = Observer()
    broker = WSLTmuxBroker(observer=observer)
    primary = ClaudeProvider(observer=observer, broker_backend=broker)
    secondary = CodexProvider(observer=observer, broker_backend=broker)
    runner = AgentRunner(primary=primary, secondary=secondary, observer=observer)

    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    http_client = WorkerHttpClient()
    heartbeat = HeartbeatTask(http_client)

    worker = AgentWorker(
        redis=redis,
        http_client=http_client,
        runner=runner,
        heartbeat=heartbeat,
    )

    _install_signal_handlers(worker)

    await worker.run()
    return 0


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


def _install_signal_handlers(worker: AgentWorker) -> None:
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            # Windows: add_signal_handler não funciona em ProactorEventLoop.
            # Fallback síncrono: KeyboardInterrupt via Ctrl+C cobre o caso.
            signal.signal(sig, lambda *_args: worker.request_stop())


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
