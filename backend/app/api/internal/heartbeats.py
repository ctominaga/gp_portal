"""POST /internal/worker-heartbeat — recebe heartbeat do worker."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.worker_auth import require_worker_auth
from app.models import WorkerHeartbeat
from app.schemas.worker import WorkerHeartbeatPayload

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/worker-heartbeat")
async def worker_heartbeat(
    body: bytes = Depends(require_worker_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        payload = WorkerHeartbeatPayload.model_validate(json.loads(body or b"{}"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"payload inválido: {exc}") from exc

    existing = await db.get(WorkerHeartbeat, payload.worker_id)
    now = datetime.now(UTC)
    if existing:
        existing.last_seen_at = now
        existing.status = payload.status
        existing.sessions_status = payload.sessions_status
        existing.jobs_processed_today = payload.jobs_processed_today
        existing.jobs_failed_today = payload.jobs_failed_today
        existing.metadata_json = payload.metadata
    else:
        db.add(
            WorkerHeartbeat(
                worker_id=payload.worker_id,
                last_seen_at=now,
                status=payload.status,
                sessions_status=payload.sessions_status,
                jobs_processed_today=payload.jobs_processed_today,
                jobs_failed_today=payload.jobs_failed_today,
                metadata_json=payload.metadata,
            )
        )
    await db.commit()
    return {"ack": "ok"}
