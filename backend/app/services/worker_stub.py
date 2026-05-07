"""Worker stub — substitui o worker real até F2.6 estar disponível.

Comportamento: quando uma Proposal é uploadada com `STUB_WORKER_ENABLED=true`
(default em dev), uma task asyncio é agendada para:
  1. esperar STUB_WORKER_DELAY_S segundos (default 6)
  2. mudar Proposal.status para 'extracted'
  3. criar Baseline draft com payload simulado e ~6 Deliverables placeholder
  4. atualizar AgentRunLog para DONE
  5. emitir evento SSE 'proposal_extracted' para o GP

O frontend depende desse comportamento honesto para a UX da F3.3 funcionar.
Em F2.6 quando o worker real assumir, basta `STUB_WORKER_ENABLED=false`.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import (
    AgentRunLog,
    AgentRunStatus,
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliverableComplexity,
    Project,
    Proposal,
    ProposalStatus,
)
from app.notifications.sse import emit_to_user

log = get_logger("worker_stub")


def is_enabled() -> bool:
    return os.environ.get("STUB_WORKER_ENABLED", "true").lower() in ("1", "true", "yes")


def delay_seconds() -> int:
    try:
        return int(os.environ.get("STUB_WORKER_DELAY_S", "6"))
    except ValueError:
        return 6


def _build_simulated_baseline_payload(proposal: Proposal, project: Project) -> dict:
    return {
        "_simulated_by_stub": True,
        "client_name": project.client_name,
        "project_name": project.name,
        "summary": (
            f"Baseline simulado pelo worker_stub para a proposta v{proposal.version} "
            f"de {project.client_name}. Ative o worker real (F2.6) para extração de produção."
        ),
        "phases": [
            {"phase_id": "fase-1", "name": "Convergência inicial", "deliverable_count": 2},
            {"phase_id": "fase-2", "name": "Escala", "deliverable_count": 2},
            {"phase_id": "fase-3", "name": "Fechamento", "deliverable_count": 2},
        ],
        "key_premises": [
            "Stub: confirmar premissas com a proposta real antes de ativar",
        ],
        # Auditoria — sub-cabeçalho da revisão (F3.5.7)
        "audit": {
            "source_proposal_filename": proposal.original_filename,
            "source_proposal_version": proposal.version,
            "extracted_at": datetime.now(UTC).isoformat(),
            "engine": "stub",
            "route": "stub",
            "confidence_score": 0.62,  # placeholder — agente real reportará
        },
    }


def _stub_deliverables(baseline_id: uuid.UUID) -> list[Deliverable]:
    """6 deliverables placeholder distribuídos em 3 fases."""
    items = [
        ("d-001", "Migração rotina A → PySpark/Databricks", "fase-1", DeliverableComplexity.LOW),
        ("d-002", "Migração rotina B → PySpark/Databricks", "fase-1", DeliverableComplexity.LOW),
        ("d-003", "Migração rotina C com lógica intermediária", "fase-2", DeliverableComplexity.MEDIUM),
        ("d-004", "Migração rotina D com lógica intermediária", "fase-2", DeliverableComplexity.MEDIUM),
        ("d-005", "Migração rotina E (alta densidade lógica)", "fase-3", DeliverableComplexity.HIGH),
        ("d-006", "Documentação técnica final + handover", "fase-3", DeliverableComplexity.MEDIUM),
    ]
    return [
        Deliverable(
            baseline_id=baseline_id,
            code=code,
            title=title,
            phase=phase,
            complexity=complexity,
            source_excerpt=(
                f"[STUB] Trecho simulado da proposta para o entregável {code}. "
                f"Em produção, o agente leitor preenche este campo com a citação "
                f"literal da proposta original."
            ),
            order_index=i,
        )
        for i, (code, title, phase, complexity) in enumerate(items)
    ]


async def _process(proposal_id: uuid.UUID, run_id: str | None) -> None:
    await asyncio.sleep(delay_seconds())
    async with SessionLocal() as db:  # type: AsyncSession
        proposal = await db.get(Proposal, proposal_id)
        if not proposal:
            log.warning("worker_stub.proposal_missing", proposal_id=str(proposal_id))
            return
        if proposal.status != ProposalStatus.PENDING_EXTRACTION:
            log.info(
                "worker_stub.skipped",
                proposal_id=str(proposal_id),
                status=proposal.status.value,
            )
            return

        project = await db.get(Project, proposal.project_id)
        if not project:
            log.warning("worker_stub.project_missing", proposal_id=str(proposal_id))
            return

        baseline = Baseline(
            project_id=project.id,
            proposal_id=proposal.id,
            status=BaselineStatus.DRAFT,
            payload=_build_simulated_baseline_payload(proposal, project),
        )
        db.add(baseline)
        await db.flush()

        for deliv in _stub_deliverables(baseline.id):
            db.add(deliv)

        proposal.status = ProposalStatus.EXTRACTED

        if run_id:
            existing = (
                await db.execute(select(AgentRunLog).where(AgentRunLog.run_id == run_id))
            ).scalar_one_or_none()
            if existing and existing.status not in (
                AgentRunStatus.DONE,
                AgentRunStatus.FAILED,
                AgentRunStatus.EXPIRED,
            ):
                existing.status = AgentRunStatus.DONE
                existing.engine_used = "stub"
                existing.route_used = "stub"
                existing.duration_s = float(delay_seconds())
                existing.worker_id = "stub-worker"
                existing.completed_at = datetime.now(UTC)
                existing.attempts = [{"engine": "stub", "route": "stub", "success": True}]

        await db.commit()

        emit_to_user(
            project.gp_user_id,
            "proposal_extracted",
            {
                "proposal_id": str(proposal.id),
                "project_id": str(project.id),
                "baseline_id": str(baseline.id),
            },
        )
        log.info(
            "worker_stub.completed",
            proposal_id=str(proposal_id),
            baseline_id=str(baseline.id),
        )


def schedule_extraction(proposal_id: uuid.UUID, run_id: str | None = None) -> None:
    """Agenda a extração simulada se o stub estiver habilitado."""
    if not is_enabled():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # sem loop ativo (ex: contexto de testes síncronos)
    loop.create_task(_process(proposal_id, run_id))
