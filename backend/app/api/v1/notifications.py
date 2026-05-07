"""Endpoints in-app de notificações."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import InAppNotification, User
from app.services import notifications as notif_svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationPublic(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread: int


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    n = (
        await db.execute(
            select(func.count())
            .select_from(InAppNotification)
            .where(
                InAppNotification.user_id == user.id,
                InAppNotification.read_at.is_(None),
            )
        )
    ).scalar_one()
    return UnreadCountResponse(unread=int(n or 0))


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InAppNotification]:
    return await notif_svc.list_recent_for(db, user.id)


@router.post("/{notification_id}/read", response_model=NotificationPublic)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InAppNotification:
    n = await notif_svc.mark_read(db, notification_id=notification_id, user_id=user.id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notificação não encontrada")
    return n
