"""Testes do _BaseProvider e AgentRunner — fallback orquestrado.

Estratégia: usar fakes determinísticos de AgentRoute para exercitar o
fluxo headless → broker dentro do provider e primary → secondary no runner.
Sem subprocess, sem WSL — puro async lógica.
"""
from __future__ import annotations

import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.providers._base import _BaseProvider
from jump_agent_runner.runner import AgentRunner
from jump_agent_runner.types import (
    AgentResult,
    AgentTask,
    AttemptLog,
    Engine,
    FailureReason,
    Route,
)


@pytest.fixture
def observer(tmp_path: Path) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=io.StringIO())


def _task(tmp_path: Path) -> AgentTask:
    ws = tmp_path / "ws"
    ws.mkdir()
    return AgentTask(
        run_id="r-1",
        prompt="x",
        output_path=ws / "out.json",
        schema_hint=None,
        workspace=ws,
        timeout_hard_s=10,
        heartbeat_s=2,
    )


@dataclass
class FakeRoute:
    """AgentRoute fake configurável: comportamento controlado por callable."""

    engine: Engine
    route: Route
    is_available_fn: Callable[[], tuple[bool, FailureReason | None]]
    execute_fn: Callable[[AgentTask], AttemptLog]
    on_execute_side_effect: Callable[[AgentTask], None] | None = field(default=None)

    async def is_available(self) -> tuple[bool, FailureReason | None]:
        return self.is_available_fn()

    async def execute(self, task: AgentTask) -> AttemptLog:
        if self.on_execute_side_effect:
            self.on_execute_side_effect(task)
        return self.execute_fn(task)


def _success_log(engine: Engine, route: Route) -> AttemptLog:
    now = time.monotonic()
    return AttemptLog(
        engine=engine,
        route=route,
        started_at=now,
        ended_at=now + 0.1,
        success=True,
        failure_reason=None,
        sentinel_observed=True,
        artifact_written=True,
        notes="ok",
    )


def _fail_log(engine: Engine, route: Route, reason: FailureReason) -> AttemptLog:
    now = time.monotonic()
    return AttemptLog(
        engine=engine,
        route=route,
        started_at=now,
        ended_at=now + 0.1,
        success=False,
        failure_reason=reason,
        sentinel_observed=False,
        artifact_written=False,
        notes=f"fake fail {reason.value}",
    )


# ---------- _BaseProvider ----------


@pytest.mark.asyncio
async def test_provider_devolve_sucesso_quando_headless_funciona(
    tmp_path: Path, observer: Observer
) -> None:
    task = _task(tmp_path)

    def grava_output(t: AgentTask) -> None:
        t.output_path.write_text(json.dumps({"ok": True}), encoding="utf-8")

    headless = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.HEADLESS,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: _success_log(Engine.CLAUDE, Route.HEADLESS),
        on_execute_side_effect=grava_output,
    )
    broker = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.BROKER,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: _success_log(Engine.CLAUDE, Route.BROKER),
    )

    provider = _BaseProvider(
        engine=Engine.CLAUDE, headless=headless, broker=broker, observer=observer
    )
    result: AgentResult = await provider.run(task)

    assert result.success is True
    assert result.engine_used == Engine.CLAUDE
    assert result.route_used == Route.HEADLESS
    assert result.artifact_data == {"ok": True}
    assert len(result.attempts) == 1


@pytest.mark.asyncio
async def test_provider_faz_fallback_para_broker_em_login_required(
    tmp_path: Path, observer: Observer
) -> None:
    task = _task(tmp_path)

    def grava_via_broker(t: AgentTask) -> None:
        t.output_path.write_text(json.dumps({"via": "broker"}), encoding="utf-8")

    headless = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.HEADLESS,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: _fail_log(Engine.CLAUDE, Route.HEADLESS, FailureReason.LOGIN_REQUIRED),
    )
    broker = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.BROKER,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: _success_log(Engine.CLAUDE, Route.BROKER),
        on_execute_side_effect=grava_via_broker,
    )

    provider = _BaseProvider(
        engine=Engine.CLAUDE, headless=headless, broker=broker, observer=observer
    )
    result = await provider.run(task)

    assert result.success is True
    assert result.route_used == Route.BROKER
    assert len(result.attempts) == 2
    assert result.attempts[0].failure_reason == FailureReason.LOGIN_REQUIRED
    assert result.artifact_data == {"via": "broker"}


@pytest.mark.asyncio
async def test_provider_nao_faz_fallback_para_broker_em_quota_exceeded(
    tmp_path: Path, observer: Observer
) -> None:
    """QUOTA_EXCEEDED não está em HEADLESS_TO_BROKER_REASONS — deve devolver
    direto a falha do headless (e o runner externo decide pelo fallback de engine)."""
    task = _task(tmp_path)
    headless = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.HEADLESS,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: _fail_log(Engine.CLAUDE, Route.HEADLESS, FailureReason.QUOTA_EXCEEDED),
    )
    broker = FakeRoute(
        engine=Engine.CLAUDE,
        route=Route.BROKER,
        is_available_fn=lambda: (True, None),
        execute_fn=lambda t: pytest.fail("broker não deveria ser chamado"),  # type: ignore
    )
    provider = _BaseProvider(
        engine=Engine.CLAUDE, headless=headless, broker=broker, observer=observer
    )
    result = await provider.run(task)

    assert result.success is False
    assert result.failure_reason == FailureReason.QUOTA_EXCEEDED
    assert len(result.attempts) == 1


