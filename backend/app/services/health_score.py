"""Cálculo do Health Score (0-100) por projeto.

Combinação ponderada de 4 sub-scores, todos em [0, 100]:
  1. progress: % de Deliverables com algum DeliveryProgress.status='done'
     no último report submetido. Sem report → fallback 50 (neutro).
  2. risks: 100 - (riscos abertos no último report × peso por severidade) clamp 0..100.
     critical=25, high=15, medium=8, low=3 pontos por risco aberto.
  3. pendings: 100 - (pending_items abertas × 12) clamp 0..100.
  4. schedule: % de DeliveryProgress sem deviation_flag, no último report.
     Sem progressos → 100.

Pesos vêm de PortfolioConfig (singleton). Se não somam 1.0, normalizamos.

Faixas de cor:
  >=70  → green
  40..69 → amber
  <40   → red
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    PendingItemStatus,
    PortfolioConfig,
    Report,
    ReportStatus,
    Risk,
    RiskStatus,
)

_RISK_PENALTY = {"critical": 25.0, "high": 15.0, "medium": 8.0, "low": 3.0}
_PENDING_PENALTY = 12.0


@dataclass(frozen=True)
class HealthScoreBreakdown:
    project_id: uuid.UUID
    score: float  # 0..100, arredondado para 1 casa
    band: str  # green | amber | red
    progress: float
    risks: float
    pendings: float
    schedule: float
    last_report_id: uuid.UUID | None
    last_report_period_end: str | None  # ISO date

    def as_dict(self) -> dict:
        return {
            "project_id": str(self.project_id),
            "score": self.score,
            "band": self.band,
            "components": {
                "progress": self.progress,
                "risks": self.risks,
                "pendings": self.pendings,
                "schedule": self.schedule,
            },
            "last_report_id": str(self.last_report_id) if self.last_report_id else None,
            "last_report_period_end": self.last_report_period_end,
        }


def _band(score: float) -> str:
    if score >= 70:
        return "green"
    if score >= 40:
        return "amber"
    return "red"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


async def _get_or_create_config(db: AsyncSession) -> PortfolioConfig:
    cfg = await db.get(PortfolioConfig, 1)
    if cfg:
        return cfg
    cfg = PortfolioConfig(id=1)
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def get_config(db: AsyncSession) -> PortfolioConfig:
    return await _get_or_create_config(db)


async def update_config(
    db: AsyncSession,
    *,
    weight_progress: float,
    weight_risks: float,
    weight_pendings: float,
    weight_schedule: float,
    updated_by_id: uuid.UUID | None = None,
) -> PortfolioConfig:
    cfg = await _get_or_create_config(db)
    cfg.weight_progress = weight_progress
    cfg.weight_risks = weight_risks
    cfg.weight_pendings = weight_pendings
    cfg.weight_schedule = weight_schedule
    cfg.updated_by_id = updated_by_id
    from datetime import datetime

    cfg.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def _last_report(db: AsyncSession, project_id: uuid.UUID) -> Report | None:
    stmt = (
        select(Report)
        .where(
            Report.project_id == project_id,
            Report.status.in_([
                ReportStatus.SUBMITTED,
                ReportStatus.PMO_APPROVED,
                ReportStatus.CLIENT_RELEASED,
                ReportStatus.ARCHIVED,
            ]),
        )
        .order_by(Report.period_end.desc(), Report.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _active_baseline_deliverables_count(
    db: AsyncSession, project_id: uuid.UUID
) -> int:
    baseline = (
        await db.execute(
            select(Baseline).where(
                Baseline.project_id == project_id,
                Baseline.status == BaselineStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if not baseline:
        return 0
    rows = await db.execute(
        select(Deliverable).where(Deliverable.baseline_id == baseline.id)
    )
    return len(list(rows.scalars().all()))


async def compute_for_project(
    db: AsyncSession, project_id: uuid.UUID, *, cfg: PortfolioConfig | None = None
) -> HealthScoreBreakdown:
    if cfg is None:
        cfg = await _get_or_create_config(db)

    # Normaliza pesos
    total_w = cfg.weight_progress + cfg.weight_risks + cfg.weight_pendings + cfg.weight_schedule
    if total_w <= 0:
        wp = wr = wpe = ws = 0.25
    else:
        wp = cfg.weight_progress / total_w
        wr = cfg.weight_risks / total_w
        wpe = cfg.weight_pendings / total_w
        ws = cfg.weight_schedule / total_w

    last = await _last_report(db, project_id)

    # 1. progress
    if last is None:
        progress = 50.0
    else:
        progresses = list(
            (
                await db.execute(
                    select(DeliveryProgress).where(DeliveryProgress.report_id == last.id)
                )
            ).scalars().all()
        )
        if not progresses:
            progress = 0.0
        else:
            done = sum(1 for p in progresses if p.status.value == "done")
            progress = (done / len(progresses)) * 100.0

    # 2. risks (só riscos abertos no último report)
    if last is None:
        risks_score = 100.0
    else:
        rows = list(
            (
                await db.execute(
                    select(Risk).where(
                        Risk.report_id == last.id,
                        Risk.status == RiskStatus.OPEN,
                    )
                )
            ).scalars().all()
        )
        penalty = sum(_RISK_PENALTY.get(r.severity.value, 5.0) for r in rows)
        risks_score = _clamp(100.0 - penalty)

    # 3. pendings
    if last is None:
        pendings_score = 100.0
    else:
        rows_p = list(
            (
                await db.execute(
                    select(PendingItem).where(
                        PendingItem.report_id == last.id,
                        PendingItem.status == PendingItemStatus.OPEN,
                    )
                )
            ).scalars().all()
        )
        pendings_score = _clamp(100.0 - len(rows_p) * _PENDING_PENALTY)

    # 4. schedule
    if last is None:
        schedule_score = 100.0
    else:
        progresses2 = list(
            (
                await db.execute(
                    select(DeliveryProgress).where(DeliveryProgress.report_id == last.id)
                )
            ).scalars().all()
        )
        if not progresses2:
            schedule_score = 100.0
        else:
            on_track = sum(1 for p in progresses2 if not p.deviation_flag)
            schedule_score = (on_track / len(progresses2)) * 100.0

    score = wp * progress + wr * risks_score + wpe * pendings_score + ws * schedule_score
    score = round(_clamp(score), 1)

    return HealthScoreBreakdown(
        project_id=project_id,
        score=score,
        band=_band(score),
        progress=round(progress, 1),
        risks=round(risks_score, 1),
        pendings=round(pendings_score, 1),
        schedule=round(schedule_score, 1),
        last_report_id=last.id if last else None,
        last_report_period_end=last.period_end.isoformat() if last else None,
    )


async def cache_to_report(
    db: AsyncSession, report: Report, score: float
) -> None:
    """Persiste o score na coluna Report.health_score após o cálculo."""
    report.health_score = score
    await db.commit()
