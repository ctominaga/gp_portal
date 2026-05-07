"""Smoke nos tipos públicos."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from jump_agent_runner.types import (
    AgentResult,
    AgentTask,
    AttemptLog,
    Engine,
    FailureReason,
    Route,
    ValidationResult,
)


def test_enum_str_values_estaveis() -> None:
    assert Engine.CLAUDE.value == "claude"
    assert Engine.CODEX.value == "codex"
    assert Route.HEADLESS.value == "headless"
    assert Route.BROKER.value == "broker"
    # Cobertura completa de FailureReason
    expected = {
        "login_required",
        "quota_exceeded",
        "interactive_mode_detected",
        "timeout_no_artifact",
        "execution_error",
        "sentinel_not_observed",
        "artifact_invalid",
        "broker_unavailable",
    }
    assert {r.value for r in FailureReason} == expected


def test_agent_task_eh_frozen() -> None:
    t = AgentTask(
        run_id="r1",
        prompt="x",
        output_path=Path("/tmp/out.json"),
        schema_hint=None,
        workspace=Path("/tmp"),
        timeout_hard_s=10,
        heartbeat_s=2,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.run_id = "r2"  # type: ignore[misc]


def test_agent_task_metadata_default_eh_dict_independente() -> None:
    t1 = AgentTask(run_id="a", prompt="x", output_path=Path("/tmp/a"),
                   schema_hint=None, workspace=Path("/tmp"),
                   timeout_hard_s=1, heartbeat_s=1)
    t2 = AgentTask(run_id="b", prompt="y", output_path=Path("/tmp/b"),
                   schema_hint=None, workspace=Path("/tmp"),
                   timeout_hard_s=1, heartbeat_s=1)
    # Mesmo objeto não deve ser compartilhado entre instâncias
    assert t1.metadata is not t2.metadata


def test_attempt_log_calcula_duracao() -> None:
    a = AttemptLog(
        engine=Engine.CLAUDE,
        route=Route.HEADLESS,
        started_at=100.0,
        ended_at=142.5,
        success=True,
        failure_reason=None,
        sentinel_observed=True,
        artifact_written=True,
    )
    assert a.duration_s == pytest.approx(42.5)


def test_validation_result_factories() -> None:
    accepted = ValidationResult.accepted_from(Path("/x"), {"a": 1}, recovered=True)
    assert accepted.accepted is True
    assert accepted.recovered_from_relay is True
    assert accepted.failure_reason is None

    rejected = ValidationResult.rejected(FailureReason.ARTIFACT_INVALID, "porquê")
    assert rejected.accepted is False
    assert rejected.failure_reason == FailureReason.ARTIFACT_INVALID
    assert rejected.failure_detail == "porquê"
    assert rejected.recovered_from_relay is False


def test_agent_result_aceita_lista_de_attempts_vazia() -> None:
    r = AgentResult(
        success=True,
        engine_used=Engine.CLAUDE,
        route_used=Route.HEADLESS,
        artifact_path=Path("/x"),
        artifact_data={"k": 1},
        failure_reason=None,
        failure_detail=None,
        attempts=[],
        duration_s=1.0,
    )
    assert r.attempts == []
