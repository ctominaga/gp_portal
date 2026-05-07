"""WSLTmuxBroker — sessões `tmux` persistentes dentro de WSL2.

Spec: 02_jump_agent_runner_spec.md, seção 6.

Decisões:
- `wsl.exe -d <distro> --` em todos os comandos (default: `Ubuntu-22.04`).
- `_preflight()` é lazy (chamado em `ensure_ready()`), evitando RuntimeError em import.
- Captura de relay usa `tmux capture-pane -p -J -S -5000` para juntar linhas
  quebradas e capturar até 5000 linhas do scrollback.
- Login pending sentinel: arquivo em `~/.jump-runner/login-pending-{engine}`.
- Implementa o protocolo `BrokerBackend`.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ..observer import Observer
from ..routes._subprocess import resolve_executable
from ..types import Engine

DEFAULT_DISTRO = "Ubuntu-22.04"
LOGIN_PENDING_DIR = Path.home() / ".jump-runner"

# Padrões em relay tmux que indicam falha de autenticação.
_LOGIN_FAIL_MARKERS = [
    "not authenticated",
    "please log in",
    "/login",
    "authentication required",
    "unauthorized",
    "not logged in",
    "run `codex login`",
    "run codex login",
    "sign in to continue",
]


class BrokerNotReadyError(RuntimeError):
    """Broker pediu para uso mas pré-requisitos (wsl, tmux) não estão presentes."""


class WSLTmuxBroker:
    """Broker que mantém sessões `tmux` em WSL2.

    Sessões dedicadas convencionais: `project-claude` e `project-codex`.
    """

    def __init__(
        self,
        observer: Observer,
        distro: str = DEFAULT_DISTRO,
        wsl_executable: str | None = None,
    ) -> None:
        self.observer = observer
        self.distro = distro
        self._wsl_path = wsl_executable
        self._preflighted = False

    # -------- preflight & helpers --------

    def _wsl(self) -> str | None:
        if self._wsl_path:
            return self._wsl_path if Path(self._wsl_path).exists() else None
        return resolve_executable("wsl") or resolve_executable("wsl.exe")

    async def ensure_ready(self) -> None:
        """Valida que wsl + distro + tmux estão disponíveis. Idempotente."""
        if self._preflighted:
            return
        wsl = self._wsl()
        if not wsl:
            raise BrokerNotReadyError("wsl.exe não encontrado no PATH.")
        result = await self._run("which", "tmux")
        if result.returncode != 0 or not result.stdout.strip():
            raise BrokerNotReadyError(
                f"tmux não encontrado em WSL distro '{self.distro}'. "
                "Rode `setup-windows.ps1` para instalar."
            )
        self._preflighted = True

    async def _run(self, *args: str, timeout_s: float = 30) -> ProcessOutcome:
        """Executa `wsl -d <distro> -- <args>` e retorna stdout/stderr/returncode."""
        wsl = self._wsl()
        if not wsl:
            raise BrokerNotReadyError("wsl.exe não encontrado.")
        cmd = [wsl, "-d", self.distro, "--", *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return ProcessOutcome("", "timeout", 124)
        return ProcessOutcome(
            stdout=(stdout or b"").decode("utf-8", errors="replace"),
            stderr=(stderr or b"").decode("utf-8", errors="replace"),
            returncode=proc.returncode if proc.returncode is not None else -1,
        )

    # -------- protocolo BrokerBackend --------

    async def session_exists(self, name: str) -> bool:
        await self.ensure_ready()
        result = await self._run("tmux", "has-session", "-t", name)
        return result.returncode == 0

    async def create_session(self, name: str, shell_cmd: str = "bash") -> None:
        await self.ensure_ready()
        if await self.session_exists(name):
            return
        await self._run("tmux", "new-session", "-d", "-s", name, shell_cmd)
        # Pequena espera para o tmux estabilizar a sessão
        await asyncio.sleep(0.5)
        self.observer.emit("broker_session_created", name=name)

    async def is_logged_in(self, name: str, engine: Engine) -> bool:
        await self.ensure_ready()
        if not await self.session_exists(name):
            return False
        probe = {
            Engine.CLAUDE: 'claude -p "respond with just ok" --bare --output-format json',
            Engine.CODEX: 'codex exec --skip-git-repo-check --json "respond with just ok"',
        }[engine]
        await self.send_command(name, probe)
        # Espera curta para o probe começar a produzir output. Login interativo
        # pediria input, gerando texto de auth no relay.
        await asyncio.sleep(3)
        relay = await self.capture_relay(name)
        relay_lc = relay.lower()
        return not any(marker in relay_lc for marker in _LOGIN_FAIL_MARKERS)

    async def request_user_login(self, name: str, engine: Engine) -> None:
        await self.ensure_ready()
        login_cmd = {
            Engine.CLAUDE: "claude /login",
            Engine.CODEX: "codex login",
        }[engine]
        await self.send_command(name, login_cmd)
        marker = LOGIN_PENDING_DIR / f"login-pending-{engine.value}"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(name, encoding="utf-8")
        self.observer.emit(
            "user_login_required",
            engine=engine.value,
            session=name,
            instructions=(
                f"Conecte ao worker e rode: wsl tmux attach -t {name}. "
                f"Conclua o login (browser abrirá pela integração wslg). "
                f"Desanexe com Ctrl+B D. "
                f"Em seguida rode: jump-runner login-confirm {engine.value}"
            ),
        )

    async def send_command(self, name: str, command: str) -> None:
        await self.ensure_ready()
        # `-l` envia literal (ignora sequências de escape do tmux)
        await self._run("tmux", "send-keys", "-t", name, "-l", command)
        await self._run("tmux", "send-keys", "-t", name, "Enter")

    async def wait_for_sentinel(
        self,
        name: str,
        sentinel: str,
        timeout_s: int,
        heartbeat_s: int,
    ) -> bool:
        await self.ensure_ready()
        deadline = time.monotonic() + timeout_s
        last_len = 0
        while time.monotonic() < deadline:
            relay = await self.capture_relay(name)
            if sentinel in relay:
                self.observer.emit("sentinel_observed", session=name, sentinel=sentinel)
                return True
            if len(relay) != last_len:
                self.observer.emit(
                    "broker_heartbeat",
                    session=name,
                    bytes_new=len(relay) - last_len,
                    elapsed_s=int(time.monotonic() - (deadline - timeout_s)),
                )
                last_len = len(relay)
            # Não dorme `heartbeat_s` se já passou do deadline
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(heartbeat_s, remaining))
        return False

    async def capture_relay(self, name: str) -> str:
        await self.ensure_ready()
        # `-J` junta linhas wrapadas; `-S -5000` pega 5000 linhas de scrollback
        result = await self._run(
            "tmux", "capture-pane", "-p", "-J", "-S", "-5000", "-t", name
        )
        return result.stdout


class ProcessOutcome:
    """Resultado simples de subprocess assíncrono. Equivalente a CompletedProcess."""

    __slots__ = ("stdout", "stderr", "returncode")

    def __init__(self, stdout: str, stderr: str, returncode: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
