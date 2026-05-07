"""Testes do Observer — saída JSONL e formatação humana em stdout."""
from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path

import pytest

from jump_agent_runner.observer import Observer
from jump_agent_runner.types import Engine, FailureReason, Route


@pytest.fixture
def fixed_clock():
    """2026-05-07 14:30:00 UTC fixo, idempotente entre chamadas."""
    return lambda: dt.datetime(2026, 5, 7, 14, 30, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def stream():
    return io.StringIO()


@pytest.fixture
def observer(tmp_path: Path, stream, fixed_clock) -> Observer:
    return Observer(log_dir=tmp_path / "logs", stream=stream, clock=fixed_clock)


def test_emit_grava_jsonl_em_arquivo_do_dia(observer: Observer) -> None:
    observer.emit("provider_selected", engine=Engine.CLAUDE, route=Route.HEADLESS, run_id="r1")

    path = observer.current_log_file()
    assert path.name == "2026-05-07.jsonl"
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["event"] == "provider_selected"
    assert record["engine"] == "claude"
    assert record["route"] == "headless"
    assert record["run_id"] == "r1"
    assert record["ts"].startswith("2026-05-07T14:30:00")


def test_emit_acumula_eventos_um_por_linha(observer: Observer) -> None:
    observer.emit("provider_selected", engine=Engine.CLAUDE, route=Route.HEADLESS, run_id="r1")
    observer.emit("artifact_accepted", path="/tmp/out.json", recovered_from_relay=False)
    observer.emit("run_complete", success=True, engine_used=Engine.CODEX, route_used=Route.BROKER,
                  duration_s=42.5, attempts_count=2)

    lines = observer.current_log_file().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    events = [json.loads(line)["event"] for line in lines]
    assert events == ["provider_selected", "artifact_accepted", "run_complete"]


def test_emit_escreve_mensagem_humana_no_stream(observer: Observer, stream: io.StringIO) -> None:
    observer.emit("provider_selected", engine=Engine.CLAUDE, route=Route.HEADLESS, run_id="r1")

    out = stream.getvalue()
    # Apenas confirma que tem timestamp [HH:MM:SS] e a mensagem reconhecível
    assert "Provider selected:" in out
    assert "claude" in out
    assert "headless" in out
    assert out.startswith("[")  # timestamp local


def test_emit_evento_desconhecido_nao_quebra(observer: Observer) -> None:
    observer.emit("evento_inventado", arg1="x", arg2=42)
    record = json.loads(observer.current_log_file().read_text(encoding="utf-8").strip())
    assert record["event"] == "evento_inventado"
    assert record["arg1"] == "x"
    assert record["arg2"] == 42


def test_emit_serializa_path_e_enum(observer: Observer, tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    observer.emit("artifact_rejected", reason=FailureReason.ARTIFACT_INVALID, path=p, detail="bla")
    record = json.loads(observer.current_log_file().read_text(encoding="utf-8").strip())
    assert record["reason"] == "artifact_invalid"
    assert record["path"] == str(p)


def test_template_com_chave_faltando_nao_levanta(observer: Observer, stream: io.StringIO) -> None:
    """Template `provider_selected` é `Provider selected: {engine} via {route}`.
    Se omitirmos `route`, deve aparecer `<missing:route>` em vez de levantar."""
    observer.emit("provider_selected", engine=Engine.CLAUDE)
    out = stream.getvalue()
    assert "Provider selected: claude via <missing:route>" in out
    # JSONL ainda deve estar bem formado
    record = json.loads(observer.current_log_file().read_text(encoding="utf-8").strip())
    assert record["engine"] == "claude"


def test_arquivo_jsonl_e_criado_se_log_dir_nao_existe(tmp_path: Path, fixed_clock, stream) -> None:
    log_dir = tmp_path / "deep" / "logs"  # não existe ainda
    observer = Observer(log_dir=log_dir, stream=stream, clock=fixed_clock)
    observer.emit("run_complete", success=True, engine_used="claude", route_used="headless",
                  duration_s=1, attempts_count=1)
    assert (log_dir / "2026-05-07.jsonl").exists()
