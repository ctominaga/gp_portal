"""ClaudeHeadlessRoute — invoca `claude -p` em modo não-interativo.

Spec: 02_jump_agent_runner_spec.md, seção 5.1.

Notas de implementação:
- O envelope de prompt é construído pela `prompt.wrap_prompt()` (§7).
- Detecção de falhas é feita por regex em stderr/stdout DEPOIS da execução.
  Padrões cobrem: login required (`Not authenticated`, `Please login`),
  quota exceeded (`rate limit`, `quota`).
- Stdin grande NÃO é usado: o input vai pra arquivo no workspace e o prompt
  referencia. Mitigação para issue conhecido de stdin grande retornar vazio.
- Hard timeout via asyncio (helper `run_with_heartbeat`).
"""
from __future__ import annotations

import re
import time

from ..observer import Observer
from ..prompt import sentinel_for, wrap_prompt
from ..types import AgentTask, AttemptLog, Engine, FailureReason, Route
from ._subprocess import quick_check, resolve_executable, run_with_heartbeat

# Patterns aplicados em stderr+stdout combinados, case-insensitive.
_LOGIN_PATTERNS = re.compile(
    r"(not\s+authenticated|please\s+log\s*in|/login|authentication\s+required|"
    r"unauthor[iz]ed|invalid\s+credentials)",
    re.IGNORECASE,
)
_QUOTA_PATTERNS = re.compile(
    r"(rate\s*limit|quota|usage\s*limit|exceeded\s+your|too\s+many\s+requests)",
    re.IGNORECASE,
)
_INTERACTIVE_PATTERNS = re.compile(
    r"(interactive\s+mode|tty\s+required|stdin\s+is\s+not\s+a\s+tty)",
    re.IGNORECASE,
)


class ClaudeHeadlessRoute:
    engine = Engine.CLAUDE
    route = Route.HEADLESS

    _DEFAULT_TOOLS = "Read,Write,Edit,Bash"

    def __init__(self, observer: Observer, executable: str | None = None) -> None:
        self.observer = observer
        # `executable` permite injetar um caminho específico (útil em testes).
        self._executable = executable

    def _claude_path(self) -> str | None:
        from pathlib import Path as _Path

        if self._executable:
            return self._executable if _Path(self._executable).exists() else None
        return resolve_executable("claude")

    async def is_available(self) -> tuple[bool, FailureReason | None]:
        path = self._claude_path()
        if not path:
            return False, FailureReason.BROKER_UNAVAILABLE
        # Probe trivial — `claude --version` retorna em <1s
        ok, _ = await quick_check([path, "--version"], timeout_s=5)
        return (ok, None) if ok else (False, FailureReason.EXECUTION_ERROR)

    async def execute(self, task: AgentTask) -> AttemptLog:
        started = time.monotonic()
        path = self._claude_path()
        if not path:
            return AttemptLog(
                engine=Engine.CLAUDE,
                route=Route.HEADLESS,
                started_at=started,
                ended_at=time.monotonic(),
                success=False,
                failure_reason=FailureReason.BROKER_UNAVAILABLE,
                sentinel_observed=False,
                artifact_written=task.output_path.exists(),
                notes="claude executable not found in PATH",
            )

        wrapped = wrap_prompt(task)
        sentinel = sentinel_for(task.run_id)

        # NOTA F5.6a (2026-05-14): `--bare` foi REMOVIDO. No Claude Code v2.1.141
        # (e provavelmente toda v2.1.x), `--bare` força auth via ANTHROPIC_API_KEY
        # ou apiKeyHelper, e *NUNCA* lê OAuth/keychain — vide `claude --help`:
        #
        #   "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via
        #    --settings (OAuth and keychain are never read)."
        #
        # Com OAuth login feito via TUI (`claude /login`), o headless com `--bare`
        # retorna `Not logged in · Please run /login` — bug F2.8 que adiou o smoke
        # no ADR 2026-05-11 e agora foi diagnosticado. Versões anteriores aceitavam
        # OAuth com `--bare`, mas o flag passou a ser estrito. Os comportamentos
        # úteis do `--bare` (skip hooks, LSP, plugin sync, CLAUDE.md auto-discovery)
        # já estão implicitamente cobertos por `-p` (print mode non-interactive).
        cmd = [
            path,
            "-p",
            wrapped,
            "--output-format",
            "json",
            "--allowedTools",
            self._DEFAULT_TOOLS,
        ]

        outcome = await run_with_heartbeat(
            cmd,
            cwd=task.workspace,
            timeout_s=task.timeout_hard_s,
            heartbeat_s=task.heartbeat_s,
            sentinel_pattern=sentinel,
            observer=self.observer,
            event_name="headless_heartbeat",
            event_payload={"engine": Engine.CLAUDE.value, "run_id": task.run_id},
        )
        ended = time.monotonic()

        artifact_written = task.output_path.exists()

        if outcome.timed_out:
            return AttemptLog(
                engine=Engine.CLAUDE,
                route=Route.HEADLESS,
                started_at=started,
                ended_at=ended,
                success=False,
                failure_reason=FailureReason.TIMEOUT_NO_ARTIFACT,
                sentinel_observed=outcome.sentinel_observed,
                artifact_written=artifact_written,
                notes=f"hard timeout after {task.timeout_hard_s}s",
            )

        failure = self._classify_failure(
            returncode=outcome.returncode,
            stderr=outcome.stderr,
            stdout=outcome.stdout,
            sentinel=outcome.sentinel_observed,
            artifact_written=artifact_written,
        )

        notes_blob = (outcome.stderr or outcome.stdout)[-500:].strip()
        return AttemptLog(
            engine=Engine.CLAUDE,
            route=Route.HEADLESS,
            started_at=started,
            ended_at=ended,
            success=(failure is None),
            failure_reason=failure,
            sentinel_observed=outcome.sentinel_observed,
            artifact_written=artifact_written,
            notes=notes_blob,
        )

    @staticmethod
    def _classify_failure(
        returncode: int,
        stderr: str,
        stdout: str,
        sentinel: bool,
        artifact_written: bool,
    ) -> FailureReason | None:
        """Mapeia output em uma `FailureReason`.

        Ordem importa: login → quota → interactive → execução → sentinel/artefato.
        Se nada bater e tudo correr bem, retorna None — quem chama (provider) usa
        o ArtifactValidator para a decisão final.
        """
        combined = f"{stderr}\n{stdout}"
        if _LOGIN_PATTERNS.search(combined):
            return FailureReason.LOGIN_REQUIRED
        if _QUOTA_PATTERNS.search(combined):
            return FailureReason.QUOTA_EXCEEDED
        if _INTERACTIVE_PATTERNS.search(combined):
            return FailureReason.INTERACTIVE_MODE_DETECTED
        if returncode != 0:
            return FailureReason.EXECUTION_ERROR
        if not sentinel and not artifact_written:
            return FailureReason.SENTINEL_NOT_OBSERVED
        return None  # validator final decide
