#!/usr/bin/env python3
"""F2.8 smoke real do agente leitor contra proposta Bradesco (F5.6b).

Invoca o `jump_agent_runner` ponta-a-ponta:

1. Carrega o prompt versionado `docs/prompts/proposal_reader_v1.md`.
2. Copia o texto pré-extraído da proposta para um workspace temporário
   (decisão Q2=b: smoke isola "agente leitor" de "extração de PDF").
3. Instancia `AgentRunner(ClaudeProvider primário, CodexProvider fallback)`.
4. Roda `await runner.run(task)` e captura o `AgentResult`.
5. Salva o artefato JSON do agente + metadata em `~/.jump-runner/f28-bradesco/`.

Este script NÃO compara o output contra o expected.json — isso é feito por
`f28_compare_bradesco.py` (Commit 3 do F5.6b).

Pré-requisitos:
- Setup do WSL completo (`worker/scripts/setup-windows.ps1`).
- Login Claude OAuth feito no tmux `project-claude`.
- Rodar via `~/.jump-runner/.venv-worker/bin/python scripts/f28_smoke_bradesco.py`
  DENTRO do WSL (claude precisa estar resolvido como nativo, não mount Windows).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

from jump_agent_runner.broker.wsl_tmux import WSLTmuxBroker
from jump_agent_runner.observer import Observer
from jump_agent_runner.providers.claude_provider import ClaudeProvider
from jump_agent_runner.providers.codex_provider import CodexProvider
from jump_agent_runner.runner import AgentRunner
from jump_agent_runner.types import AgentTask

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = REPO_ROOT / "docs" / "prompts" / "proposal_reader_v1.md"
PROPOSAL_TXT = (
    REPO_ROOT / "backend" / "tests" / "fixtures" / "proposals"
    / "bradesco_sas_databricks.txt"
)
DELIM_START = "=== INÍCIO DO PROMPT proposal_reader_v1 ==="
DELIM_END = "=== FIM DO PROMPT proposal_reader_v1 ==="

# Schema das 6 chaves top-level do `bradesco_sas_databricks.expected.json`.
# Contrato grosso para o agente; a comparação fina vai pelo script de compare.
SCHEMA_HINT: dict = {
    "type": "object",
    "required": ["project", "phases", "deliverables", "out_of_scope", "key_premises"],
    "properties": {
        "_meta": {"type": "object"},
        "project": {"type": "object"},
        "phases": {"type": "array"},
        "deliverables": {"type": "array"},
        "out_of_scope": {"type": "array"},
        "key_premises": {"type": "array"},
    },
}


def _extract_prompt_body(md_text: str) -> str:
    """Extrai o texto literal entre os delimitadores do markdown do prompt."""
    start = md_text.find(DELIM_START)
    end = md_text.find(DELIM_END)
    if start < 0 or end < 0:
        raise RuntimeError(
            f"delimitadores '{DELIM_START}' / '{DELIM_END}' não encontrados em "
            f"{PROMPT_PATH}"
        )
    body = md_text[start + len(DELIM_START) : end]
    # Remove cercas de código `\`\`\`` que delimitam o bloco em markdown.
    return body.strip("` \n")


async def _run_smoke(workspace: Path, timeout_s: int) -> int:
    if not PROMPT_PATH.exists():
        print(f"ERRO: prompt ausente em {PROMPT_PATH}", file=sys.stderr)
        return 2
    if not PROPOSAL_TXT.exists():
        print(f"ERRO: proposta ausente em {PROPOSAL_TXT}", file=sys.stderr)
        return 2

    prompt_body = _extract_prompt_body(PROMPT_PATH.read_text(encoding="utf-8"))

    workspace.mkdir(parents=True, exist_ok=True)
    proposal_in_ws = workspace / "proposal.txt"
    shutil.copyfile(PROPOSAL_TXT, proposal_in_ws)
    output_path = workspace / "bradesco_actual.json"
    output_path.unlink(missing_ok=True)

    task_prompt = (
        f"{prompt_body}\n\n"
        f"PROPOSTA A EXTRAIR: leia o arquivo `{proposal_in_ws}` com a "
        "ferramenta Read e produza o JSON canônico conforme as instruções acima "
        "e o schema fornecido."
    )

    run_id = f"f28-bradesco-{int(time.time())}"

    print(f"workspace       = {workspace}")
    print(f"output_path     = {output_path}")
    print(f"run_id          = {run_id}")
    print(f"prompt chars    = {len(task_prompt):,}")
    print(f"proposal chars  = {proposal_in_ws.stat().st_size:,}")
    print(f"timeout_hard_s  = {timeout_s}")
    print()
    print(f"--- AgentRunner.run() start at {time.strftime('%H:%M:%S')} ---")

    observer = Observer()
    broker = WSLTmuxBroker(observer=observer)
    primary = ClaudeProvider(observer=observer, broker_backend=broker)
    secondary = CodexProvider(observer=observer, broker_backend=broker)
    runner = AgentRunner(primary=primary, secondary=secondary, observer=observer)

    task = AgentTask(
        run_id=run_id,
        prompt=task_prompt,
        output_path=output_path,
        schema_hint=SCHEMA_HINT,
        workspace=workspace,
        timeout_hard_s=timeout_s,
        heartbeat_s=30,
    )

    started = time.monotonic()
    result = await runner.run(task)
    elapsed = time.monotonic() - started

    print()
    print(f"--- AgentRunner.run() end ({elapsed:.1f}s) ---")
    print(f"success         = {result.success}")
    print(f"engine_used     = {result.engine_used.value if result.engine_used else None}")
    print(f"route_used      = {result.route_used.value if result.route_used else None}")
    print(f"attempts        = {len(result.attempts)}")
    if result.failure_reason:
        print(f"failure_reason  = {result.failure_reason.value}")
    if result.failure_detail:
        print(f"failure_detail  = {result.failure_detail[:300]}")
    if result.success and result.artifact_data:
        keys = list(result.artifact_data.keys())
        print(f"artifact keys   = {keys}")

    metadata = {
        "run_id": run_id,
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_s": round(elapsed, 1),
        "success": result.success,
        "engine_used": result.engine_used.value if result.engine_used else None,
        "route_used": result.route_used.value if result.route_used else None,
        "failure_reason": (
            result.failure_reason.value if result.failure_reason else None
        ),
        "failure_detail": result.failure_detail,
        "attempts": [
            {
                "engine": a.engine.value,
                "route": a.route.value,
                "success": a.success,
                "failure_reason": (
                    a.failure_reason.value if a.failure_reason else None
                ),
                "duration_s": round(a.duration_s, 2),
                "sentinel_observed": a.sentinel_observed,
                "artifact_written": a.artifact_written,
            }
            for a in result.attempts
        ],
        "artifact_path": str(result.artifact_path) if result.artifact_path else None,
        "prompt_version": "proposal_reader_v1.md",
        "proposal_source": str(PROPOSAL_TXT.relative_to(REPO_ROOT)),
    }
    metadata_path = workspace / "smoke_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"metadata saved  = {metadata_path}")

    return 0 if result.success else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="f28-smoke-bradesco")
    parser.add_argument(
        "--workspace",
        help="diretório do workspace (default: ~/.jump-runner/f28-bradesco)",
    )
    parser.add_argument(
        "--timeout-s",
        type=int,
        default=900,
        help="timeout hard do AgentRunner em segundos (default: 900 = 15min)",
    )
    args = parser.parse_args()
    workspace = (
        Path(args.workspace).resolve()
        if args.workspace
        else (Path.home() / ".jump-runner" / "f28-bradesco")
    )
    return asyncio.run(_run_smoke(workspace, args.timeout_s))


if __name__ == "__main__":
    raise SystemExit(main())
