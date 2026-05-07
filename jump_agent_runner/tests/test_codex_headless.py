"""Testes do CodexHeadlessRoute — análogos ao do Claude.

Estratégia idêntica:
- _classify_failure: padrões de erro específicos do Codex (codex login, etc).
- windows_to_wsl: conversão de path determinística.
- is_available e execute usam wsl.exe; substituível por sys.executable em CI.
- Smoke real em test_codex_headless_real.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.routes.codex_headless import (
    CodexHeadlessRoute,
    windows_to_wsl,
)
from jump_agent_runner.types import AgentTask, Engine, FailureReason, Route


@pytest.fixture
def stream():
    import io

    return io.StringIO()


@pytest.fixture
def observer(tmp_path: Path, stream) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=stream)


# ---- windows_to_wsl ----


def test_windows_to_wsl_traduz_caminho_padrao() -> None:
    assert windows_to_wsl("C:\\Users\\chris\\foo") == "/mnt/c/Users/chris/foo"


def test_windows_to_wsl_lower_case_drive_letter() -> None:
    assert windows_to_wsl("D:\\bar") == "/mnt/d/bar"


def test_windows_to_wsl_path_object() -> None:
    p = Path("C:/Users/chris/x.json")
    assert windows_to_wsl(p) == "/mnt/c/Users/chris/x.json"


def test_windows_to_wsl_idempotente_em_path_wsl() -> None:
    assert windows_to_wsl("/mnt/c/foo") == "/mnt/c/foo"
    assert windows_to_wsl("/home/chris/x") == "/home/chris/x"


# ---- _classify_failure ----


def test_codex_classify_login_required_codex_login_message() -> None:
    f = CodexHeadlessRoute._classify_failure(
        returncode=1,
        stderr="Error: Not logged in. Run `codex login` to authenticate.",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.LOGIN_REQUIRED


def test_codex_classify_quota_exceeded() -> None:
    f = CodexHeadlessRoute._classify_failure(
        returncode=1,
        stderr="429 Too Many Requests: rate limit exceeded",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.QUOTA_EXCEEDED


def test_codex_classify_execution_error_quando_returncode_nao_zero() -> None:
    f = CodexHeadlessRoute._classify_failure(
        returncode=2,
        stderr="codex: invalid argument",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.EXECUTION_ERROR


def test_codex_classify_returns_none_quando_tudo_ok() -> None:
    f = CodexHeadlessRoute._classify_failure(
        returncode=0,
        stderr="",
        stdout="AGENT_DONE:r1",
        sentinel=True,
        artifact_written=True,
    )
    assert f is None


# ---- is_available e execute ----


@pytest.mark.asyncio
async def test_is_available_retorna_false_se_wsl_nao_existe(observer: Observer) -> None:
    route = CodexHeadlessRoute(observer=observer, wsl_executable="C:/inexistente/wsl.exe")
    ok, reason = await route.is_available()
    assert ok is False
    assert reason == FailureReason.BROKER_UNAVAILABLE


@pytest.mark.asyncio
async def test_execute_sem_wsl_retorna_broker_unavailable(
    tmp_path: Path, observer: Observer
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    task = AgentTask(
        run_id="r-x",
        prompt="x",
        output_path=workspace / "out.json",
        schema_hint=None,
        workspace=workspace,
        timeout_hard_s=10,
        heartbeat_s=2,
    )
    route = CodexHeadlessRoute(observer=observer, wsl_executable="C:/nada/wsl.exe")
    log = await route.execute(task)
    assert log.engine == Engine.CODEX
    assert log.route == Route.HEADLESS
    assert log.success is False
    assert log.failure_reason == FailureReason.BROKER_UNAVAILABLE


@pytest.mark.asyncio
async def test_execute_com_subprocess_fake_que_grava_arquivo_e_emite_sentinel(
    tmp_path: Path, observer: Observer
) -> None:
    """Mesmo padrão do Claude: usa Python como stand-in do agente."""
    import json

    workspace = tmp_path / "ws"
    workspace.mkdir()
    out = workspace / "out.json"

    fake_script = tmp_path / "fake_codex.py"
    payload = json.dumps({"engine": "codex", "ok": True})
    fake_script.write_text(
        f"""
import pathlib
out = pathlib.Path(r'''{out}''')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text({payload!r}, encoding='utf-8')
print('AGENT_DONE:r-codex-fake')
""".lstrip(),
        encoding="utf-8",
    )

    from jump_agent_runner.prompt import sentinel_for
    from jump_agent_runner.routes._subprocess import run_with_heartbeat

    cmd = [sys.executable, str(fake_script)]
    outcome = await run_with_heartbeat(
        cmd,
        cwd=workspace,
        timeout_s=10,
        heartbeat_s=2,
        sentinel_pattern=sentinel_for("r-codex-fake"),
        observer=observer,
        event_name="headless_heartbeat",
        event_payload={"engine": "codex", "run_id": "r-codex-fake"},
    )

    assert outcome.returncode == 0
    assert outcome.sentinel_observed is True
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8")) == {"engine": "codex", "ok": True}
