"""Serviço de notificações: in-app (DB + SSE) + e-mail (Resend).

Resend opera em modo "dry-run" se `RESEND_API_KEY` estiver vazio ou se
`RESEND_DRY_RUN=true`. Dry-run só loga; útil em dev/CI/tests.

In-app: cria InAppNotification + emite SSE 'notification' para o user_id.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    Baseline,
    InAppNotification,
    Project,
    Report,
    ReportApproval,
    ReportStatus,
    Role,
    User,
)
from app.notifications.sse import emit_to_user

log = get_logger("notifications")


def _resend_dry_run() -> bool:
    if os.environ.get("RESEND_DRY_RUN", "false").lower() in ("1", "true", "yes"):
        return True
    if not os.environ.get("RESEND_API_KEY", ""):
        return True
    return False


async def _create_inapp(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> InAppNotification:
    notif = InAppNotification(
        user_id=user_id, kind=kind, title=title, body=body, link=link,
    )
    db.add(notif)
    await db.flush()
    emit_to_user(
        user_id,
        "notification",
        {
            "id": str(notif.id),
            "kind": kind,
            "title": title,
            "body": body,
            "link": link,
        },
    )
    return notif


def _send_email(*, to: str, subject: str, body: str) -> None:
    """Envia via Resend ou loga em dry-run."""
    if _resend_dry_run():
        log.info("email.dry_run", to=to, subject=subject)
        return
    try:
        import resend  # type: ignore[import-not-found]

        resend.api_key = os.environ.get("RESEND_API_KEY", "")
        sender = os.environ.get(
            "RESEND_FROM_EMAIL", "christopher.tominaga@jumplabel.com.br"
        )
        resend.Emails.send({
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": f"<p>{body}</p>",
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("email.send_failed", to=to, error=str(exc))


async def notify_report_submitted(
    db: AsyncSession, *, report: Report, project: Project
) -> None:
    """GP submeteu — avisa todos os PMOs."""
    pmos = list(
        (
            await db.execute(select(User).where(User.role == Role.PMO))
        ).scalars().all()
    )
    title = f"Report submetido: {project.name}"
    body = f"GP submeteu report do período {report.period_start} → {report.period_end}."
    link = f"/pmo/reports/{report.id}/review"
    for pmo in pmos:
        await _create_inapp(
            db, user_id=pmo.id, kind="report_submitted", title=title, body=body, link=link
        )
        _send_email(to=pmo.email, subject=title, body=body + f' Acesse: {link}')
    await db.commit()


async def notify_approval_decision(
    db: AsyncSession,
    *,
    report: Report,
    approval: ReportApproval,
    project: Project,
) -> None:
    """Após cada decisão, notifica os papéis interessados."""
    decided = approval.decision.value
    if report.status == ReportStatus.PMO_APPROVED:
        # PMO aprovou → notifica cliente (se houver) + GP
        if project.client_user_id:
            client = await db.get(User, project.client_user_id)
            if client:
                await _create_inapp(
                    db,
                    user_id=client.id,
                    kind="report_pending_release",
                    title=f"Report do {project.name} aguarda sua aprovação",
                    body=f"Período {report.period_start} → {report.period_end}.",
                    link=f"/portal/reports/{report.id}",
                )
                _send_email(
                    to=client.email,
                    subject=f"Report aguarda sua aprovação - {project.name}",
                    body=f"Período {report.period_start} → {report.period_end}.",
                )
        gp = await db.get(User, project.gp_user_id)
        if gp:
            # Quando aprovação tem nota interna, destacar no corpo da notificação
            # — o comment é visível ao GP no histórico, mas nunca ao cliente.
            if approval.comment and approval.comment.strip():
                body = (
                    f"Período {report.period_start} → {report.period_end}. "
                    f'Nota interna do PMO: "{approval.comment.strip()}"'
                )
                kind = "report_pmo_approved_with_comment"
            else:
                body = f"Período {report.period_start} → {report.period_end}."
                kind = "report_pmo_approved"
            await _create_inapp(
                db,
                user_id=gp.id,
                kind=kind,
                title=f"PMO aprovou seu report: {project.name}",
                body=body,
                link=f"/projetos/{project.id}/reports/{report.id}/edit",
            )
    elif report.status == ReportStatus.CLIENT_RELEASED:
        gp = await db.get(User, project.gp_user_id)
        if gp:
            await _create_inapp(
                db,
                user_id=gp.id,
                kind="report_client_released",
                title=f"Cliente aprovou: {project.name}",
                body=f"Report {report.period_start} → {report.period_end} liberado.",
                link=f"/projetos/{project.id}/reports/{report.id}/edit",
            )
    elif report.status == ReportStatus.NEEDS_REVISION:
        gp = await db.get(User, project.gp_user_id)
        if gp:
            await _create_inapp(
                db,
                user_id=gp.id,
                kind="report_needs_revision",
                title=f"Revisão pedida: {project.name}",
                body=approval.comment or f"Decisão: {decided}",
                link=f"/projetos/{project.id}/reports/{report.id}/edit",
            )
    await db.commit()


async def notify_transition_decision(
    db: AsyncSession,
    *,
    project: Project,
    baseline: Baseline,
    decision: str,  # "approve" | "reject"
    scope_changes_count: int,
    comment: str | None,
) -> None:
    """PMO decidiu uma transição de escopo (F5.2 — v3.1 §10.5). Notifica GP.

    Replica o pattern de `notify_approval_decision`: in-app + e-mail (Resend
    em dry-run quando RESEND_API_KEY ausente). Falha não bloqueia a transição
    no endpoint chamador.
    """
    gp = await db.get(User, project.gp_user_id)
    if not gp:
        return

    if decision == "approve":
        kind = "scope_transition_approved"
        title = f"PMO aprovou mudança de escopo: {project.name}"
        body = (
            f"{scope_changes_count} alteração(ões) aprovada(s). "
            f"Novo baseline está ativo."
        )
    else:
        kind = "scope_transition_rejected"
        title = f"PMO rejeitou mudança de escopo: {project.name}"
        suffix = (
            f' Motivo: "{comment.strip()}"' if comment and comment.strip() else ""
        )
        body = (
            f"{scope_changes_count} alteração(ões) rejeitada(s)."
            f"{suffix} Ajuste a proposta e suba uma nova versão."
        )

    link = f"/projetos/{project.id}/diff?new={baseline.id}"
    await _create_inapp(
        db, user_id=gp.id, kind=kind, title=title, body=body, link=link
    )
    _send_email(to=gp.email, subject=title, body=body + f" Acesse: {link}")
    await db.commit()


# -- Endpoints in-app (lista, marcar como lida) --


async def list_unread_for(db: AsyncSession, user_id: uuid.UUID) -> list[InAppNotification]:
    rows = (
        await db.execute(
            select(InAppNotification)
            .where(
                InAppNotification.user_id == user_id,
                InAppNotification.read_at.is_(None),
            )
            .order_by(InAppNotification.created_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def list_recent_for(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 30
) -> list[InAppNotification]:
    rows = (
        await db.execute(
            select(InAppNotification)
            .where(InAppNotification.user_id == user_id)
            .order_by(InAppNotification.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def mark_read(
    db: AsyncSession, *, notification_id: uuid.UUID, user_id: uuid.UUID
) -> InAppNotification | None:
    from datetime import datetime

    notif = await db.get(InAppNotification, notification_id)
    if not notif or notif.user_id != user_id:
        return None
    if notif.read_at is None:
        notif.read_at = datetime.now(UTC)
        await db.commit()
    return notif


__all__ = [
    "list_recent_for",
    "list_unread_for",
    "mark_read",
    "notify_approval_decision",
    "notify_report_submitted",
    "notify_transition_decision",
]


# Permite import sem efeitos colaterais
_ = Any
