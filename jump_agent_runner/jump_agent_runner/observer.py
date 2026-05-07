"""Observer — emite eventos estruturados em duas saídas simultâneas.

Spec: 02_jump_agent_runner_spec.md, seção 10.

- stdout: formatação humana com timestamp local
- JSONL persistente: ~/.jump-runner/logs/{date}.jsonl

Threadsafe a nível de arquivo (cada `emit` abre, escreve, fecha em modo append).
Múltiplos processos rodando o runner gravam no mesmo dia sem corromper o JSONL.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import threading
from enum import Enum as _Enum
from pathlib import Path
from typing import Any, TextIO

DEFAULT_LOG_DIR = Path.home() / ".jump-runner" / "logs"

# Templates humanos por evento. Aceitam {key} de payload; se faltar, formata
# com ":<valor padrão>" gracioso.
_HUMAN_TEMPLATES: dict[str, str] = {
    "provider_selected": "Provider selected: {engine} via {route}",
    "headless_unavailable": "Headless unavailable: {engine} ({reason})",
    "headless_failed": "Headless failed: {engine} ({reason}) — {detail}",
    "broker_session_starting": "Starting broker session {name} (backend: {backend})",
    "broker_session_created": "Broker session created: {name}",
    "broker_already_logged_in": "Broker already logged in: {engine} ({name})",
    "user_login_required": "User login required for {engine} broker ({session})",
    "login_confirmed": "Login confirmed for {engine} broker ({session})",
    "task_dispatched": "Task dispatched (run_id={run_id}) → {output_path}",
    "broker_heartbeat": "Heartbeat: broker has progress, no artifact yet ({elapsed_s}s elapsed)",
    "sentinel_observed": "Sentinel observed: {sentinel} ({session})",
    "artifact_accepted": "Artifact accepted from {path} (recovered_from_relay={recovered_from_relay})",
    "artifact_rejected": "Artifact rejected: {reason} — {detail}",
    "provider_failover": "Provider failover: {from_engine} → {to_engine} ({reason})",
    "run_complete": "Run complete (engine={engine_used}, route={route_used}, "
    "duration={duration_s}s, attempts={attempts_count})",
}


class Observer:
    """Emite eventos canônicos em stdout (humano) e JSONL persistente."""

    def __init__(
        self,
        log_dir: Path | None = None,
        stream: TextIO | None = None,
        clock: Any = None,
    ) -> None:
        self._log_dir = log_dir or DEFAULT_LOG_DIR
        self._stream = stream if stream is not None else sys.stdout
        # `clock` é um callable opcional retornando datetime.datetime — facilita testes
        self._clock = clock or (lambda: _dt.datetime.now(_dt.UTC))
        self._lock = threading.Lock()

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    def current_log_file(self) -> Path:
        date = self._clock().date().isoformat()
        return self._log_dir / f"{date}.jsonl"

    def emit(self, event: str, **payload: Any) -> None:
        """Emite um evento. Payload é serializado em JSON (objects → str)."""
        ts = self._clock()
        record: dict[str, Any] = {
            "ts": ts.isoformat(),
            "event": event,
            **payload,
        }
        line = json.dumps(record, default=_json_default, ensure_ascii=False)

        with self._lock:
            self._write_jsonl(line)
            self._write_human(ts, event, payload)

    def _write_jsonl(self, line: str) -> None:
        path = self.current_log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # `os.O_APPEND` em POSIX dá atomicidade até PIPE_BUF; em Windows o
        # mode "a" do Python já serializa por arquivo no mesmo processo.
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")

    def _write_human(self, ts: _dt.datetime, event: str, payload: dict[str, Any]) -> None:
        template = _HUMAN_TEMPLATES.get(event)
        formatted = {k: _human_value(v) for k, v in payload.items()}
        try:
            if template is not None:
                msg = template.format_map(_DefaultDict(formatted))
            else:
                msg = f"{event} {formatted}" if formatted else event
        except Exception:  # noqa: BLE001
            msg = f"{event} {formatted}"
        local = ts.astimezone().strftime("%H:%M:%S")
        try:
            self._stream.write(f"[{local}] {msg}\n")
            self._stream.flush()
        except (BrokenPipeError, ValueError):
            # stdout fechado — engole; o JSONL ainda foi gravado
            pass


class _DefaultDict(dict):
    """Dict que retorna `<missing:KEY>` em format_map quando a chave falta."""

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return f"<missing:{key}>"


def _json_default(obj: Any) -> Any:
    """Coerção segura para JSON: Path → str, Enum → value, fallback → repr."""
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, os.PathLike):
        return str(obj)
    return repr(obj)


def _human_value(v: Any) -> Any:
    """Coerção para a saída humana: Enum → value (curto), Path → str, resto inalterado."""
    if isinstance(v, _Enum):
        return v.value
    if isinstance(v, os.PathLike):
        return str(v)
    return v
