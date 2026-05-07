"""BrokerRoute — usa um `BrokerBackend` para executar tarefas via sessão persistente.

Implementa o protocolo `AgentRoute` para rotas broker (claude e codex). É genérico:
o engine vem do construtor.

Fluxo em `execute(task)`:
    1. Garante que a sessão tmux existe (cria se preciso).
    2. Probe de login: se falhar → emite user_login_required e aguarda
       sentinela `~/.jump-runner/login-pending-{engine}` ser removida pelo
       operador via `jump-runner login-confirm`.
    3. Envia o prompt envelopado (em arquivo, para evitar problema de
       quoting) como comando na sessão.
    4. Aguarda sentinela `AGENT_DONE:{run_id}` no relay.
    5. Captura relay completo, classifica resultado, retorna AttemptLog.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ..observer import Observer
from ..prompt import sentinel_for, wrap_prompt
from ..protocols import BrokerBackend
from ..types import AgentTask, AttemptLog, Engine, FailureReason, Route

LOGIN_PENDING_DIR = Path.home() / ".jump-runner"


class BrokerRoute:
    """Rota de execução via broker (sessão tmux persistente).

    `route = Route.BROKER`. `engine` vem do construtor.
    """

    route = Route.BROKER

    def __init__(
        self,
        engine: Engine,
        backend: BrokerBackend,
        observer: Observer,
        session_name: str | None = None,
    ) -> None:
        self.engine = engine
        self.backend = backend
        self.observer = observer
        self.session_name = session_name or f"project-{engine.value}"

    async def is_available(self) -> tuple[bool, FailureReason | None]:
        """Backend está pronto? Para WSLTmuxBroker, valida wsl + tmux."""
        try:
            # ensure_ready é específico do WSLTmuxBroker, mas aderente ao protocolo
            ensure = getattr(self.backend, "ensure_ready", None)
            if ensure:
                await ensure()
            return True, None
        except Exception as exc:  # noqa: BLE001
            self.observer.emit(
                "headless_unavailable",  # reutiliza evento — semanticamente "broker_unavailable"
                engine=self.engine.value,
                reason=FailureReason.BROKER_UNAVAILABLE.value,
                detail=str(exc)[:200],
            )
            return False, FailureReason.BROKER_UNAVAILABLE

    async def execute(self, task: AgentTask) -> AttemptLog:
        started = time.monotonic()

        # 1. ensure session
        try:
            if not await self.backend.session_exists(self.session_name):
                await self.backend.create_session(self.session_name)
        except Exception as exc:  # noqa: BLE001
            return self._failure_log(started, FailureReason.BROKER_UNAVAILABLE, str(exc))

        self.observer.emit(
            "broker_session_starting",
            name=self.session_name,
            backend=type(self.backend).__name__,
        )

        # 2. probe login
        try:
            logged_in = await self.backend.is_logged_in(self.session_name, self.engine)
        except Exception as exc:  # noqa: BLE001
            return self._failure_log(started, FailureReason.EXECUTION_ERROR, str(exc))

        if not logged_in:
            await self.backend.request_user_login(self.session_name, self.engine)
            ok = await self._wait_for_login_confirmed(timeout_s=task.timeout_hard_s)
            if not ok:
                return self._failure_log(
                    started,
                    FailureReason.LOGIN_REQUIRED,
                    "operador não confirmou login dentro do timeout",
                )
            self.observer.emit(
                "login_confirmed",
                engine=self.engine.value,
                session=self.session_name,
            )
        else:
            self.observer.emit(
                "broker_already_logged_in",
                engine=self.engine.value,
                name=self.session_name,
            )

        # 3. dispatch — escreve prompt em arquivo no workspace e envia comando
        # que faz o engine ler dali. Evita problemas de quoting.
        prompt_file = task.workspace / f".{task.run_id}.prompt.txt"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(wrap_prompt(task), encoding="utf-8")

        cmd = self._build_engine_command(task, prompt_file)
        await self.backend.send_command(self.session_name, cmd)
        self.observer.emit(
            "task_dispatched",
            session=self.session_name,
            run_id=task.run_id,
            output_path=str(task.output_path),
        )

        # 4. wait for sentinel
        sentinel = sentinel_for(task.run_id)
        observed = await self.backend.wait_for_sentinel(
            self.session_name,
            sentinel=sentinel,
            timeout_s=task.timeout_hard_s,
            heartbeat_s=task.heartbeat_s,
        )
        ended = time.monotonic()

        artifact_written = task.output_path.exists()

        if not observed and not artifact_written:
            return AttemptLog(
                engine=self.engine,
                route=Route.BROKER,
                started_at=started,
                ended_at=ended,
                success=False,
                failure_reason=FailureReason.TIMEOUT_NO_ARTIFACT,
                sentinel_observed=False,
                artifact_written=False,
                notes=f"sentinel não observado em {task.timeout_hard_s}s",
            )

        # 5. captura final do relay para notes
        try:
            final_relay = await self.backend.capture_relay(self.session_name)
        except Exception:  # noqa: BLE001
            final_relay = ""

        return AttemptLog(
            engine=self.engine,
            route=Route.BROKER,
            started_at=started,
            ended_at=ended,
            success=True,
            failure_reason=None,
            sentinel_observed=observed,
            artifact_written=artifact_written,
            notes=final_relay[-500:].strip(),
        )

    # -------- helpers --------

    def _build_engine_command(self, task: AgentTask, prompt_file: Path) -> str:
        """Comando shell que será enviado à sessão tmux."""
        # Path do prompt em formato WSL — broker está rodando em WSL
        from .codex_headless import windows_to_wsl

        wsl_prompt_file = windows_to_wsl(prompt_file)
        if self.engine == Engine.CLAUDE:
            return (
                f'claude -p "$(cat {wsl_prompt_file})" '
                f"--bare --output-format json --allowedTools Read,Write,Edit,Bash"
            )
        # CODEX
        wsl_output = windows_to_wsl(task.output_path)
        return (
            f"codex exec --skip-git-repo-check --json --ephemeral "
            f"--output-last-message {wsl_output} "
            f'"$(cat {wsl_prompt_file})"'
        )

    async def _wait_for_login_confirmed(self, timeout_s: int) -> bool:
        """Aguarda sentinela `login-pending-{engine}` ser removida.

        O operador usa `jump-runner login-confirm <engine>` para remover a sentinela.
        """
        marker = LOGIN_PENDING_DIR / f"login-pending-{self.engine.value}"
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not marker.exists():
                return True
            await asyncio.sleep(2)
        return False

    def _failure_log(
        self, started: float, reason: FailureReason, detail: str
    ) -> AttemptLog:
        return AttemptLog(
            engine=self.engine,
            route=Route.BROKER,
            started_at=started,
            ended_at=time.monotonic(),
            success=False,
            failure_reason=reason,
            sentinel_observed=False,
            artifact_written=False,
            notes=detail[-500:],
        )
