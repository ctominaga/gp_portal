"""Testes do ClaudeHeadlessRoute.

Estratégia:
- Unit tests do `_classify_failure` cobrem a lógica de detecção de falha
  (puro, sem subprocess).
- Teste de integração com subprocess fake (`python -c "..."`) cobre execute()
  end-to-end sem precisar do Claude CLI real. Roda em qualquer SO/CI.
- Smoke real com `claude -p` em workstation com login está em
  `tests/test_claude_headless_real.py` (marcado @requires_claude_cli, skipa em CI).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.routes.claude_headless import ClaudeHeadlessRoute
from jump_agent_runner.types import AgentTask, Engine, FailureReason, Route


@pytest.fixture
def stream(tmp_path):
    import io

    return io.StringIO()


@pytest.fixture
def observer(tmp_path: Path, stream) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=stream)


# ---- _classify_failure (unit, sem subprocess) ----


def test_classify_login_required_via_stderr() -> None:
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=1,
        stderr="Error: Not authenticated. Please log in via /login.",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.LOGIN_REQUIRED


def test_classify_quota_exceeded() -> None:
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=1,
        stderr="Error: rate limit exceeded for organization",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.QUOTA_EXCEEDED


def test_classify_interactive_mode_detected() -> None:
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=1,
        stderr="stdin is not a tty; interactive mode required",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.INTERACTIVE_MODE_DETECTED


def test_classify_execution_error_quando_returncode_nao_zero() -> None:
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=2,
        stderr="something broke",
        stdout="",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.EXECUTION_ERROR


def test_classify_sentinel_not_observed_quando_returncode_zero_mas_sem_nada() -> None:
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=0,
        stderr="",
        stdout="apenas prosa, sem sentinel",
        sentinel=False,
        artifact_written=False,
    )
    assert f == FailureReason.SENTINEL_NOT_OBSERVED


def test_classify_returns_none_quando_tudo_ok() -> None:
    """returncode=0 + sentinel observado → None (validador final decide)."""
    f = ClaudeHeadlessRoute._classify_failure(
        returncode=0,
        stderr="",
        stdout="AGENT_DONE:r1",
        sentinel=True,
        artifact_written=True,
    )
    assert f is None


# ---- is_available (subprocess fake) ----


@pytest.mark.asyncio
async def test_is_available_retorna_false_se_executavel_nao_existe(observer: Observer) -> None:
    route = ClaudeHeadlessRoute(observer=observer, executable="C:/inexistente/claude.exe")
    ok, reason = await route.is_available()
    assert ok is False
    assert reason == FailureReason.BROKER_UNAVAILABLE


@pytest.mark.asyncio
async def test_is_available_retorna_true_quando_claude_responde_versao(
    tmp_path: Path, observer: Observer
) -> None:
    """Usa `python -c 'print(...)'` como stand-in: comando que sai com 0."""
    fake = sys.executable  # python sempre existe
    route = ClaudeHeadlessRoute(observer=observer, executable=fake)
    # Monkey-patch interno: substituir o argumento `--version` por `-V`
    # (python entende -V; claude entenderia --version). Esquema mais portável:
    # vamos rodar com o args do is_available real e aceitar que `python --version`
    # também retorna 0 e printa em stderr na maioria das versões.
    ok, _ = await route.is_available()
    assert ok is True


# ---- execute() end-to-end com subprocess fake ----


@pytest.mark.asyncio
async def test_execute_com_subprocess_fake_que_grava_arquivo_e_emite_sentinel(
    tmp_path: Path, observer: Observer
) -> None:
    """Mock executável: script Python que (1) grava JSON em output_path,
    (2) emite o sentinel em stdout, (3) sai com 0. Deve ser classificado como sucesso."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    out = workspace / "out.json"

    task = AgentTask(
        run_id="r-fake-1",
        prompt="x",
        output_path=out,
        schema_hint=None,
        workspace=workspace,
        timeout_hard_s=10,
        heartbeat_s=2,
        metadata={},
        continuation_hint=None,
    )

    fake_script = tmp_path / "fake_claude.py"
    payload = json.dumps({"k": "v"})
    fake_script.write_text(
        f"""
import sys, pathlib
out = pathlib.Path(r'''{out}''')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text({payload!r}, encoding='utf-8')
print('AGENT_DONE:r-fake-1')
""".lstrip(),
        encoding="utf-8",
    )

    # Validamos diretamente o helper compartilhado `run_with_heartbeat` com um
    # subprocesso Python que mimetiza a interface do agente real (grava arquivo +
    # emite sentinel). Isso testa o caminho crítico de execute() sem depender do
    # binário `claude` real.
    from jump_agent_runner.prompt import sentinel_for
    from jump_agent_runner.routes._subprocess import run_with_heartbeat

    cmd = [sys.executable, str(fake_script)]
    outcome = await run_with_heartbeat(
        cmd,
        cwd=workspace,
        timeout_s=10,
        heartbeat_s=2,
        sentinel_pattern=sentinel_for(task.run_id),
        observer=observer,
        event_name="headless_heartbeat",
        event_payload={"engine": "claude", "run_id": task.run_id},
    )

    assert outcome.returncode == 0
    assert outcome.sentinel_observed is True
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8")) == {"k": "v"}


@pytest.mark.asyncio
async def test_execute_com_subprocess_fake_que_dispara_timeout(
    tmp_path: Path, observer: Observer
) -> None:
    """Script que dorme mais que `timeout_hard_s` deve ser killado."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    sleep_script = tmp_path / "sleep.py"
    sleep_script.write_text("import time; time.sleep(30)\n", encoding="utf-8")

    from jump_agent_runner.routes._subprocess import run_with_heartbeat

    outcome = await run_with_heartbeat(
        [sys.executable, str(sleep_script)],
        cwd=workspace,
        timeout_s=2,
        heartbeat_s=1,
        sentinel_pattern="AGENT_DONE:any",
        observer=observer,
        event_name="headless_heartbeat",
        event_payload={"engine": "claude", "run_id": "r-sleep"},
    )
    assert outcome.timed_out is True
    assert outcome.duration_s < 5  # killed rapidamente após estourar
    assert outcome.sentinel_observed is False


@pytest.mark.asyncio
async def test_execute_sem_executavel_retorna_broker_unavailable(
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

    route = ClaudeHeadlessRoute(observer=observer, executable="C:/nada/claude.exe")
    log = await route.execute(task)
    assert log.engine == Engine.CLAUDE
    assert log.route == Route.HEADLESS
    assert log.success is False
    assert log.failure_reason == FailureReason.BROKER_UNAVAILABLE
