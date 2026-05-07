"""Smoke real do WSLTmuxBroker — requer WSL2 + Ubuntu + tmux instalados."""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from jump_agent_runner.broker.wsl_tmux import DEFAULT_DISTRO, WSLTmuxBroker
from jump_agent_runner.observer import Observer

pytestmark = pytest.mark.requires_wsl


def _wsl_has_tmux() -> bool:
    if not (shutil.which("wsl") or shutil.which("wsl.exe")):
        return False
    try:
        proc = subprocess.run(
            ["wsl", "-d", DEFAULT_DISTRO, "--", "which", "tmux"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


WSL_AVAILABLE = _wsl_has_tmux()


@pytest.fixture
def observer(tmp_path: Path) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=io.StringIO())


@pytest.fixture
def broker(observer: Observer) -> WSLTmuxBroker:
    return WSLTmuxBroker(observer=observer)


def _kill_session(name: str) -> None:
    """Remove sessão tmux residual entre testes."""
    subprocess.run(
        ["wsl", "-d", DEFAULT_DISTRO, "--", "tmux", "kill-session", "-t", name],
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.skipif(not WSL_AVAILABLE, reason="WSL2 + tmux não disponíveis")
@pytest.mark.asyncio
async def test_create_session_e_session_exists_e_capture_relay(broker: WSLTmuxBroker) -> None:
    session = "jump-runner-test-1"
    _kill_session(session)
    try:
        assert await broker.session_exists(session) is False
        await broker.create_session(session)
        assert await broker.session_exists(session) is True
        relay = await broker.capture_relay(session)
        # Relay tipicamente contém o prompt PS1 do shell
        assert isinstance(relay, str)
    finally:
        _kill_session(session)


@pytest.mark.skipif(not WSL_AVAILABLE, reason="WSL2 + tmux não disponíveis")
@pytest.mark.asyncio
async def test_send_command_e_wait_for_sentinel_detecta_echo(
    broker: WSLTmuxBroker,
) -> None:
    session = "jump-runner-test-2"
    _kill_session(session)
    try:
        await broker.create_session(session)
        await broker.send_command(session, "echo AGENT_DONE:abc-001")
        ok = await broker.wait_for_sentinel(
            session,
            sentinel="AGENT_DONE:abc-001",
            timeout_s=10,
            heartbeat_s=2,
        )
        assert ok is True
    finally:
        _kill_session(session)


@pytest.mark.skipif(not WSL_AVAILABLE, reason="WSL2 + tmux não disponíveis")
@pytest.mark.asyncio
async def test_wait_for_sentinel_timeout_quando_nada_chega(broker: WSLTmuxBroker) -> None:
    session = "jump-runner-test-3"
    _kill_session(session)
    try:
        await broker.create_session(session)
        # Nenhum comando enviado; sentinel jamais aparecerá
        ok = await broker.wait_for_sentinel(
            session,
            sentinel="AGENT_DONE:never",
            timeout_s=2,
            heartbeat_s=1,
        )
        assert ok is False
    finally:
        _kill_session(session)
