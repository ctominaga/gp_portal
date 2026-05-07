"""CodexProvider — orquestra CodexHeadlessRoute → BrokerRoute(codex)."""
from __future__ import annotations

from ..artifact import ArtifactValidator
from ..observer import Observer
from ..protocols import AgentRoute, BrokerBackend
from ..routes.broker_route import BrokerRoute
from ..routes.codex_headless import CodexHeadlessRoute
from ..types import Engine
from ._base import _BaseProvider


class CodexProvider(_BaseProvider):
    engine = Engine.CODEX

    def __init__(
        self,
        observer: Observer,
        broker_backend: BrokerBackend,
        headless: AgentRoute | None = None,
        broker: AgentRoute | None = None,
        validator: ArtifactValidator | None = None,
    ) -> None:
        super().__init__(
            engine=Engine.CODEX,
            headless=headless or CodexHeadlessRoute(observer=observer),
            broker=broker or BrokerRoute(Engine.CODEX, broker_backend, observer),
            observer=observer,
            validator=validator,
        )
