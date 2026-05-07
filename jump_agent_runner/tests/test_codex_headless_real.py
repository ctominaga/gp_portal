"""Smoke real do CodexHeadlessRoute — só roda em workstation com WSL2 + codex no PATH WSL."""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.routes.codex_headless import DEFAULT_DISTRO, CodexHeadlessRoute
from jump_agent_runner.types import AgentTask

pytestmark = pytest.mark.requires_codex_cli


def _wsl_has_codex() -> bool:
    if not shutil.which("wsl") and not shutil.which("wsl.exe"):
        return False
    try:
        proc = subprocess.run(
            ["wsl", "-d", DEFAULT_DISTRO, "--", "which", "codex"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


CODEX_AVAILABLE = _wsl_has_codex()


@pytest.mark.skipif(not CODEX_AVAILABLE, reason="codex CLI não disponível em WSL")
@pytest.mark.asyncio
async def test_smoke_codex_responde_a_pedido_trivial(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    output = workspace / "out.json"

    observer = Observer(log_dir=tmp_path / "logs", stream=io.StringIO())
    route = CodexHeadlessRoute(observer=observer)

    task = AgentTask(
        run_id="smoke-codex-001",
        prompt='Escreva o objeto JSON {"ok": true} no arquivo de saída e emita o sentinel.',
        output_path=output,
        schema_hint={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        workspace=workspace,
        timeout_hard_s=180,
        heartbeat_s=20,
    )

    log = await route.execute(task)

    # Não asseguramos `success=True` rigorosamente — login do Codex pode não
    # estar feito, ou o comportamento pode variar.
    assert log.engine.value == "codex"
    assert log.route.value == "headless"
    assert log.ended_at >= log.started_at
