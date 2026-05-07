"""CLI do jump-agent-runner — `jump-runner <subcommand>`.

Subcommands:
  - `login-confirm <engine>`: marca login Claude/Codex como concluído
    (remove sentinela `~/.jump-runner/login-pending-{engine}`).
  - `smoke`: executa uma tarefa trivial end-to-end (Claude → Codex)
    para validar que o setup do worker está funcional.

Uso direto também via `python -m jump_agent_runner.cli.main`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from ..artifact import ArtifactValidator
from ..broker.wsl_tmux import LOGIN_PENDING_DIR, WSLTmuxBroker
from ..observer import Observer
from ..providers.claude_provider import ClaudeProvider
from ..providers.codex_provider import CodexProvider
from ..runner import AgentRunner
from ..types import AgentTask, Engine

_VALID_ENGINES = {e.value for e in Engine}


def _login_confirm(engine: str) -> int:
    if engine not in _VALID_ENGINES:
        print(f"engine inválido: {engine}. Use: {sorted(_VALID_ENGINES)}", file=sys.stderr)
        return 2
    marker = LOGIN_PENDING_DIR / f"login-pending-{engine}"
    if not marker.exists():
        print(f"nenhum login pendente para {engine} (sentinela {marker} não existe).")
        return 0
    marker.unlink()
    print(f"login confirmado para {engine}: {marker} removido.")
    return 0


async def _run_smoke(workspace: Path) -> int:
    workspace.mkdir(parents=True, exist_ok=True)
    out = workspace / "smoke-out.json"

    observer = Observer()
    backend = WSLTmuxBroker(observer=observer)

    primary = ClaudeProvider(observer=observer, broker_backend=backend)
    secondary = CodexProvider(observer=observer, broker_backend=backend)

    runner = AgentRunner(primary=primary, secondary=secondary, observer=observer)

    task = AgentTask(
        run_id=f"smoke-{int(time.time())}",
        prompt='Escreva o objeto JSON {"ok": true} no arquivo de saída e emita o sentinel.',
        output_path=out,
        schema_hint={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        workspace=workspace,
        timeout_hard_s=180,
        heartbeat_s=15,
    )

    print(f"smoke iniciando — workspace={workspace}, output={out}")
    result = await runner.run(task)

    if result.success:
        print(
            f"OK engine={result.engine_used.value if result.engine_used else '?'} "
            f"route={result.route_used.value if result.route_used else '?'} "
            f"duration={result.duration_s:.1f}s attempts={len(result.attempts)}"
        )
        if result.artifact_data:
            print("artifact:", json.dumps(result.artifact_data, ensure_ascii=False))
        return 0

    print(
        f"FAIL reason={result.failure_reason.value if result.failure_reason else '?'} "
        f"detail={(result.failure_detail or '')[:300]}",
        file=sys.stderr,
    )
    print("attempts:", file=sys.stderr)
    for i, att in enumerate(result.attempts, start=1):
        print(
            f"  [{i}] engine={att.engine.value} route={att.route.value} "
            f"success={att.success} reason={att.failure_reason.value if att.failure_reason else '-'}",
            file=sys.stderr,
        )
    return 1


def _cmd_smoke(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve() if args.workspace else (
        Path.home() / ".jump-runner" / "smoke-workspace"
    )
    return asyncio.run(_run_smoke(ws))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jump-runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login-confirm", help="confirma login interativo de Claude ou Codex")
    p_login.add_argument("engine", choices=sorted(_VALID_ENGINES))

    p_smoke = sub.add_parser("smoke", help="executa uma tarefa simples end-to-end")
    p_smoke.add_argument("--workspace", help="workspace para o smoke (default: ~/.jump-runner/smoke-workspace)")

    args = parser.parse_args(argv)

    if args.cmd == "login-confirm":
        return _login_confirm(args.engine)
    if args.cmd == "smoke":
        return _cmd_smoke(args)

    parser.print_help()
    return 2


# Garantir que ArtifactValidator é importavel via cli (ruff F401 em modules vazios)
__all__ = ["main", "ArtifactValidator"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
