"""Protocolos (interfaces) do jump-agent-runner.

Spec: 02_jump_agent_runner_spec.md, seção 4.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import AgentResult, AgentTask, AttemptLog, Engine, FailureReason, Route


@runtime_checkable
class AgentRoute(Protocol):
    """Uma rota de execução para um engine específico (headless ou broker)."""

    engine: Engine
    route: Route

    async def is_available(self) -> tuple[bool, FailureReason | None]:
        ...

    async def execute(self, task: AgentTask) -> AttemptLog:
        ...


@runtime_checkable
class BrokerBackend(Protocol):
    """Backend de broker — sessão persistente onde login interativo é possível."""

    async def session_exists(self, name: str) -> bool:
        ...

    async def create_session(self, name: str, shell_cmd: str) -> None:
        ...

    async def is_logged_in(self, name: str, engine: Engine) -> bool:
        ...

    async def request_user_login(self, name: str, engine: Engine) -> None:
        ...

    async def send_command(self, name: str, command: str) -> None:
        ...

    async def wait_for_sentinel(
        self,
        name: str,
        sentinel: str,
        timeout_s: int,
        heartbeat_s: int,
    ) -> bool:
        ...

    async def capture_relay(self, name: str) -> str:
        ...


@runtime_checkable
class AgentProvider(Protocol):
    """Provedor de execução para um engine — orquestra suas rotas (headless + broker)."""

    engine: Engine

    async def run(self, task: AgentTask) -> AgentResult:
        ...
