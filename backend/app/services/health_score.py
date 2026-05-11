"""Cálculo do Health Score (0-100) por projeto — spec v3.1 §10.3.

Fórmula com 5 componentes ponderados:

  Health Score =
    (Status RAG médio       × w.rag_avg) +
    (SPI                    × w.spi) +
    (Risco geral inverso    × w.risk_inverse) +
    (Taxa de resolução      × w.resolution_rate) +
    (Estabilidade do status × w.stability)

Pesos default ancorados na spec: 35/25/20/10/10. Editáveis pelo PMO via
PortfolioConfig.health_score_weights (JSONB). Se a soma não é 1.00, o
serviço normaliza no momento do cálculo (defesa em profundidade).

Definições dos componentes (todas em [0..100]):

  1. rag_avg
     Média numérica das 3 dimensões RAG (Prazo/Escopo/Qualidade) do último
     report submetido. Verde=100, Amarelo=50, Vermelho=0. Sem report → 50.

  2. spi  — Schedule Performance Index
     Para cada deliverable do baseline ativo:
       %_planejado_até_hoje = (hoje - project.started_at) / (deliverable.due_date - started_at)
       cap em [0, 100]
       %_real = DeliveryProgress.percent_complete mais recente
     SPI = (média de %_real) / (média de %_planejado) × 100, cap em 100.
     Sem baseline ativo ou sem progressos → 100 (sem dado de desvio).

  3. risk_inverse
     100 − (média ponderada dos riscos abertos no último report).
     Pesos numéricos: Critical=100, High=75, Medium=50, Low=25.
     "Peso = nível" (cada risco contribui com seu próprio valor como peso E
     valor, conforme nota explicativa da spec). Sem riscos abertos → 100.

  4. resolution_rate
     (PendingItems com status=resolved) / (total de PendingItems do report)
     × 100. Sem pendências no report → 100.

  5. stability
     Tabela aplicada sobre o `rag_status` agregado dos últimos 5 reports
     submetidos (mais recentes primeiro):
       ≥5 reports e TODOS no mesmo rag → 100 se Verde, 50 se Amarelo, 0 se Vermelho
       ≥3 reports e TODOS no mesmo rag → 60
       qualquer oscilação ou < 3 reports     → 30
     Sem reports → 50 (neutro).
     Heurística inicial (ADR 2026-05-11): a tabela é refinável com PMO real.

Faixas de classificação textual:
  ≥ 70  → green ("Saudável")
  40-69 → amber ("Atenção")
  < 40  → red   ("Crítico")
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    OPEN_RISK_STATUSES,
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    PendingItemStatus,
    PortfolioConfig,
    Project,
    RAGStatus,
    Report,
    ReportStatus,
    Risk,
)

# Pesos default da spec v3.1 §10.3
DEFAULT_WEIGHTS: dict[str, float] = {
    "rag_avg": 0.35,
    "spi": 0.25,
    "risk_inverse": 0.20,
    "resolution_rate": 0.10,
    "stability": 0.10,
}

_WEIGHT_KEYS = tuple(DEFAULT_WEIGHTS.keys())

# Mapeamento RAG → valor numérico (spec v3.1 §10.3)
_RAG_NUMERIC: dict[RAGStatus, float] = {
    RAGStatus.GREEN: 100.0,
    RAGStatus.AMBER: 50.0,
    RAGStatus.RED: 0.0,
}

# Pesos numéricos dos níveis de risco (spec v3.1 §10.3 — Critical=100..Low=25)
_RISK_LEVEL_VALUE: dict[str, float] = {
    "critical": 100.0,
    "high": 75.0,
    "medium": 50.0,
    "low": 25.0,
}

_RAG_NEUTRO = 50.0


@dataclass(frozen=True)
class HealthScoreBreakdown:
    """Resultado do cálculo com os 5 componentes + agregado + pesos aplicados."""

    project_id: uuid.UUID
    score: float
    band: str  # green | amber | red
    rag_avg: float
    spi: float
    risk_inverse: float
    resolution_rate: float
    stability: float
    weights_applied: dict[str, float]
    last_report_id: uuid.UUID | None
    last_report_period_end: str | None

    def as_dict(self) -> dict:
        return {
            "project_id": str(self.project_id),
            "score": self.score,
            "band": self.band,
            "components": {
                "rag_avg": self.rag_avg,
                "spi": self.spi,
                "risk_inverse": self.risk_inverse,
                "resolution_rate": self.resolution_rate,
                "stability": self.stability,
            },
            "weights_applied": self.weights_applied,
            "last_report_id": str(self.last_report_id) if self.last_report_id else None,
            "last_report_period_end": self.last_report_period_end,
        }


def _band(score: float) -> str:
    """Classificação textual (spec v3.1 §10.3)."""
    if score >= 70:
        return "green"
    if score >= 40:
        return "amber"
    return "red"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _normalize_weights(raw: dict | None) -> dict[str, float]:
    """Lê pesos do JSONB, preenche faltantes com defaults, normaliza para soma=1.0.

    Defensivo: aceita JSON com chaves extras (ignora) ou faltantes (default).
    Se soma ≤ 0, retorna defaults.
    """
    raw = raw or {}
    weights = {k: float(raw.get(k, DEFAULT_WEIGHTS[k])) for k in _WEIGHT_KEYS}
    total = sum(weights.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    if abs(total - 1.0) <= 0.01:
        return weights
    return {k: v / total for k, v in weights.items()}


# ---------- Acesso à config ----------


async def _get_or_create_config(db: AsyncSession) -> PortfolioConfig:
    cfg = await db.get(PortfolioConfig, 1)
    if cfg:
        return cfg
    cfg = PortfolioConfig(id=1, health_score_weights=dict(DEFAULT_WEIGHTS))
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


async def get_config(db: AsyncSession) -> PortfolioConfig:
    return await _get_or_create_config(db)


async def update_weights(
    db: AsyncSession,
    *,
    weights: dict[str, float],
    updated_by_id: uuid.UUID | None = None,
) -> PortfolioConfig:
    """Atualiza os pesos. Valida soma=1.00 ± 0.01 (chamador deve garantir antes).

    Mantemos validação tolerante aqui: se a soma escapar a tolerância, ainda
    persistimos e o serviço normaliza no cálculo.
    """
    cfg = await _get_or_create_config(db)
    cfg.health_score_weights = dict(weights)
    cfg.updated_by_id = updated_by_id
    cfg.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ---------- Componentes (5 funções) ----------


def compute_rag_avg(report: Report | None) -> float:
    """Componente 1 — Status RAG médio (spec v3.1 §10.3).

    Média das 3 dimensões do último report. Verde=100, Amarelo=50, Vermelho=0.
    Sem report → 50 (neutro). Se as dimensões não estão preenchidas mas
    rag_status agregado está, usa o agregado.
    """
    if report is None:
        return _RAG_NEUTRO
    vals: list[float] = []
    for dim in (report.rag_prazo, report.rag_escopo, report.rag_qualidade):
        if dim is not None:
            vals.append(_RAG_NUMERIC[dim])
    if vals:
        return sum(vals) / len(vals)
    if report.rag_status is not None:
        return _RAG_NUMERIC[report.rag_status]
    return _RAG_NEUTRO


async def compute_spi(
    db: AsyncSession,
    project: Project,
    *,
    today: date | None = None,
) -> float:
    """Componente 2 — SPI (Schedule Performance Index).

    Para cada deliverable do baseline ativo:
      %_planejado_hoje = (hoje - project.started_at) / (due_date - started_at) × 100, cap [0,100]
      %_real           = max(percent_complete dos DeliveryProgress do deliverable)
    SPI = média(%_real) / média(%_planejado) × 100, cap em 100.

    Sem baseline ativo, sem deliverables ou sem datas → 100 (sem dado de desvio).
    """
    today = today or datetime.now(UTC).date()
    start = project.started_at or project.created_at.date()

    active_baseline = (
        await db.execute(
            select(Baseline).where(
                Baseline.project_id == project.id,
                Baseline.status == BaselineStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if active_baseline is None:
        return 100.0

    deliverables = list(
        (
            await db.execute(
                select(Deliverable).where(Deliverable.baseline_id == active_baseline.id)
            )
        ).scalars().all()
    )
    if not deliverables:
        return 100.0

    real_pcts: list[float] = []
    planned_pcts: list[float] = []
    for d in deliverables:
        if d.due_date is None or d.due_date <= start:
            # Sem prazo confiável: ignora deliverable do SPI
            continue
        span_days = (d.due_date - start).days
        if span_days <= 0:
            continue
        elapsed = (today - start).days
        planned = _clamp(elapsed / span_days * 100.0)
        # %_real: maior percent_complete observado em qualquer report submetido
        rows = list(
            (
                await db.execute(
                    select(DeliveryProgress).where(
                        DeliveryProgress.deliverable_id == d.id
                    )
                )
            ).scalars().all()
        )
        real = max((float(p.percent_complete) for p in rows), default=0.0)
        real_pcts.append(real)
        planned_pcts.append(planned)

    if not planned_pcts:
        return 100.0
    avg_real = sum(real_pcts) / len(real_pcts)
    avg_planned = sum(planned_pcts) / len(planned_pcts)
    if avg_planned <= 0:
        # Nada planejado ainda; se já há %_real, está adiantado → cap 100
        return 100.0 if avg_real > 0 else _RAG_NEUTRO
    return _clamp(avg_real / avg_planned * 100.0)


async def compute_risk_inverse(
    db: AsyncSession, last_report: Report | None
) -> float:
    """Componente 3 — Risco geral inverso (spec v3.1 §10.3).

    100 − média ponderada dos riscos abertos. Critical=100, High=75, Medium=50, Low=25.
    Peso = valor do nível (riscos críticos pesam mais na média). Sem report ou
    sem riscos abertos → 100 (nenhum risco = saudável).
    """
    if last_report is None:
        return 100.0
    # OPEN_RISK_STATUSES = (IDENTIFIED, MONITORING) — MITIGATED já foi tratado
    # e MATERIALIZED virou problema; nenhum dos dois conta como "risco vivo".
    rows = list(
        (
            await db.execute(
                select(Risk).where(
                    Risk.report_id == last_report.id,
                    Risk.status.in_(OPEN_RISK_STATUSES),
                )
            )
        ).scalars().all()
    )
    if not rows:
        return 100.0
    weighted_sum = 0.0
    total_weight = 0.0
    for r in rows:
        # `r.level` é property derivada de (probability × impact) — spec §4.2.3
        val = _RISK_LEVEL_VALUE.get(r.level.value, 50.0)
        # peso = valor (self-weighted)
        weighted_sum += val * val
        total_weight += val
    if total_weight <= 0:
        return 100.0
    weighted_avg = weighted_sum / total_weight
    return _clamp(100.0 - weighted_avg)


async def compute_resolution_rate(
    db: AsyncSession, last_report: Report | None
) -> float:
    """Componente 4 — Taxa de resolução (spec v3.1 §10.3).

    (PendingItems resolvidas no report) / (total de PendingItems no report) × 100.
    Sem report ou sem pendências → 100.
    """
    if last_report is None:
        return 100.0
    rows = list(
        (
            await db.execute(
                select(PendingItem).where(PendingItem.report_id == last_report.id)
            )
        ).scalars().all()
    )
    if not rows:
        return 100.0
    resolved = sum(1 for p in rows if p.status == PendingItemStatus.RESOLVED)
    return _clamp(resolved / len(rows) * 100.0)


async def compute_stability(
    db: AsyncSession, project: Project
) -> float:
    """Componente 5 — Estabilidade (spec v3.1 §10.3, heurística inicial).

    Olha rag_status agregado dos últimos 5 reports submetidos (mais recente
    primeiro). Tabela:
      ≥5 reports e TODOS no mesmo rag → 100 (Verde), 50 (Amarelo), 0 (Vermelho)
      ≥3 reports e TODOS no mesmo rag → 60 (estabilidade mediana)
      qualquer oscilação ou <3 reports → 30 (instável ou histórico curto)
    Sem reports → 50 (neutro, não há base pra avaliar).
    """
    stmt = (
        select(Report.rag_status)
        .where(
            Report.project_id == project.id,
            Report.status.in_(
                [
                    ReportStatus.SUBMITTED,
                    ReportStatus.PMO_APPROVED,
                    ReportStatus.CLIENT_RELEASED,
                    ReportStatus.ARCHIVED,
                ]
            ),
        )
        .order_by(Report.period_end.desc(), Report.created_at.desc())
        .limit(5)
    )
    rows: list[RAGStatus | None] = list(
        (await db.execute(stmt)).scalars().all()
    )
    rags = [r for r in rows if r is not None]
    if not rags:
        return _RAG_NEUTRO
    if len(rags) >= 5 and len(set(rags)) == 1:
        return _RAG_NUMERIC[rags[0]]
    if len(rags) >= 3 and len(set(rags)) == 1:
        return 60.0
    return 30.0


# ---------- Orquestração ----------


async def _last_submitted_report(
    db: AsyncSession, project_id: uuid.UUID
) -> Report | None:
    stmt = (
        select(Report)
        .where(
            Report.project_id == project_id,
            Report.status.in_(
                [
                    ReportStatus.SUBMITTED,
                    ReportStatus.PMO_APPROVED,
                    ReportStatus.CLIENT_RELEASED,
                    ReportStatus.ARCHIVED,
                ]
            ),
        )
        .order_by(Report.period_end.desc(), Report.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def compute_for_project(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    cfg: PortfolioConfig | None = None,
) -> HealthScoreBreakdown:
    """Orquestra os 5 componentes + agregação ponderada (spec v3.1 §10.3)."""
    if cfg is None:
        cfg = await _get_or_create_config(db)
    project = await db.get(Project, project_id)
    if project is None:
        raise ValueError(f"projeto não encontrado: {project_id}")

    weights = _normalize_weights(cfg.health_score_weights)
    last = await _last_submitted_report(db, project_id)

    rag_avg = compute_rag_avg(last)
    spi = await compute_spi(db, project)
    risk_inv = await compute_risk_inverse(db, last)
    res_rate = await compute_resolution_rate(db, last)
    stab = await compute_stability(db, project)

    score = (
        weights["rag_avg"] * rag_avg
        + weights["spi"] * spi
        + weights["risk_inverse"] * risk_inv
        + weights["resolution_rate"] * res_rate
        + weights["stability"] * stab
    )
    score = round(_clamp(score), 1)

    return HealthScoreBreakdown(
        project_id=project_id,
        score=score,
        band=_band(score),
        rag_avg=round(rag_avg, 1),
        spi=round(spi, 1),
        risk_inverse=round(risk_inv, 1),
        resolution_rate=round(res_rate, 1),
        stability=round(stab, 1),
        weights_applied=weights,
        last_report_id=last.id if last else None,
        last_report_period_end=last.period_end.isoformat() if last else None,
    )


async def cache_to_report(
    db: AsyncSession, report: Report, score: float
) -> None:
    """Persiste o score no Report e no Project.health_score_cached (spec v3.1 §10.3)."""
    report.health_score = score
    project = await db.get(Project, report.project_id)
    if project is not None:
        project.health_score_cached = score
    await db.commit()
