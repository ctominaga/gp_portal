"""AgentRunner — fallback entre engines (Claude ↔ Codex).

Spec: 02_jump_agent_runner_spec.md, seção 9 (política) e 2 (modelo).

Fluxo:
    1. Tenta `primary.run(task)`.
    2. Se falhar com motivo em PROVIDER_TO_PROVIDER_REASONS, monta
       `continuation_hint` rico com o histórico das tentativas e tenta
       `secondary.run(task_com_hint)`.
    3. Retorna AgentResult com a lista combinada de tentativas.

Limpeza de arquivos temporários do workspace acontece DEPOIS de retornar
o resultado (mantém preservados em caso de falha para inspeção humana).
"""
from __future__ import annotations

import time
from dataclasses import replace

from .observer import Observer
from .policy import PROVIDER_TO_PROVIDER_REASONS
from .protocols import AgentProvider
from .types import AgentResult, AgentTask


class AgentRunner:
    def __init__(
        self,
        primary: AgentProvider,
        secondary: AgentProvider,
        observer: Observer,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.observer = observer

    async def run(self, task: AgentTask) -> AgentResult:
        run_started = time.monotonic()

        primary_result = await self.primary.run(task)
        if primary_result.success:
            self._emit_complete(primary_result, run_started)
            return primary_result

        if primary_result.failure_reason not in PROVIDER_TO_PROVIDER_REASONS:
            # Não é falha que justifica fallback — devolve resultado primário
            self._emit_complete(primary_result, run_started)
            return primary_result

        # ---- fallback ----
        self.observer.emit(
            "provider_failover",
            from_engine=self.primary.engine.value,
            to_engine=self.secondary.engine.value,
            reason=primary_result.failure_reason.value if primary_result.failure_reason else "unknown",
        )

        hint = self._build_continuation_hint(task, primary_result)
        secondary_task = replace(task, continuation_hint=hint)
        secondary_result = await self.secondary.run(secondary_task)

        # Combinamos as tentativas dos dois providers
        combined_attempts = list(primary_result.attempts) + list(secondary_result.attempts)
        merged = AgentResult(
            success=secondary_result.success,
            engine_used=secondary_result.engine_used,
            route_used=secondary_result.route_used,
            artifact_path=secondary_result.artifact_path,
            artifact_data=secondary_result.artifact_data,
            failure_reason=secondary_result.failure_reason,
            failure_detail=secondary_result.failure_detail,
            attempts=combined_attempts,
            duration_s=time.monotonic() - run_started,
        )
        self._emit_complete(merged, run_started)
        return merged

    # -------- helpers --------

    def _emit_complete(self, result: AgentResult, run_started: float) -> None:
        self.observer.emit(
            "run_complete",
            success=result.success,
            engine_used=result.engine_used.value if result.engine_used else None,
            route_used=result.route_used.value if result.route_used else None,
            duration_s=int(time.monotonic() - run_started),
            attempts_count=len(result.attempts),
        )

    @staticmethod
    def _build_continuation_hint(task: AgentTask, primary_result: AgentResult) -> str:
        lines = [
            f"O engine {primary_result.engine_used.value if primary_result.engine_used else '?'} "
            f"falhou com {primary_result.failure_reason.value if primary_result.failure_reason else '?'}.",
            f"Detalhe: {(primary_result.failure_detail or '')[:200]}",
            "",
            "Tentativas anteriores:",
        ]
        for i, att in enumerate(primary_result.attempts, start=1):
            lines.append(
                f"  [{i}] engine={att.engine.value} route={att.route.value} "
                f"success={att.success} reason={att.failure_reason.value if att.failure_reason else '-'} "
                f"duration={att.duration_s:.1f}s"
            )
        existing = "sim" if task.output_path.exists() else "não"
        lines.append("")
        lines.append(f"Output_path ({task.output_path}) já existe: {existing}.")
        if task.output_path.exists():
            lines.append("Aproveite o conteúdo parcial em vez de recomeçar do zero.")
        return "\n".join(lines)
