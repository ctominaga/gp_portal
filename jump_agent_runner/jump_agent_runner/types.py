"""Tipos públicos do jump-agent-runner.

Spec: 02_jump_agent_runner_spec.md, seções 3 e 8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Engine(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class Route(str, Enum):
    HEADLESS = "headless"
    BROKER = "broker"


class FailureReason(str, Enum):
    LOGIN_REQUIRED = "login_required"
    QUOTA_EXCEEDED = "quota_exceeded"
    INTERACTIVE_MODE_DETECTED = "interactive_mode_detected"
    TIMEOUT_NO_ARTIFACT = "timeout_no_artifact"
    EXECUTION_ERROR = "execution_error"
    SENTINEL_NOT_OBSERVED = "sentinel_not_observed"
    ARTIFACT_INVALID = "artifact_invalid"
    BROKER_UNAVAILABLE = "broker_unavailable"


@dataclass(frozen=True)
class AgentTask:
    run_id: str
    prompt: str
    output_path: Path
    schema_hint: dict | None
    workspace: Path
    timeout_hard_s: int
    heartbeat_s: int
    metadata: dict = field(default_factory=dict)
    continuation_hint: str | None = None


@dataclass(frozen=True)
class AttemptLog:
    engine: Engine
    route: Route
    started_at: float
    ended_at: float
    success: bool
    failure_reason: FailureReason | None
    sentinel_observed: bool
    artifact_written: bool
    notes: str = ""

    @property
    def duration_s(self) -> float:
        return self.ended_at - self.started_at


@dataclass(frozen=True)
class AgentResult:
    success: bool
    engine_used: Engine | None
    route_used: Route | None
    artifact_path: Path | None
    artifact_data: dict | None
    failure_reason: FailureReason | None
    failure_detail: str | None
    attempts: list[AttemptLog]
    duration_s: float


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    artifact_path: Path | None
    artifact_data: dict | None
    failure_reason: FailureReason | None
    failure_detail: str | None
    recovered_from_relay: bool

    @classmethod
    def accepted_from(
        cls,
        path: Path,
        data: dict,
        recovered: bool = False,
    ) -> ValidationResult:
        return cls(
            accepted=True,
            artifact_path=path,
            artifact_data=data,
            failure_reason=None,
            failure_detail=None,
            recovered_from_relay=recovered,
        )

    @classmethod
    def rejected(cls, reason: FailureReason, detail: str) -> ValidationResult:
        return cls(
            accepted=False,
            artifact_path=None,
            artifact_data=None,
            failure_reason=reason,
            failure_detail=detail,
            recovered_from_relay=False,
        )
