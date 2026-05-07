"""Base genérica de Provider — orquestra headless → broker para um engine.

Spec: 02_jump_agent_runner_spec.md, seções 2 e 9.

Recebe duas rotas (headless e broker) e o ArtifactValidator. Tenta headless
primeiro; se falhar com motivo em HEADLESS_TO_BROKER_REASONS, tenta broker.
Antes do broker, monta `continuation_hint` com o histórico, se houver trabalho
parcial.

Retorna `AgentResult` com a lista de `AttemptLog` produzida e o resultado da
validação aplicada à última tentativa bem-sucedida.
"""
from __future__ import annotations

import time
from dataclasses import replace

from ..artifact import ArtifactValidator
from ..observer import Observer
from ..policy import HEADLESS_TO_BROKER_REASONS
from ..protocols import AgentRoute
from ..types import AgentResult, AgentTask, AttemptLog, Engine, FailureReason


class _BaseProvider:
    engine: Engine

    def __init__(
        self,
        engine: Engine,
        headless: AgentRoute,
        broker: AgentRoute,
        observer: Observer,
        validator: ArtifactValidator | None = None,
    ) -> None:
        self.engine = engine
        self.headless = headless
        self.broker = broker
        self.observer = observer
        self.validator = validator or ArtifactValidator()

    async def run(self, task: AgentTask) -> AgentResult:
        attempts: list[AttemptLog] = []
        run_started = time.monotonic()

        # ---- 1. headless ----
        self.observer.emit(
            "provider_selected",
            engine=self.engine.value,
            route="headless",
            run_id=task.run_id,
        )
        ok, reason = await self.headless.is_available()
        if not ok:
            self.observer.emit(
                "headless_unavailable",
                engine=self.engine.value,
                reason=reason.value if reason else "unknown",
            )
            headless_log: AttemptLog | None = None
        else:
            headless_log = await self.headless.execute(task)
            attempts.append(headless_log)

            if headless_log.success:
                # validar artefato
                relay_text = headless_log.notes or ""
                validation = self.validator.validate(
                    task, relay=relay_text, sentinel_observed=headless_log.sentinel_observed
                )
                if validation.accepted:
                    self.observer.emit(
                        "artifact_accepted",
                        path=str(validation.artifact_path),
                        recovered_from_relay=validation.recovered_from_relay,
                    )
                    return AgentResult(
                        success=True,
                        engine_used=self.engine,
                        route_used=headless_log.route,
                        artifact_path=validation.artifact_path,
                        artifact_data=validation.artifact_data,
                        failure_reason=None,
                        failure_detail=None,
                        attempts=attempts,
                        duration_s=time.monotonic() - run_started,
                    )
                else:
                    self.observer.emit(
                        "artifact_rejected",
                        reason=validation.failure_reason.value if validation.failure_reason else "unknown",
                        detail=validation.failure_detail or "",
                    )
                    # Atualiza headless_log para refletir falha do validator
                    failed_log = replace(
                        headless_log,
                        success=False,
                        failure_reason=validation.failure_reason,
                        notes=(validation.failure_detail or "")[-500:],
                    )
                    attempts[-1] = failed_log
                    headless_log = failed_log

            # tentar broker?
            should_fallback = (
                headless_log is not None
                and headless_log.failure_reason in HEADLESS_TO_BROKER_REASONS
            )
            if not should_fallback:
                return self._make_final_result(
                    task,
                    success=False,
                    failed_log=headless_log,
                    attempts=attempts,
                    run_started=run_started,
                )

        # ---- 2. broker ----
        ok, reason = await self.broker.is_available()
        if not ok:
            return self._make_final_result(
                task,
                success=False,
                failed_log=None,
                attempts=attempts,
                run_started=run_started,
                fallback_reason=reason or FailureReason.BROKER_UNAVAILABLE,
            )

        # Monta continuation_hint para o broker se houver trabalho parcial
        continuation = None
        if headless_log is not None and (
            headless_log.artifact_written or headless_log.notes
        ):
            continuation = (
                f"A tentativa anterior (headless {self.engine.value}) falhou com "
                f"{headless_log.failure_reason.value if headless_log.failure_reason else 'desconhecido'}. "
                f"Notas finais do relay/stderr: {headless_log.notes[:200]}"
            )

        broker_task = (
            replace(task, continuation_hint=continuation) if continuation else task
        )
        broker_log = await self.broker.execute(broker_task)
        attempts.append(broker_log)

        if not broker_log.success:
            return self._make_final_result(
                task,
                success=False,
                failed_log=broker_log,
                attempts=attempts,
                run_started=run_started,
            )

        relay_text = broker_log.notes or ""
        validation = self.validator.validate(
            task, relay=relay_text, sentinel_observed=broker_log.sentinel_observed
        )
        if validation.accepted:
            self.observer.emit(
                "artifact_accepted",
                path=str(validation.artifact_path),
                recovered_from_relay=validation.recovered_from_relay,
            )
            return AgentResult(
                success=True,
                engine_used=self.engine,
                route_used=broker_log.route,
                artifact_path=validation.artifact_path,
                artifact_data=validation.artifact_data,
                failure_reason=None,
                failure_detail=None,
                attempts=attempts,
                duration_s=time.monotonic() - run_started,
            )

        self.observer.emit(
            "artifact_rejected",
            reason=validation.failure_reason.value if validation.failure_reason else "unknown",
            detail=validation.failure_detail or "",
        )
        failed_broker_log = replace(
            broker_log,
            success=False,
            failure_reason=validation.failure_reason,
            notes=(validation.failure_detail or "")[-500:],
        )
        attempts[-1] = failed_broker_log
        return self._make_final_result(
            task,
            success=False,
            failed_log=failed_broker_log,
            attempts=attempts,
            run_started=run_started,
        )

    def _make_final_result(
        self,
        task: AgentTask,
        *,
        success: bool,
        failed_log: AttemptLog | None,
        attempts: list[AttemptLog],
        run_started: float,
        fallback_reason: FailureReason | None = None,
    ) -> AgentResult:
        reason = (
            failed_log.failure_reason
            if failed_log and failed_log.failure_reason
            else fallback_reason or FailureReason.BROKER_UNAVAILABLE
        )
        detail = failed_log.notes if failed_log else "broker indisponível"
        return AgentResult(
            success=success,
            engine_used=self.engine if attempts else None,
            route_used=attempts[-1].route if attempts else None,
            artifact_path=task.output_path if task.output_path.exists() else None,
            artifact_data=None,
            failure_reason=reason,
            failure_detail=detail,
            attempts=attempts,
            duration_s=time.monotonic() - run_started,
        )
