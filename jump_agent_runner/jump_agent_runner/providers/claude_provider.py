"""ClaudeProvider — orquestra ClaudeHeadlessRoute → BrokerRoute(claude)."""
from __future__ import annotations

from ..artifact import ArtifactValidator
from ..observer import Observer
from ..protocols import AgentRoute, BrokerBackend
from ..routes.broker_route import BrokerRoute
from ..routes.claude_headless import ClaudeHeadlessRoute
from ..types import Engine
from ._base import _BaseProvider


class ClaudeProvider(_BaseProvider):
    engine = Engine.CLAUDE

    def __init__(
        self,
        observer: Observer,
        broker_backend: BrokerBackend,
        headless: AgentRoute | None = None,
        broker: AgentRoute | None = None,
        validator: ArtifactValidator | None = None,
    ) -> None:
        super().__init__(
            engine=Engine.CLAUDE,
            headless=headless or ClaudeHeadlessRoute(observer=observer),
            broker=broker or BrokerRoute(Engine.CLAUDE, broker_backend, observer),
            observer=observer,
            validator=validator,
        )
