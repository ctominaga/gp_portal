"""Stub do agente analyzer de reports — substitui o agente real até F2.6.

Quando um Report é submetido, agenda task asyncio que:
  1. espera STUB_ANALYZER_DELAY_S (default 4)
  2. cria 1 a 3 AIInsights baseados em heurísticas simples
  3. emite SSE 'report_insights_ready' para o GP

Schema canônico do payload em shared/schemas/report_insights.json.
Real worker (F2.6) reusa o mesmo task_type=report_analysis e mesmo schema.
"""
from __future__ import annotations

import asyncio
import os
import uuid

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import (
    OPEN_RISK_STATUSES,
    AIInsight,
    DeliveryProgress,
    InsightScope,
    PendingItem,
    PendingItemStatus,
    Project,
    Report,
    Risk,
    RiskLevel,
)
from app.notifications.sse import emit_to_user

log = get_logger("analyzer_stub")


def is_enabled() -> bool:
    return os.environ.get("STUB_ANALYZER_ENABLED", "true").lower() in ("1", "true", "yes")


def _delay_s() -> int:
    try:
        return int(os.environ.get("STUB_ANALYZER_DELAY_S", "4"))
    except ValueError:
        return 4


async def _process(report_id: uuid.UUID) -> None:
    await asyncio.sleep(_delay_s())
    async with SessionLocal() as db:
        report = await db.get(Report, report_id)
        if not report:
            return
        project = await db.get(Project, report.project_id)
        if not project:
            return

        # Heurísticas simples (real agente: prompt LLM contra report+contexto)
        insights: list[dict] = []
        progresses = list(
            (
                await db.execute(
                    select(DeliveryProgress).where(DeliveryProgress.report_id == report.id)
                )
            ).scalars().all()
        )
        deviations = sum(1 for p in progresses if p.deviation_flag)
        if deviations >= 2:
            insights.append({
                "kind": "schedule_drift",
                "severity": "high" if deviations >= 4 else "medium",
                "headline": f"{deviations} entregáveis com desvio de prazo",
                "detail": (
                    "Recomenda-se revisar a capacidade da squad e renegociar prazos com cliente "
                    "se o padrão se repetir nos próximos 2 reports."
                ),
                "evidence": {"deviations": deviations, "total": len(progresses)},
            })
        # OPEN_RISK_STATUSES = IDENTIFIED+MONITORING; filtramos level=CRITICAL
        # em Python porque level é property derivada (probability × impact).
        open_risks = list(
            (
                await db.execute(
                    select(Risk).where(
                        Risk.report_id == report.id,
                        Risk.status.in_(OPEN_RISK_STATUSES),
                    )
                )
            ).scalars().all()
        )
        critical_risks = [r for r in open_risks if r.level == RiskLevel.CRITICAL]
        if critical_risks:
            insights.append({
                "kind": "critical_risk_alert",
                "severity": "critical",
                "headline": f"{len(critical_risks)} risco(s) crítico(s) abertos",
                "detail": "Riscos críticos abertos sinalizam atenção imediata do PMO.",
                "evidence": {"risks": [r.description for r in critical_risks]},
            })
        client_pending = list(
            (
                await db.execute(
                    select(PendingItem).where(
                        PendingItem.report_id == report.id,
                        PendingItem.status == PendingItemStatus.OPEN,
                        PendingItem.owner_party == "client",
                    )
                )
            ).scalars().all()
        )
        if len(client_pending) >= 3:
            insights.append({
                "kind": "client_blocking_items",
                "severity": "medium",
                "headline": f"{len(client_pending)} pendências do cliente em aberto",
                "detail": "Pendências acumuladas do lado do cliente costumam virar gargalo de prazo.",
                "evidence": {"items": [p.description for p in client_pending]},
            })

        if not insights:
            insights.append({
                "kind": "all_clear",
                "severity": "info",
                "headline": "Nenhum padrão de risco detectado",
                "detail": "O report apresenta indicadores saudáveis. Mantenha a cadência.",
                "evidence": {},
            })

        for ins in insights:
            db.add(
                AIInsight(
                    scope=InsightScope.PROJECT,
                    project_id=project.id,
                    report_id=report.id,
                    payload=ins,
                )
            )
        await db.commit()

        emit_to_user(
            project.gp_user_id,
            "report_insights_ready",
            {"report_id": str(report.id), "count": len(insights)},
        )
        log.info(
            "analyzer_stub.completed",
            report_id=str(report.id),
            insights=len(insights),
        )


def schedule_analysis(report_id: uuid.UUID) -> None:
    if not is_enabled():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_process(report_id))
