"""Testes do envelope canônico de prompt (§7)."""
from __future__ import annotations

import json
from pathlib import Path

from jump_agent_runner.prompt import sentinel_for, wrap_prompt
from jump_agent_runner.types import AgentTask


def _make_task(**overrides) -> AgentTask:
    base = {
        "run_id": "r-001",
        "prompt": "Faça X",
        "output_path": Path("/abs/out.json"),
        "schema_hint": None,
        "workspace": Path("/abs/ws"),
        "timeout_hard_s": 60,
        "heartbeat_s": 10,
        "metadata": {},
        "continuation_hint": None,
    }
    base.update(overrides)
    return AgentTask(**base)


def test_sentinel_for_eh_string_canonica() -> None:
    assert sentinel_for("abc-123") == "AGENT_DONE:abc-123"


def test_envelope_inclui_prompt_e_output_path_e_sentinel() -> None:
    task = _make_task(prompt="Extraia entregáveis da proposta.")
    out = wrap_prompt(task)

    assert "Extraia entregáveis da proposta." in out
    assert str(task.output_path) in out
    assert "AGENT_DONE:r-001" in out
    assert "esquema livre" in out  # schema_hint=None -> texto livre


def test_envelope_serializa_schema_hint_quando_presente() -> None:
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    task = _make_task(schema_hint=schema)
    out = wrap_prompt(task)

    assert json.dumps(schema, indent=2, ensure_ascii=False) in out
    assert "esquema livre" not in out


def test_envelope_inclui_continuation_hint_quando_presente() -> None:
    task = _make_task(
        continuation_hint="Tentativa anterior produziu workspace/scratch/foo.json. Continue daí."
    )
    out = wrap_prompt(task)

    assert "CONTINUAÇÃO DE TENTATIVA ANTERIOR" in out
    assert "workspace/scratch/foo.json" in out


def test_envelope_sem_continuation_nao_tem_secao() -> None:
    task = _make_task()
    out = wrap_prompt(task)
    assert "CONTINUAÇÃO" not in out


def test_envelope_referencia_workspace() -> None:
    workspace = Path("/data/jump/ws-abc")
    task = _make_task(workspace=workspace)
    out = wrap_prompt(task)
    # Comparação OS-aware: no Windows str(Path("/x/y")) usa "\\"; no POSIX, "/"
    assert str(workspace) in out