# ---------- AgentRunner ----------


@pytest.mark.asyncio
async def test_runner_devolve_sucesso_quando_primary_funciona(
    tmp_path: Path, observer: Observer
) -> None:
    task = _task(tmp_path)
    task.output_path.write_text(json.dumps({"ok": True}), encoding="utf-8")

    class StubProvider:
        def __init__(self, engine: Engine, succeed: bool, reason: FailureReason | None = None):
            self.engine = engine
            self._succeed = succeed
            self._reason = reason

        async def run(self, t: AgentTask) -> AgentResult:
            if self._succeed:
                return AgentResult(
                    success=True,
                    engine_used=self.engine,
                    route_used=Route.HEADLESS,
                    artifact_path=t.output_path,
                    artifact_data={"ok": True},
                    failure_reason=None,
                    failure_detail=None,
                    attempts=[_success_log(self.engine, Route.HEADLESS)],
                    duration_s=1.0,
                )
            return AgentResult(
                success=False,
                engine_used=self.engine,
                route_used=Route.HEADLESS,
                artifact_path=None,
                artifact_data=None,
                failure_reason=self._reason,
                failure_detail="fake",
                attempts=[_fail_log(self.engine, Route.HEADLESS, self._reason)],
                duration_s=1.0,
            )

    primary = StubProvider(Engine.CLAUDE, succeed=True)
    secondary = StubProvider(Engine.CODEX, succeed=True)
    runner = AgentRunner(primary, secondary, observer)  # type: ignore[arg-type]

    result = await runner.run(task)
    assert result.success is True
    assert result.engine_used == Engine.CLAUDE
    assert len(result.attempts) == 1


@pytest.mark.asyncio
async def test_runner_faz_fallback_engine_em_quota_exceeded(
    tmp_path: Path, observer: Observer
) -> None:
    task = _task(tmp_path)

    class StubProvider:
        def __init__(self, engine: Engine, succeed: bool, reason: FailureReason | None = None):
            self.engine = engine
            self._succeed = succeed
            self._reason = reason
            self.runs: list[AgentTask] = []

        async def run(self, t: AgentTask) -> AgentResult:
            self.runs.append(t)
            if self._succeed:
                t.output_path.write_text(json.dumps({"engine": self.engine.value}), encoding="utf-8")
                return AgentResult(
                    success=True,
                    engine_used=self.engine,
                    route_used=Route.HEADLESS,
                    artifact_path=t.output_path,
                    artifact_data={"engine": self.engine.value},
                    failure_reason=None,
                    failure_detail=None,
                    attempts=[_success_log(self.engine, Route.HEADLESS)],
                    duration_s=1.0,
                )
            return AgentResult(
                success=False,
                engine_used=self.engine,
                route_used=Route.HEADLESS,
                artifact_path=None,
                artifact_data=None,
                failure_reason=self._reason,
                failure_detail="primary failed",
                attempts=[_fail_log(self.engine, Route.HEADLESS, self._reason)],
                duration_s=1.0,
            )

    primary = StubProvider(Engine.CLAUDE, succeed=False, reason=FailureReason.QUOTA_EXCEEDED)
    secondary = StubProvider(Engine.CODEX, succeed=True)
    runner = AgentRunner(primary, secondary, observer)  # type: ignore[arg-type]

    result = await runner.run(task)

    assert result.success is True
    assert result.engine_used == Engine.CODEX
    assert len(secondary.runs) == 1
    # continuation_hint montado pelo runner deve estar presente na task secundária
    assert secondary.runs[0].continuation_hint is not None
    assert "QUOTA_EXCEEDED".lower() in secondary.runs[0].continuation_hint.lower()
    # AgentResult final deve ter as 2 tentativas combinadas
    assert len(result.attempts) == 2


@pytest.mark.asyncio
async def test_runner_nao_faz_fallback_quando_motivo_nao_qualifica(
    tmp_path: Path, observer: Observer
) -> None:
    """TIMEOUT_NO_ARTIFACT não está em PROVIDER_TO_PROVIDER_REASONS → não faz fallback de engine."""
    task = _task(tmp_path)

    class StubProvider:
        def __init__(self, engine: Engine, succeed: bool, reason: FailureReason | None = None):
            self.engine = engine
            self._succeed = succeed
            self._reason = reason
            self.runs = 0

        async def run(self, t: AgentTask) -> AgentResult:
            self.runs += 1
            return AgentResult(
                success=self._succeed,
                engine_used=self.engine,
                route_used=Route.HEADLESS,
                artifact_path=None,
                artifact_data=None,
                failure_reason=self._reason,
                failure_detail="x",
                attempts=[_fail_log(self.engine, Route.HEADLESS, self._reason)] if not self._succeed else [],
                duration_s=1.0,
            )

    primary = StubProvider(Engine.CLAUDE, succeed=False, reason=FailureReason.TIMEOUT_NO_ARTIFACT)
    secondary = StubProvider(Engine.CODEX, succeed=True)
    runner = AgentRunner(primary, secondary, observer)  # type: ignore[arg-type]

    result = await runner.run(task)
    assert result.success is False
    assert result.failure_reason == FailureReason.TIMEOUT_NO_ARTIFACT
    assert secondary.runs == 0  # fallback não foi acionado
