"""Testes do CLI `jump-runner`."""
from __future__ import annotations

from pathlib import Path

import pytest

from jump_agent_runner.cli import main as cli_main


def test_cli_login_confirm_engine_invalido(capsys) -> None:
    """argparse rejeita engines fora de {claude, codex} com SystemExit(2)."""
    with pytest.raises(SystemExit) as exc:
        cli_main.main(["login-confirm", "gpt-5"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


def test_cli_login_confirm_remove_sentinela(tmp_path: Path, monkeypatch, capsys) -> None:
    pending_dir = tmp_path / ".jump-runner"
    pending_dir.mkdir()
    sentinel = pending_dir / "login-pending-claude"
    sentinel.write_text("project-claude", encoding="utf-8")

    monkeypatch.setattr(cli_main, "LOGIN_PENDING_DIR", pending_dir)
    rc = cli_main.main(["login-confirm", "claude"])
    assert rc == 0
    assert not sentinel.exists()
    out = capsys.readouterr()
    assert "login confirmado para claude" in out.out


def test_cli_login_confirm_idempotente_quando_nao_ha_pendente(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli_main, "LOGIN_PENDING_DIR", tmp_path / "vazio")
    rc = cli_main.main(["login-confirm", "codex"])
    assert rc == 0
    out = capsys.readouterr()
    assert "nenhum login pendente" in out.out


def test_cli_help_exits_2_quando_nenhum_subcommand() -> None:
    """argparse com subparsers `required=True` aborta com SystemExit."""
    with pytest.raises(SystemExit) as exc:
        cli_main.main([])
    assert exc.value.code != 0
