"""Helpers compartilhados entre routes headless: spawn de subprocess com heartbeat e
hard timeout. Não depende de nenhuma route específica.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..observer import Observer


@dataclass(frozen=True)
class SubprocessOutcome:
    stdout: str
    stderr: str
    returncode: int
    sentinel_observed: bool
    timed_out: bool
    duration_s: float


def resolve_executable(name: str) -> str | None:
    """`shutil.which` consciente de Windows (.cmd / .exe via PATHEXT)."""
    return shutil.which(name)


async def quick_check(cmd: Sequence[str], timeout_s: int = 5) -> tuple[bool, str]:
    """Roda um comando trivial (sem heartbeat) e retorna (success, output_combinado).

    Usado para sondas leves como `claude --version`. Mata e retorna False se exceder timeout.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (OSError, FileNotFoundError) as exc:
        return False, str(exc)

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        with _suppress_exceptions():
            await proc.wait()
        return False, "timeout"

    output = (stdout or b"").decode("utf-8", errors="replace") + (stderr or b"").decode(
        "utf-8", errors="replace"
    )
    return proc.returncode == 0, output


@contextmanager
def _suppress_exceptions():
    try:
        yield
    except Exception:  # noqa: BLE001
        pass


async def run_with_heartbeat(
    cmd: Sequence[str],
    *,
    cwd: Path,
    timeout_s: int,
    heartbeat_s: int,
    sentinel_pattern: str,
    observer: Observer,
    event_name: str,
    event_payload: dict[str, object],
    env: dict[str, str] | None = None,
) -> SubprocessOutcome:
    """Roda `cmd` em subprocess assíncrono. A cada `heartbeat_s` sem progresso
    visível, emite `event_name` no observer.

    `sentinel_pattern` (string literal) é procurado em stdout — se encontrado,
    `sentinel_observed=True` no resultado, mas o processo NÃO é interrompido
    (deixa terminar naturalmente para coletar stderr/returncode).

    Em hard timeout, mata o processo e retorna `timed_out=True`.
    """
    started = time.monotonic()
    full_env = {**os.environ, **(env or {})}

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=full_env,
    )

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    sentinel_observed = False

    async def _drain(stream: asyncio.StreamReader | None, sink: list[str]) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            sink.append(chunk.decode("utf-8", errors="replace"))

    drain_out = asyncio.create_task(_drain(proc.stdout, stdout_chunks))
    drain_err = asyncio.create_task(_drain(proc.stderr, stderr_chunks))

    timed_out = False
    last_total_bytes = 0
    deadline = started + timeout_s

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                proc.kill()
                break

            try:
                await asyncio.wait_for(proc.wait(), timeout=min(heartbeat_s, remaining))
                break  # process exited
            except TimeoutError:
                # heartbeat — checa progresso
                now = time.monotonic()
                total = sum(len(c) for c in stdout_chunks) + sum(len(c) for c in stderr_chunks)
                bytes_new = total - last_total_bytes
                last_total_bytes = total
                observer.emit(
                    event_name,
                    bytes_new=bytes_new,
                    elapsed_s=int(now - started),
                    **event_payload,
                )
    finally:
        await asyncio.gather(drain_out, drain_err, return_exceptions=True)

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    sentinel_observed = sentinel_pattern in stdout

    return SubprocessOutcome(
        stdout=stdout,
        stderr=stderr,
        returncode=proc.returncode if proc.returncode is not None else -1,
        sentinel_observed=sentinel_observed,
        timed_out=timed_out,
        duration_s=time.monotonic() - started,
    )
