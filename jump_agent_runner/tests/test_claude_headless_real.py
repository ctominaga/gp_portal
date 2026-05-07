"""Smoke real do ClaudeHeadlessRoute — só roda em workstation com `claude` no PATH.

CI sem login do Claude pula via skipif. Para rodar localmente:
    pytest tests/test_claude_headless_real.py -v
"""
from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.routes.claude_headless import ClaudeHeadlessRoute
from jump_agent_runner.types import AgentTask

pytestmark = pytest.mark.requires_claude_cli

CLAUDE_AVAILABLE = shutil.which("claude") is not None


@pytest.mark.skipif(not CLAUDE_AVAILABLE, reason="claude CLI não disponível no PATH")
@pytest.mark.asyncio
async def test_smoke_claude_responde_a_pedido_trivial(tmp_path: Path) -> None:
    """Pede ao Claude para escrever {"ok": true} em out.json e emitir sentinel."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    output = workspace / "out.json"

    observer = Observer(log_dir=tmp_path / "logs", stream=io.StringIO())
    route = ClaudeHeadlessRoute(observer=observer)

    task = AgentTask(
        run_id="smoke-001",
        prompt='Escreva o objeto JSON {"ok": true} no arquivo de saída e emita o sentinel.',
        output_path=output,
        schema_hint={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        workspace=workspace,
        timeout_hard_s=120,
        heartbeat_s=15,
    )

    log = await route.execute(task)

    # Não asseguramos `success=True` rigorosamente — Claude pode responder com
    # texto ao invés de gravar arquivo, dependendo do estado de login.
    # O importante é não levantar exceção e produzir um AttemptLog coerente.
    assert log.engine.value == "claude"
    assert log.route.value == "headless"
    assert log.ended_at >= log.started_at

    # Se sucesso: arquivo deve existir e conter o JSON pedido.
    if log.success and log.artifact_written:
        import json

        data = json.loads(output.read_text(encoding="utf-8"))
        assert data.get("ok") is True
