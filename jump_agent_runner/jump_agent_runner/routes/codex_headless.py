"""CodexHeadlessRoute — invoca `codex exec` em modo não-interativo via WSL.

Spec: 02_jump_agent_runner_spec.md, seção 5.2.

Notas:
- Sempre passa por `wsl.exe -d <distro> --` para garantir TTY adequado e
  ambiente Linux. Codex tem histórico de instabilidade em cmd.exe direto.
- Paths Windows são traduzidos para WSL: C:\\foo → /mnt/c/foo.
- Flags usadas: --skip-git-repo-check, --json, --output-last-message FILE,
  --output-schema FILE (quando aplicável), --ephemeral.
- A última mensagem do agente é gravada em output_path (via --output-last-message).
  Isto é diferente da rota Claude, onde o agente usa Write tool para criar o arquivo.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..observer import Observer
from ..prompt import sentinel_for, wrap_prompt
from ..types import AgentTask, AttemptLog, Engine, FailureReason, Route
from ._subprocess import quick_check, resolve_executable, run_with_heartbeat

DEFAULT_DISTRO = "Ubuntu-22.04"

_LOGIN_PATTERNS = re.compile(
    r"(not\s+(?:logged\s*in|authenticated)|please\s+log\s*in|run\s+`?codex\s+login`?|"
    r"sign\s+in\s+to\s+continue|authentication\s+required|unauthor[iz]ed)",
    re.IGNORECASE,
)
_QUOTA_PATTERNS = re.compile(
    r"(rate\s*limit|quota|usage\s*limit|exceeded\s+your|too\s+many\s+requests)",
    re.IGNORECASE,
)
_INTERACTIVE_PATTERNS = re.compile(
    r"(stdin\s+is\s+not\s+a\s+tty|interactive\s+mode|tty\s+required)",
    re.IGNORECASE,
)


def windows_to_wsl(path: Path | str) -> str:
    """C:\\Users\\chris\\foo → /mnt/c/Users/chris/foo. Idempotente para paths já WSL."""
    s = str(path).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        drive = s[0].lower()
        rest = s[2:].lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return s


class CodexHeadlessRoute:
    engine = Engine.CODEX
    route = Route.HEADLESS

    def __init__(
        self,
        observer: Observer,
        distro: str = DEFAULT_DISTRO,
        wsl_executable: str | None = None,
    ) -> None:
        self.observer = observer
        self.distro = distro
        self._wsl = wsl_executable

    def _wsl_path(self) -> str | None:
        if self._wsl:
            return self._wsl if Path(self._wsl).exists() else None
        # `wsl.exe` reside em System32 e está sempre no PATH do Windows
        return resolve_executable("wsl") or resolve_executable("wsl.exe")

    async def is_available(self) -> tuple[bool, FailureReason | None]:
        wsl = self._wsl_path()
        if not wsl:
            return False, FailureReason.BROKER_UNAVAILABLE
        # Probe: `wsl -d <distro> -- codex --version`
        ok, _ = await quick_check([wsl, "-d", self.distro, "--", "codex", "--version"], timeout_s=10)
        return (ok, None) if ok else (False, FailureReason.EXECUTION_ERROR)

    async def execute(self, task: AgentTask) -> AttemptLog:
        started = time.monotonic()
        wsl = self._wsl_path()
        if not wsl:
            return AttemptLog(
                engine=Engine.CODEX,
                route=Route.HEADLESS,
                started_at=started,
                ended_at=time.monotonic(),
                success=False,
                failure_reason=FailureReason.BROKER_UNAVAILABLE,
                sentinel_observed=False,
                artifact_written=task.output_path.exists(),
                notes="wsl.exe not found in PATH",
            )

        # output_path em formato WSL para passar ao codex
        wsl_output = windows_to_wsl(task.output_path)

        cmd: list[str] = [
            wsl,
            "-d",
            self.distro,
            "--",
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--json",
            "--ephemeral",
            "--output-last-message",
            wsl_output,
        ]

        # Schema opcional vai pra arquivo no workspace
        if task.schema_hint:
            schema_file = task.workspace / f".{task.run_id}.schema.json"
            schema_file.write_text(json.dumps(task.schema_hint), encoding="utf-8")
            cmd += ["--output-schema", windows_to_wsl(schema_file)]

        cmd.append(wrap_prompt(task))

        sentinel = sentinel_for(task.run_id)
        outcome = await run_with_heartbeat(
            cmd,
            cwd=task.workspace,
            timeout_s=task.timeout_hard_s,
            heartbeat_s=task.heartbeat_s,
            sentinel_pattern=sentinel,
            observer=self.observer,
            event_name="headless_heartbeat",
            event_payload={"engine": Engine.CODEX.value, "run_id": task.run_id},
        )
        ended = time.monotonic()

        artifact_written = task.output_path.exists()

        if outcome.timed_out:
            return AttemptLog(
                engine=Engine.CODEX,
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
            engine=Engine.CODEX,
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
        return None
