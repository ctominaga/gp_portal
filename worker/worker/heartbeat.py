"""Heartbeat periódico — best-effort, falhas não interrompem o worker.

A task envia `POST /internal/worker-heartbeat` a cada `HEARTBEAT_S` segundos
com contadores do dia (jobs processados, jobs falhados) e status `"ok"`. Os
contadores são atualizados pelo loop principal via `record_job(success=...)`.

Falha de heartbeat é warning, não erro — backend perceberá worker morto pela
ausência de `last_seen_at` recente; loop continua processando jobs mesmo sem
heartbeat reportável.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from .config import get_settings
from .http_client import WorkerHttpClient

log = structlog.get_logger("worker.heartbeat")


class HeartbeatTask:
    def __init__(self, client: WorkerHttpClient) -> None:
        self._client = client
        self._jobs_today = 0
        self._failed_today = 0
        self._last_reset_date = datetime.now(UTC).date()
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    @property
    def jobs_processed_today(self) -> int:
        return self._jobs_today

    @property
    def jobs_failed_today(self) -> int:
        return self._failed_today

    def record_job(self, *, success: bool) -> None:
        self._roll_day_if_needed()
        self._jobs_today += 1
        if not success:
            self._failed_today += 1

    def _roll_day_if_needed(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._last_reset_date:
            self._jobs_today = 0
            self._failed_today = 0
            self._last_reset_date = today

    async def send_once(self) -> None:
        """Envia um heartbeat. Falha é logada como warning, não levantada."""
        settings = get_settings()
        self._roll_day_if_needed()
        payload = {
            "worker_id": settings.worker_id,
            "status": "ok",
            "sessions_status": {},
            "jobs_processed_today": self._jobs_today,
            "jobs_failed_today": self._failed_today,
            "metadata": {},
        }
        try:
            await self._client.post_signed("/internal/worker-heartbeat", payload)
            log.debug("heartbeat.sent", jobs=self._jobs_today, failed=self._failed_today)
        except Exception as exc:  # noqa: BLE001
            log.warning("heartbeat.failed", exc=str(exc))

    async def run(self) -> None:
        """Loop principal — heartbeat imediato + cada HEARTBEAT_S até stop."""
        settings = get_settings()
        while not self._stop.is_set():
            await self.send_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.heartbeat_s)
            except asyncio.TimeoutError:
                continue

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run(), name="worker-heartbeat")
        return self._task

    async def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=timeout_s)
            except asyncio.TimeoutError:
                log.warning("heartbeat.stop_timeout")
                self._task.cancel()
