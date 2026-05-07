"""Fixtures comuns aos testes do jump-agent-runner."""
from __future__ import annotations

from pathlib import Path

import pytest

from jump_agent_runner.types import AgentTask


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def task(workspace: Path) -> AgentTask:
    return AgentTask(
        run_id="test-run-001",
        prompt="Faça X e devolva JSON.",
        output_path=workspace / "out.json",
        schema_hint=None,
        workspace=workspace,
        timeout_hard_s=60,
        heartbeat_s=10,
        metadata={},
        continuation_hint=None,
    )
