"""Stub do backend Windows nativo (ConPTY + named pipes).

Spec §6.1: WSL2+tmux é o backend padrão. Esta classe existe apenas para reservar
a interface caso a Jump tenha máquinas onde WSL não pode rodar (raras).
"""
from __future__ import annotations


class WindowsNativeBroker:
    """Broker baseado em ConPTY + processo daemon. NÃO implementado."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ARG002, D401
        raise NotImplementedError(
            "Use WSLTmuxBroker. ConPTY backend não está implementado — "
            "ver §6.1 da spec para racional."
        )
