"""Testes do WSLTmuxBroker.

Estratégia:
- `windows_native.py`: import + raise NotImplementedError no construtor.
- Casos sem WSL (BrokerNotReadyError) testáveis em qualquer SO.
- Casos com WSL real ficam em `test_wsl_tmux_broker_real.py`.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from jump_agent_runner.broker.windows_native import WindowsNativeBroker
from jump_agent_runner.broker.wsl_tmux import (
    BrokerNotReadyError,
    WSLTmuxBroker,
)
from jump_agent_runner.observer import Observer


@pytest.fixture
def observer(tmp_path: Path) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=io.StringIO())


def test_windows_native_broker_levanta_not_implemented() -> None:
    with pytest.raises(NotImplementedError) as exc:
        WindowsNativeBroker()
    assert "WSLTmuxBroker" in str(exc.value)


@pytest.mark.asyncio
async def test_ensure_ready_levanta_se_wsl_path_invalido(observer: Observer) -> None:
    broker = WSLTmuxBroker(
        observer=observer,
        distro="Ubuntu-22.04",
        wsl_executable="C:/inexistente/wsl.exe",
    )
    with pytest.raises(BrokerNotReadyError):
        await broker.ensure_ready()


@pytest.mark.asyncio
async def test_session_exists_propaga_broker_not_ready(observer: Observer) -> None:
    broker = WSLTmuxBroker(
        observer=observer, wsl_executable="C:/inexistente/wsl.exe"
    )
    with pytest.raises(BrokerNotReadyError):
        await broker.session_exists("any")


# ---- LOGIN_FAIL_MARKERS é um conjunto canônico ----


def test_login_fail_markers_cobrem_claude_e_codex() -> None:
    from jump_agent_runner.broker.wsl_tmux import _LOGIN_FAIL_MARKERS

    expected_claude = ["not authenticated", "please log in", "/login", "authentication required"]
    expected_codex = ["not logged in", "run codex login", "sign in to continue"]
    for s in expected_claude + expected_codex:
        assert s in _LOGIN_FAIL_MARKERS or any(s in m for m in _LOGIN_FAIL_MARKERS), s
