"""F4: Health Score, aprovação 3 estágios, portal cliente, diff de baselines."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models import (
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliverableComplexity,
    DeliveryProgress,
    PendingItem,
    PendingItemStatus,
    PortfolioConfig,
    ProgressStatus,
    Project,
    Proposal,
    ProposalStatus,
    RAGStatus,
    Report,
    ReportStatus,
    Risk,
    RiskImpact,
    RiskLevel,
    RiskProbability,
    RiskStatus,
    Role,
    User,
)
from app.models.domain import OPEN_RISK_STATUSES, compute_risk_level
from app.services import health_score


async def _login(client, *, role: str, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


async def _seed_project(db, *, gp_email="gp@x.com", client_email=None) -> Project:
    gp = User(name="GP", email=gp_email, password_hash=hash_password("JumpDev123!"), role=Role.GP)
    db.add(gp)
    await db.flush()
    client_id = None
    if client_email:
        cli = User(
            name="Cliente",
            email=client_email,
            password_hash=hash_password("JumpDev123!"),
            role=Role.CLIENT,
        )
        db.add(cli)
        await db.flush()
        client_id = cli.id
    project = Project(name="Bradesco SAS", client_name="Bradesco", gp_user_id=gp.id, client_user_id=client_id)
    db.add(project)
    await db.commit()
    return project


async def _seed_full_report(
    db, *, project: Project, rag_p="G", rag_e="G", rag_q="G",
    risks=0, criticals=0, pending_client=0, deliverables_done=0, total_deliv=4,
    period_end=date(2026, 5, 15),
) -> Report:
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db.add(proposal)
    await db.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id, status=BaselineStatus.ACTIVE, payload={},
    )
    db.add(baseline)
    await db.flush()
    delivs = []
    for i in range(total_deliv):
        d = Deliverable(
            baseline_id=baseline.id,
            code=f"d-{i:03d}",
            title=f"Entregavel {i}",
            phase="fase-1",
            complexity=DeliverableComplexity.LOW,
            due_date=date(2026, 6, 1),
        )
        db.add(d)
        delivs.append(d)
    await db.flush()

    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1),
        period_end=period_end,
        rag_prazo=RAGStatus(rag_p),
        rag_escopo=RAGStatus(rag_e),
        rag_qualidade=RAGStatus(rag_q),
        rag_status=RAGStatus(rag_q),  # simplificado
        status=ReportStatus.SUBMITTED,
        submitted_at=datetime.now(UTC),
        created_by_id=project.gp_user_id,
    )
    db.add(report)
    await db.flush()
    for i in range(deliverables_done):
        db.add(
            DeliveryProgress(
                report_id=report.id,
                deliverable_id=delivs[i].id,
                status=ProgressStatus.DONE,
                percent_complete=100,
            )
        )
    for i in range(deliverables_done, total_deliv):
        db.add(
            DeliveryProgress(
                report_id=report.id,
                deliverable_id=delivs[i].id,
                status=ProgressStatus.PLANNED,
                percent_complete=0,
            )
        )
    # Seed de riscos: cada `criticals` vira Alta×Alto → level=CRITICAL;
    # demais (risks - criticals) viram Alta×Medio → level=HIGH.
    for _ in range(criticals):
        db.add(Risk(
            report_id=report.id, description="r-crit",
            probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
            status=RiskStatus.IDENTIFIED,
        ))
    for _ in range(risks - criticals):
        db.add(Risk(
            report_id=report.id, description="r-high",
            probability=RiskProbability.ALTA, impact=RiskImpact.MEDIO,
            status=RiskStatus.IDENTIFIED,
        ))
    for _ in range(pending_client):
        db.add(
            PendingItem(
                report_id=report.id, description="p", owner_party="client", status=PendingItemStatus.OPEN
            )
        )
    await db.commit()
    return report


# ---------- Health Score ----------


# ---------- Health Score: 5 componentes da spec v3.1 §10.3 ----------


@pytest.mark.asyncio
async def test_health_score_componentes_neutros_quando_sem_report(db_session) -> None:
    """Sem reports: rag_avg=50, spi=100 (sem baseline), risk_inverse=100,
    resolution_rate=100, stability=50. Score com defaults 35/25/20/10/10."""
    project = await _seed_project(db_session, gp_email="gp1@x.com")
    breakdown = await health_score.compute_for_project(db_session, project.id)
    assert breakdown.rag_avg == 50.0
    assert breakdown.spi == 100.0
    assert breakdown.risk_inverse == 100.0
    assert breakdown.resolution_rate == 100.0
    assert breakdown.stability == 50.0
    # 50*0.35 + 100*0.25 + 100*0.20 + 100*0.10 + 50*0.10 = 77.5 → green
    assert abs(breakdown.score - 77.5) < 0.5
    assert breakdown.band == "green"


@pytest.mark.asyncio
async def test_compute_rag_avg_e_componente_independente() -> None:
    """rag_avg é função pura sobre o report. Verde=100, Amarelo=50, Vermelho=0."""
    from datetime import date as _d

    fake_g = Report(
        period_start=_d(2026, 5, 1),
        period_end=_d(2026, 5, 7),
        rag_prazo=RAGStatus.GREEN,
        rag_escopo=RAGStatus.GREEN,
        rag_qualidade=RAGStatus.GREEN,
        rag_status=RAGStatus.GREEN,
    )
    assert health_score.compute_rag_avg(fake_g) == 100.0

    fake_mix = Report(
        period_start=_d(2026, 5, 1),
        period_end=_d(2026, 5, 7),
        rag_prazo=RAGStatus.GREEN,
        rag_escopo=RAGStatus.AMBER,
        rag_qualidade=RAGStatus.RED,
        rag_status=RAGStatus.RED,
    )
    # (100 + 50 + 0) / 3 ≈ 50.0
    assert abs(health_score.compute_rag_avg(fake_mix) - 50.0) < 0.01

    assert health_score.compute_rag_avg(None) == 50.0


@pytest.mark.asyncio
async def test_compute_risk_inverse_e_componente_independente(db_session) -> None:
    """4 criticais (peso 100, valor 100) → média=100 → inverse=0."""
    project = await _seed_project(db_session, gp_email="gp-rinv@x.com")
    report = await _seed_full_report(
        db_session, project=project, risks=4, criticals=4
    )
    val = await health_score.compute_risk_inverse(db_session, report)
    assert abs(val - 0.0) < 0.01

    # Sem riscos abertos → 100
    project2 = await _seed_project(db_session, gp_email="gp-rinv2@x.com")
    report2 = await _seed_full_report(db_session, project=project2, risks=0)
    val2 = await health_score.compute_risk_inverse(db_session, report2)
    assert val2 == 100.0


def test_compute_risk_level_matrix_3x3() -> None:
    """spec v3.1 §4.2.3: 9 combinações de (probability × impact) → RiskLevel."""
    cases = [
        # (probability, impact, expected_level)
        (RiskProbability.ALTA,  RiskImpact.ALTO,  RiskLevel.CRITICAL),
        (RiskProbability.ALTA,  RiskImpact.MEDIO, RiskLevel.HIGH),
        (RiskProbability.ALTA,  RiskImpact.BAIXO, RiskLevel.MEDIUM),
        (RiskProbability.MEDIA, RiskImpact.ALTO,  RiskLevel.HIGH),
        (RiskProbability.MEDIA, RiskImpact.MEDIO, RiskLevel.MEDIUM),
        (RiskProbability.MEDIA, RiskImpact.BAIXO, RiskLevel.LOW),
        (RiskProbability.BAIXA, RiskImpact.ALTO,  RiskLevel.MEDIUM),
        (RiskProbability.BAIXA, RiskImpact.MEDIO, RiskLevel.LOW),
        (RiskProbability.BAIXA, RiskImpact.BAIXO, RiskLevel.LOW),
    ]
    for prob, imp, expected in cases:
        assert compute_risk_level(prob, imp) == expected, f"{prob}×{imp}"


def test_risk_level_property_via_orm() -> None:
    """Risk.level usa compute_risk_level direto da property."""
    r = Risk(
        description="x",
        probability=RiskProbability.MEDIA,
        impact=RiskImpact.ALTO,
        status=RiskStatus.IDENTIFIED,
    )
    assert r.level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_compute_risk_inverse_ignora_materialized_e_mitigated(db_session) -> None:
    """spec v3.1: risco MATERIALIZED virou problema (conta em outro lugar);
    MITIGATED já foi resolvido. Nenhum dos dois entra em compute_risk_inverse."""
    project = await _seed_project(db_session, gp_email="gp-rinv-mat@x.com")
    report = await _seed_full_report(db_session, project=project, risks=0)

    # Adiciona riscos manualmente em estados diversos
    db_session.add_all([
        Risk(  # entra
            report_id=report.id, description="ainda preocupa",
            probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
            status=RiskStatus.IDENTIFIED,
        ),
        Risk(  # NÃO entra — materializou
            report_id=report.id, description="virou problema",
            probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
            status=RiskStatus.MATERIALIZED,
        ),
        Risk(  # NÃO entra — já mitigado
            report_id=report.id, description="resolvido",
            probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
            status=RiskStatus.MITIGATED,
        ),
    ])
    await db_session.commit()

    val = await health_score.compute_risk_inverse(db_session, report)
    # Só o risco IDENTIFIED entra → mesmo cálculo de 1 critical aberto = 0
    assert val == 0.0


@pytest.mark.asyncio
async def test_compute_risk_inverse_inclui_identified_e_monitoring(db_session) -> None:
    """Ambos IDENTIFIED e MONITORING contam como 'risco aberto' (OPEN_RISK_STATUSES)."""
    project = await _seed_project(db_session, gp_email="gp-rinv-mon@x.com")
    report = await _seed_full_report(db_session, project=project, risks=0)

    db_session.add_all([
        Risk(
            report_id=report.id, description="recém detectado",
            probability=RiskProbability.MEDIA, impact=RiskImpact.MEDIO,  # MEDIUM
            status=RiskStatus.IDENTIFIED,
        ),
        Risk(
            report_id=report.id, description="sendo acompanhado",
            probability=RiskProbability.BAIXA, impact=RiskImpact.BAIXO,  # LOW
            status=RiskStatus.MONITORING,
        ),
    ])
    await db_session.commit()

    val = await health_score.compute_risk_inverse(db_session, report)
    # Cálculo: levels = MEDIUM(50), LOW(25). Self-weighted:
    # weighted_avg = (50*50 + 25*25) / (50+25) = (2500+625)/75 = 41.67
    # inverse = 100 - 41.67 ≈ 58.3
    assert abs(val - 58.33) < 0.5

    assert set(OPEN_RISK_STATUSES) == {RiskStatus.IDENTIFIED, RiskStatus.MONITORING}


# ---------- F5.1 Deliverable: type + acceptance + deps + status auto-update (v3.1 §4.2.2/§6.4.1) ----------


@pytest.mark.asyncio
async def test_deliverable_novos_campos_persistem(db_session) -> None:
    """acceptance_criteria, dependencies (lista), status default."""
    from app.models import DeliverableStatus, DeliverableType, DeliverableCategory

    project = await _seed_project(db_session, gp_email="gp-dnew@x.com")
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()
    deliv = Deliverable(
        baseline_id=baseline.id,
        code="d-001",
        title="Migração rotina A",
        type=DeliverableType.CODE_MIGRATION,
        category=DeliverableCategory.TECHNICAL,
        complexity=DeliverableComplexity.LOW,
        acceptance_criteria="Notebook executando em prod com 100% paridade",
        dependencies=["d-000", "external:databricks-env-ready"],
    )
    db_session.add(deliv)
    await db_session.commit()
    await db_session.refresh(deliv)

    assert deliv.status == DeliverableStatus.NOT_STARTED  # default
    assert deliv.acceptance_criteria.startswith("Notebook")
    assert deliv.dependencies == ["d-000", "external:databricks-env-ready"]
    assert deliv.type == DeliverableType.CODE_MIGRATION
    assert deliv.category == DeliverableCategory.TECHNICAL


@pytest.mark.asyncio
async def test_deliverable_dependencies_aceita_lista_vazia_e_default(
    db_session,
) -> None:
    """`dependencies` é NOT NULL com default `[]`. Não criar com lista
    explícita → vem `[]`. Criar com lista → preservada."""
    project = await _seed_project(db_session, gp_email="gp-ddep@x.com")
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="b" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()
    d1 = Deliverable(baseline_id=baseline.id, title="sem deps")
    d2 = Deliverable(baseline_id=baseline.id, title="com deps", dependencies=[])
    db_session.add_all([d1, d2])
    await db_session.commit()
    await db_session.refresh(d1)
    await db_session.refresh(d2)
    assert d1.dependencies == []
    assert d2.dependencies == []


# --- 3 casos do auto-update Deliverable.status = CONCLUDED ---


async def _seed_one_deliverable(db, gp_email: str) -> tuple[Project, Deliverable, Report]:
    """Helper: 1 projeto + 1 baseline ativo + 1 deliverable + 1 report draft."""
    project = await _seed_project(db, gp_email=gp_email)
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x",
        file_sha256="a" * 64, original_filename="p.pdf", size_bytes=1,
        status=ProposalStatus.EXTRACTED, uploaded_by_id=project.gp_user_id,
    )
    db.add(proposal)
    await db.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db.add(baseline)
    await db.flush()
    deliv = Deliverable(
        baseline_id=baseline.id, code="d-001", title="Entregavel teste",
        due_date=date(2026, 6, 1),
    )
    db.add(deliv)
    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1), period_end=date(2026, 5, 15),
        status=ReportStatus.DRAFT, created_by_id=project.gp_user_id,
    )
    db.add(report)
    await db.commit()
    return project, deliv, report


@pytest.mark.asyncio
async def test_auto_update_done_100_sem_acceptance_falha_e_nao_promove(
    client: AsyncClient, db_session
) -> None:
    """Cenário 1: done+100 sem acceptance_confirmed → backend já rejeita 400
    (validação AJUSTE I). Deliverable.status permanece NOT_STARTED.
    Esse teste defende o invariante: status nunca muda sem trilha completa.
    """
    from app.models import DeliverableStatus

    _, deliv, report = await _seed_one_deliverable(db_session, "gp-au1@x.com")
    gp = await _login(client, role="GP", email="gp-au1@x.com")
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={"progresses": [{
            "deliverable_id": str(deliv.id),
            "status": "done", "percent_complete": 100,
            # acceptance_confirmed AUSENTE → 400 do AJUSTE I
        }]},
    )
    assert r.status_code == 400
    await db_session.refresh(deliv)
    assert deliv.status == DeliverableStatus.NOT_STARTED  # invariante mantido


@pytest.mark.asyncio
async def test_auto_update_done_100_com_acceptance_promove_para_concluded(
    client: AsyncClient, db_session
) -> None:
    """Cenário 2: done+100+acceptance_confirmed=true → Deliverable.status=CONCLUDED."""
    from app.models import DeliverableStatus

    _, deliv, report = await _seed_one_deliverable(db_session, "gp-au2@x.com")
    gp = await _login(client, role="GP", email="gp-au2@x.com")
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={"progresses": [{
            "deliverable_id": str(deliv.id),
            "status": "done", "percent_complete": 100,
            "acceptance_confirmed": True,
        }]},
    )
    assert r.status_code == 200, r.text
    # Recarrega o deliverable depois da promoção cross-model
    await db_session.refresh(deliv)
    assert deliv.status == DeliverableStatus.CONCLUDED


@pytest.mark.asyncio
async def test_auto_update_parcial_com_acceptance_indevido_nao_promove(
    client: AsyncClient, db_session
) -> None:
    """Cenário 3 (patológico): progresso parcial (60%) com acceptance_confirmed=true
    (caso que não deveria existir, mas pode aparecer por bug de cliente) →
    Deliverable.status NÃO promove. Defende o invariante: a regra é a
    CONJUNÇÃO das 3 condições, não só a flag.
    """
    from app.models import DeliverableStatus

    _, deliv, report = await _seed_one_deliverable(db_session, "gp-au3@x.com")
    gp = await _login(client, role="GP", email="gp-au3@x.com")
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={"progresses": [{
            "deliverable_id": str(deliv.id),
            "status": "in_progress", "percent_complete": 60,
            "acceptance_confirmed": True,  # flag presente mas progresso é parcial
        }]},
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(deliv)
    assert deliv.status == DeliverableStatus.NOT_STARTED


# ---------- F5.1 ActionPlan: objective + vinculações (v3.1 §4.2.4) ----------


@pytest.mark.asyncio
async def test_action_plan_com_objective_e_vinculacao_a_risk(db_session) -> None:
    """ActionPlan vinculado a Risk persiste e a FK é navegável."""
    from app.models import ActionPlan, ActionPlanStatus

    project = await _seed_project(db_session, gp_email="gp-ap1@x.com")
    report = await _seed_full_report(db_session, project=project, risks=1)
    # pega o risco criado
    risk = (
        await db_session.execute(__import__("sqlalchemy").select(Risk).where(Risk.report_id == report.id))
    ).scalar_one()

    ap = ActionPlan(
        report_id=report.id,
        description="contratar consultoria externa",
        objective="reduzir probabilidade do risco IRRBB",
        linked_risk_id=risk.id,
        status=ActionPlanStatus.OPEN,
    )
    db_session.add(ap)
    await db_session.commit()
    await db_session.refresh(ap)

    assert ap.linked_risk_id == risk.id
    assert ap.linked_deliverable_id is None
    assert ap.objective == "reduzir probabilidade do risco IRRBB"


@pytest.mark.asyncio
async def test_action_plan_com_vinculacao_a_deliverable(db_session) -> None:
    """ActionPlan vinculado a Deliverable persiste."""
    from app.models import ActionPlan, ActionPlanStatus, Deliverable
    from sqlalchemy import select as _select

    project = await _seed_project(db_session, gp_email="gp-ap2@x.com")
    report = await _seed_full_report(db_session, project=project, total_deliv=2)
    deliv = (
        await db_session.execute(_select(Deliverable).limit(1))
    ).scalar_one()

    ap = ActionPlan(
        report_id=report.id,
        description="acelerar revisão técnica",
        objective="garantir d-001 entregue no prazo",
        linked_deliverable_id=deliv.id,
        status=ActionPlanStatus.OPEN,
    )
    db_session.add(ap)
    await db_session.commit()
    await db_session.refresh(ap)

    assert ap.linked_deliverable_id == deliv.id
    assert ap.linked_risk_id is None


@pytest.mark.asyncio
async def test_action_plan_sem_vinculacoes_eh_valido(db_session) -> None:
    """ActionPlan independente — sem linked_* — é permitido."""
    from app.models import ActionPlan, ActionPlanStatus

    project = await _seed_project(db_session, gp_email="gp-ap3@x.com")
    report = await _seed_full_report(db_session, project=project)

    ap = ActionPlan(
        report_id=report.id,
        description="documentar processo",
        objective="reduzir bus factor",
        status=ActionPlanStatus.OPEN,
    )
    db_session.add(ap)
    await db_session.commit()
    await db_session.refresh(ap)

    assert ap.linked_risk_id is None
    assert ap.linked_deliverable_id is None


@pytest.mark.asyncio
async def test_action_plan_set_null_quando_risk_deletado(db_session) -> None:
    """ON DELETE SET NULL: ao remover o risco, ActionPlan persiste com linked_risk_id=NULL.

    Comportamento esperado da migration 0011 (`ondelete="SET NULL"` na FK).
    Em SQLite (testes in-memory), `PRAGMA foreign_keys=ON` precisa estar ativo
    para que ON DELETE SET NULL funcione — o conftest já faz isso via event.
    """
    from app.models import ActionPlan, ActionPlanStatus
    from sqlalchemy import event as _event

    # Garantia: ativar FKs no SQLite para este teste
    conn = await db_session.connection()
    await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    project = await _seed_project(db_session, gp_email="gp-ap4@x.com")
    report = await _seed_full_report(db_session, project=project, risks=1)
    risk = (
        await db_session.execute(__import__("sqlalchemy").select(Risk).where(Risk.report_id == report.id))
    ).scalar_one()

    ap = ActionPlan(
        report_id=report.id,
        description="ação que vai virar órfã",
        objective="testar ON DELETE SET NULL",
        linked_risk_id=risk.id,
    )
    db_session.add(ap)
    await db_session.commit()
    ap_id = ap.id
    risk_id = risk.id

    # Deleta o risco
    await db_session.delete(risk)
    await db_session.commit()
    db_session.expire_all()

    refetched = await db_session.get(ActionPlan, ap_id)
    assert refetched is not None  # ActionPlan sobrevive
    assert refetched.linked_risk_id is None  # vinculação ficou NULL


@pytest.mark.asyncio
async def test_action_plan_objective_obrigatorio_no_schema_pydantic() -> None:
    """ActionPlanIn rejeita objective vazio ou ausente (validação Pydantic)."""
    from pydantic import ValidationError as _PydanticError

    from app.schemas.report import ActionPlanIn

    # Ausente → falha
    with pytest.raises(_PydanticError):
        ActionPlanIn(description="x")
    # Vazio → falha (min_length=1)
    with pytest.raises(_PydanticError):
        ActionPlanIn(description="x", objective="")
    # OK
    obj = ActionPlanIn(description="x", objective="por isso")
    assert obj.objective == "por isso"


@pytest.mark.asyncio
async def test_action_plan_expand_linked_descriptions_em_get_report(
    client: AsyncClient, db_session
) -> None:
    """GET /reports/{id} preenche linked_risk_description e linked_deliverable_title
    quando o ActionPlan tem vínculos. Spec v3.1 §4.2.4 — útil para UI da revisão PMO."""
    from app.models import ActionPlan, ActionPlanStatus, Deliverable
    from sqlalchemy import select as _select

    project = await _seed_project(db_session, gp_email="gp-ap6@x.com")
    report = await _seed_full_report(db_session, project=project, risks=1, total_deliv=2)
    risk = (
        await db_session.execute(_select(Risk).where(Risk.report_id == report.id))
    ).scalar_one()
    deliv = (
        await db_session.execute(_select(Deliverable).limit(1))
    ).scalar_one()
    db_session.add(ActionPlan(
        report_id=report.id,
        description="ação vinculada",
        objective="testar expansão",
        linked_risk_id=risk.id,
        linked_deliverable_id=deliv.id,
        status=ActionPlanStatus.OPEN,
    ))
    await db_session.commit()

    gp = await _login(client, role="GP", email="gp-ap6@x.com")
    r = await client.get(
        f"/reports/{report.id}", headers={"Authorization": f"Bearer {gp}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["action_plans"]) == 1
    ap = body["action_plans"][0]
    assert ap["objective"] == "testar expansão"
    # Expansão preenchida
    assert ap["linked_risk_description"] == risk.description
    assert ap["linked_deliverable_title"] == deliv.title


# ---------- F5.1 PendingItem: impact + open_date (v3.1 §4.2.5) ----------


@pytest.mark.asyncio
async def test_pending_item_impact_nullable_e_created_at_default(db_session) -> None:
    """`impact` aceita null e string; `created_at` cumpre `open_date` (default=now)."""
    from datetime import datetime as _dt

    project = await _seed_project(db_session, gp_email="gp-pi1@x.com")
    report = await _seed_full_report(db_session, project=project)

    p_sem = PendingItem(
        report_id=report.id,
        description="acesso ao Databricks ainda pendente",
        owner_party="client",
        status=PendingItemStatus.OPEN,
    )
    p_com = PendingItem(
        report_id=report.id,
        description="validação técnica da rotina IRRBB",
        owner_party="client",
        status=PendingItemStatus.OPEN,
        impact="Bloqueia entrega da Sprint 3 e fecha gate regulatório",
    )
    db_session.add_all([p_sem, p_com])
    await db_session.commit()
    await db_session.refresh(p_sem)
    await db_session.refresh(p_com)

    assert p_sem.impact is None
    assert p_com.impact.startswith("Bloqueia")
    # `created_at` cumpre `open_date` semanticamente — default=now sempre populado
    assert isinstance(p_sem.created_at, _dt)
    assert isinstance(p_com.created_at, _dt)


@pytest.mark.asyncio
async def test_pending_item_impact_rejeita_string_vazia_via_schema(db_session) -> None:
    """Validação Pydantic: description não pode ser vazia; impact pode ser
    null mas se preenchido aceita qualquer string."""
    from pydantic import ValidationError as _PV

    from app.schemas.report import PendingItemIn

    # description vazia → falha
    with pytest.raises(_PV):
        PendingItemIn(description="", impact="x")
    # impact null → OK
    obj = PendingItemIn(description="x")
    assert obj.impact is None
    # impact string → OK
    obj2 = PendingItemIn(description="x", impact="some impact")
    assert obj2.impact == "some impact"


@pytest.mark.asyncio
async def test_pending_item_payload_expoe_impact_e_created_at(
    client: AsyncClient, db_session
) -> None:
    """GET /reports/{id} retorna pending_items com impact + created_at."""
    project = await _seed_project(db_session, gp_email="gp-pi3@x.com")
    report = await _seed_full_report(db_session, project=project)
    db_session.add(PendingItem(
        report_id=report.id,
        description="cred. Databricks",
        owner_party="client",
        status=PendingItemStatus.OPEN,
        impact="atrasa Sprint 3",
    ))
    await db_session.commit()

    gp = await _login(client, role="GP", email="gp-pi3@x.com")
    r = await client.get(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
    )
    assert r.status_code == 200
    pendings = r.json()["pending_items"]
    assert len(pendings) == 1
    item = pendings[0]
    assert item["impact"] == "atrasa Sprint 3"
    assert item["created_at"] is not None


@pytest.mark.asyncio
async def test_compute_resolution_rate_pendings_resolved_vs_total(db_session) -> None:
    """3 abertas + 0 resolvidas → 0. Adiciona 2 resolvidas → 2/5 = 40."""
    project = await _seed_project(db_session, gp_email="gp-res@x.com")
    report = await _seed_full_report(db_session, project=project, pending_client=3)
    val = await health_score.compute_resolution_rate(db_session, report)
    assert val == 0.0

    # adiciona 2 resolvidas
    db_session.add_all(
        [
            PendingItem(
                report_id=report.id,
                description=f"resolvida-{i}",
                owner_party="client",
                status=PendingItemStatus.RESOLVED,
            )
            for i in range(2)
        ]
    )
    await db_session.commit()
    val2 = await health_score.compute_resolution_rate(db_session, report)
    # 2 resolvidas de 5 totais (3 abertas + 2 resolvidas) = 40
    assert abs(val2 - 40.0) < 0.5


async def _seed_n_reports_with_rag(
    db, project: Project, *, n: int, rags: list[str]
) -> None:
    """Cria n reports submetidos no mesmo projeto com os rag_status fornecidos.

    Não cria propostas/baselines/deliverables — só reports, suficiente para
    `compute_stability` que lê apenas `Report.rag_status` agregado.
    """
    for i in range(n):
        rag = RAGStatus(rags[i % len(rags)])
        r = Report(
            project_id=project.id,
            period_start=date(2026, 1 + i, 1),
            period_end=date(2026, 1 + i, 15),
            rag_prazo=rag,
            rag_escopo=rag,
            rag_qualidade=rag,
            rag_status=rag,
            status=ReportStatus.SUBMITTED,
            submitted_at=datetime.now(UTC),
            created_by_id=project.gp_user_id,
        )
        db.add(r)
    await db.commit()


@pytest.mark.asyncio
async def test_compute_stability_5_reports_iguais_verde(db_session) -> None:
    """≥5 reports todos no mesmo Verde → 100. Em Vermelho → 0. Em Amarelo → 50."""
    project = await _seed_project(db_session, gp_email="gp-stab@x.com")
    await _seed_n_reports_with_rag(db_session, project, n=5, rags=["G"])
    val = await health_score.compute_stability(db_session, project)
    assert val == 100.0


@pytest.mark.asyncio
async def test_compute_stability_oscilacao_da_30(db_session) -> None:
    """5 reports oscilando G→R → oscilação = 30."""
    project = await _seed_project(db_session, gp_email="gp-stab2@x.com")
    await _seed_n_reports_with_rag(
        db_session, project, n=5, rags=["G", "R", "G", "R", "G"]
    )
    val = await health_score.compute_stability(db_session, project)
    assert val == 30.0


@pytest.mark.asyncio
async def test_health_score_band_red_com_tudo_critico(db_session) -> None:
    """RAG=R + 4 criticais + 4 pending client + 0 done → score baixo."""
    project = await _seed_project(db_session, gp_email="gp2@x.com")
    await _seed_full_report(
        db_session,
        project=project,
        rag_p="R", rag_e="R", rag_q="R",
        risks=4, criticals=4,
        pending_client=4,
        deliverables_done=0, total_deliv=4,
    )
    breakdown = await health_score.compute_for_project(db_session, project.id)
    # Espera: rag_avg=0, risk_inverse=0, resolution_rate=0, stability=30 (1 report)
    # spi varia (sem started_at fixo), mas no pior caso ainda contribui pouco.
    # Score deve ficar em "atenção" ou "crítico" — band red OU amber é aceitavel.
    assert breakdown.rag_avg == 0.0
    assert breakdown.risk_inverse == 0.0
    assert breakdown.resolution_rate == 0.0
    assert breakdown.band in ("red", "amber")
    # Score significativamente abaixo do projeto "tudo OK" do próximo teste
    assert breakdown.score < 50


@pytest.mark.asyncio
async def test_health_score_band_green_com_tudo_ok(db_session) -> None:
    project = await _seed_project(db_session, gp_email="gp3@x.com")
    await _seed_full_report(
        db_session,
        project=project,
        rag_p="G", rag_e="G", rag_q="G",
        risks=0, criticals=0, pending_client=0,
        deliverables_done=4, total_deliv=4,
    )
    breakdown = await health_score.compute_for_project(db_session, project.id)
    assert breakdown.rag_avg == 100.0
    assert breakdown.risk_inverse == 100.0
    assert breakdown.resolution_rate == 100.0
    assert breakdown.band == "green"
    assert breakdown.score >= 70


@pytest.mark.asyncio
async def test_health_score_classificacao_textual_3_faixas(db_session) -> None:
    """Confirma faixas: ≥70 green, 40-69 amber, <40 red."""
    from app.services.health_score import _band

    assert _band(85) == "green"
    assert _band(70) == "green"
    assert _band(69.9) == "amber"
    assert _band(40) == "amber"
    assert _band(39.9) == "red"
    assert _band(0) == "red"


@pytest.mark.asyncio
async def test_health_score_bradesco_scenario_documental(
    db_session, capsys
) -> None:
    """Documental: cenário Bradesco-like realista expõe os 5 intermediários
    para validação manual da matemática (spec v3.1 §10.3).

    Cenário:
      - Projeto iniciado 2026-01-10, hoje fixado em 2026-05-11
      - Baseline ativo com 5 deliverables (due_dates entre fev/jun 2026)
      - Progresso real: 3 done, 1 in_progress 60%, 1 planejado 0%
      - 5 reports submetidos: 4 Verdes + 1 último com RAG misto (P=A, E=G, Q=G)
      - 1 risco crítico aberto no último report
      - 5 pendências no último: 4 resolved + 1 open
      - Pesos default 35/25/20/10/10
    """
    today = date(2026, 5, 11)
    start = date(2026, 1, 10)

    # Cria GP e projeto com started_at
    gp = User(name="GP-Br", email="gp-bradesco-doc@x.com",
              password_hash=hash_password("JumpDev123!"), role=Role.GP)
    db_session.add(gp)
    await db_session.flush()
    project = Project(
        name="SAS→Databricks", client_name="Bradesco",
        gp_user_id=gp.id, started_at=start,
    )
    db_session.add(project)
    await db_session.flush()

    # Proposal + Baseline ativo
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()

    # 5 deliverables com due_dates espalhadas pelo projeto
    deliv_specs = [
        ("d-001", "Análise SAS",             date(2026, 2, 15), 100),
        ("d-002", "Mapeamento dependências", date(2026, 3, 15), 100),
        ("d-003", "Migração rotina A",       date(2026, 4, 15), 100),
        ("d-004", "Migração rotina B",       date(2026, 5, 15),  60),
        ("d-005", "Validação Databricks",    date(2026, 6, 15),   0),
    ]
    delivs = []
    for code, title, due, _real in deliv_specs:
        d = Deliverable(
            baseline_id=baseline.id, code=code, title=title,
            phase="fase-1", complexity=DeliverableComplexity.MEDIUM, due_date=due,
        )
        db_session.add(d)
        delivs.append(d)
    await db_session.flush()

    # 5 reports submetidos (4 Verdes + 1 RAG misto no último)
    rags = [
        ("G", "G", "G", date(2026, 1, 31)),
        ("G", "G", "G", date(2026, 2, 28)),
        ("G", "G", "G", date(2026, 3, 31)),
        ("G", "G", "G", date(2026, 4, 30)),
        ("A", "G", "G", date(2026, 5, 10)),  # último — RAG misto
    ]
    last_report = None
    for i, (rp, re_, rq, pend) in enumerate(rags):
        # rag_status agregado = worst-of-3
        agg = RAGStatus(rp) if rp == "R" else (
            RAGStatus(re_) if re_ == "R" else (
                RAGStatus(rq) if rq == "R" else (
                    RAGStatus("A") if "A" in (rp, re_, rq) else RAGStatus("G")
                )
            )
        )
        r = Report(
            project_id=project.id,
            period_start=date(pend.year, pend.month, 1),
            period_end=pend,
            rag_prazo=RAGStatus(rp), rag_escopo=RAGStatus(re_), rag_qualidade=RAGStatus(rq),
            rag_status=agg, status=ReportStatus.SUBMITTED,
            submitted_at=datetime.now(UTC), created_by_id=gp.id,
        )
        db_session.add(r)
        await db_session.flush()
        last_report = r

    # DeliveryProgress no último report — 3 done, 1 60%, 1 0%
    assert last_report is not None
    for d, (_, _, _, pct) in zip(delivs, deliv_specs):
        st = (
            ProgressStatus.DONE if pct >= 100
            else ProgressStatus.IN_PROGRESS if pct > 0
            else ProgressStatus.PLANNED
        )
        db_session.add(
            DeliveryProgress(
                report_id=last_report.id, deliverable_id=d.id,
                status=st, percent_complete=pct,
            )
        )
    # 1 risco crítico aberto + 5 pendências (4 resolved + 1 open).
    # Alta×Alto → level=CRITICAL.
    db_session.add(Risk(
        report_id=last_report.id, description="Bug regulatório IRRBB",
        probability=RiskProbability.ALTA, impact=RiskImpact.ALTO,
        status=RiskStatus.IDENTIFIED,
    ))
    for i in range(4):
        db_session.add(PendingItem(
            report_id=last_report.id, description=f"resolved-{i}",
            owner_party="client", status=PendingItemStatus.RESOLVED,
        ))
    db_session.add(PendingItem(
        report_id=last_report.id, description="open-cliente",
        owner_party="client", status=PendingItemStatus.OPEN,
    ))
    await db_session.commit()

    # Computa cada componente individualmente para expor a matemática
    rag_avg = health_score.compute_rag_avg(last_report)
    # SPI precisa de hoje fixado — chamamos a função baixa-nível com `today`
    spi = await health_score.compute_spi(db_session, project, today=today)
    risk_inv = await health_score.compute_risk_inverse(db_session, last_report)
    res_rate = await health_score.compute_resolution_rate(db_session, last_report)
    stab = await health_score.compute_stability(db_session, project)

    # Agora score final (com pesos default)
    breakdown = await health_score.compute_for_project(db_session, project.id)
    # SPI no breakdown usa hoje real do sistema — só batemos os outros 4
    # componentes contra os intermediários. Para SPI, exibimos a versão
    # calculada com `today` fixado.
    weights = breakdown.weights_applied

    print("\n========== Validacao documental (spec v3.1 sec 10.3) ==========")
    print(f"Projeto: Bradesco SAS->Databricks (started_at=2026-01-10, hoje fixado=2026-05-11)")
    print(f"5 reports submetidos (G/G/G/G + A-G-G no último)")
    print()
    print("Componente 1 - rag_avg:")
    print(f"  Ultimo report: rag_prazo=A(50), rag_escopo=G(100), rag_qualidade=G(100)")
    print(f"  Media = (50 + 100 + 100) / 3 = {rag_avg}")
    print()
    print("Componente 2 - spi (com today=2026-05-11):")
    span_days = lambda d: (d - start).days
    for d, (_, t, due, real) in zip(delivs, deliv_specs):
        if due <= start: continue
        planned = max(0, min(100, (today - start).days / (due - start).days * 100))
        print(f"  {d.code} '{t}' due={due} → %planejado={planned:.1f} | %real={real}")
    print(f"  SPI = média(reais) / média(planejados) × 100, cap 100 = {spi:.1f}")
    print()
    print("Componente 3 - risk_inverse:")
    print(f"  1 risco critico aberto (valor=100, peso=100)")
    print(f"  Media ponderada = (100*100) / 100 = 100")
    print(f"  Inverso = 100 - 100 = {risk_inv}")
    print()
    print("Componente 4 - resolution_rate:")
    print(f"  Pendencias no report: 4 resolved + 1 open = 5 total")
    print(f"  Taxa = 4/5 * 100 = {res_rate}")
    print()
    print("Componente 5 - stability:")
    print(f"  Ultimos 5 reports (rag agregado, mais recente primeiro):")
    print(f"  [A, G, G, G, G] - oscilou no ultimo, nao todos iguais")
    print(f"  -> 30 (heuristica 'oscilacao ou <3 reports iguais')")
    print(f"  Calculado: {stab}")
    print()
    print(f"Pesos aplicados: {weights}")
    print(f"Score = {rag_avg:.1f}*{weights['rag_avg']} + {spi:.1f}*{weights['spi']} "
          f"+ {risk_inv:.1f}*{weights['risk_inverse']} + {res_rate:.1f}*{weights['resolution_rate']} "
          f"+ {stab:.1f}*{weights['stability']}")
    score_manual = (
        rag_avg * weights['rag_avg']
        + spi * weights['spi']
        + risk_inv * weights['risk_inverse']
        + res_rate * weights['resolution_rate']
        + stab * weights['stability']
    )
    print(f"     = {score_manual:.2f} (band={health_score._band(score_manual)})")
    print()
    print(f"breakdown.score (sistema, com today=runtime): {breakdown.score} "
          f"(band={breakdown.band})")
    print("======================================================\n")

    # Asserts: matemática bate com expectativa
    assert rag_avg == pytest.approx(83.333, abs=0.01)
    assert risk_inv == 0.0
    assert res_rate == 80.0
    assert stab == 30.0
    # SPI esperado: span de cada deliverable:
    # d-001: due 2026-02-15, span=36d; elapsed_today=122d → planned=cap(100), real=100 ✓
    # d-002: due 2026-03-15, span=64d; elapsed_today=122d → planned=cap(100), real=100 ✓
    # d-003: due 2026-04-15, span=95d; elapsed_today=122d → planned=cap(100), real=100 ✓
    # d-004: due 2026-05-15, span=125d; elapsed_today=122d → planned=97.6, real=60
    # d-005: due 2026-06-15, span=156d; elapsed_today=122d → planned=78.2, real=0
    # média_real = (100+100+100+60+0)/5 = 72
    # média_planejado = (100+100+100+97.6+78.2)/5 = 95.16
    # SPI = 72/95.16 × 100 = 75.66
    assert spi == pytest.approx(75.66, abs=0.5)


# ---------- AJUSTE I: DeliveryProgress.acceptance_confirmed (spec v3.1 §4.2.2) ----------


@pytest.mark.asyncio
async def test_patch_progress_done_100_sem_acceptance_falha(
    client: AsyncClient, db_session
) -> None:
    """status=done + percent_complete=100 sem acceptance_confirmed=true → 400."""
    project = await _seed_project(db_session, gp_email="gp-acc1@x.com")
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()
    deliv = Deliverable(
        baseline_id=baseline.id, code="d-001", title="Entregavel",
        phase="fase-1", due_date=date(2026, 6, 1),
    )
    db_session.add(deliv)
    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1), period_end=date(2026, 5, 15),
        status=ReportStatus.DRAFT, created_by_id=project.gp_user_id,
    )
    db_session.add(report)
    await db_session.commit()

    gp = await _login(client, role="GP", email="gp-acc1@x.com")
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={
            "progresses": [
                {
                    "deliverable_id": str(deliv.id),
                    "status": "done",
                    "percent_complete": 100,
                    # acceptance_confirmed AUSENTE — backend rejeita
                }
            ]
        },
    )
    assert r.status_code == 400, r.text
    assert "aceite" in r.text.lower()


@pytest.mark.asyncio
async def test_patch_progress_done_100_com_acceptance_persiste(
    client: AsyncClient, db_session
) -> None:
    """status=done + percent_complete=100 + acceptance_confirmed=true → 200 e persiste."""
    project = await _seed_project(db_session, gp_email="gp-acc2@x.com")
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="b" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()
    deliv = Deliverable(
        baseline_id=baseline.id, code="d-001", title="Entregavel",
        phase="fase-1", due_date=date(2026, 6, 1),
    )
    db_session.add(deliv)
    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1), period_end=date(2026, 5, 15),
        status=ReportStatus.DRAFT, created_by_id=project.gp_user_id,
    )
    db_session.add(report)
    await db_session.commit()

    gp = await _login(client, role="GP", email="gp-acc2@x.com")
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={
            "progresses": [
                {
                    "deliverable_id": str(deliv.id),
                    "status": "done",
                    "percent_complete": 100,
                    "acceptance_confirmed": True,
                }
            ]
        },
    )
    assert r.status_code == 200, r.text

    # Verifica persistência no banco
    from app.models import DeliveryProgress as _DP

    rows = (
        await db_session.execute(
            __import__("sqlalchemy").select(_DP).where(_DP.report_id == report.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].acceptance_confirmed is True


@pytest.mark.asyncio
async def test_patch_progress_parcial_nao_exige_acceptance(
    client: AsyncClient, db_session
) -> None:
    """Progressos parciais (status != done OU percent < 100) não passam pela
    validação — acceptance_confirmed continua opcional (nullable)."""
    project = await _seed_project(db_session, gp_email="gp-acc3@x.com")
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="c" * 64,
        original_filename="p.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add(proposal)
    await db_session.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db_session.add(baseline)
    await db_session.flush()
    deliv = Deliverable(
        baseline_id=baseline.id, code="d-001", title="Entregavel",
        phase="fase-1", due_date=date(2026, 6, 1),
    )
    db_session.add(deliv)
    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1), period_end=date(2026, 5, 15),
        status=ReportStatus.DRAFT, created_by_id=project.gp_user_id,
    )
    db_session.add(report)
    await db_session.commit()

    gp = await _login(client, role="GP", email="gp-acc3@x.com")
    # in_progress 60% sem acceptance_confirmed → OK
    r = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={
            "progresses": [
                {
                    "deliverable_id": str(deliv.id),
                    "status": "in_progress",
                    "percent_complete": 60,
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    # done com pct < 100 → também OK (estado raro mas válido)
    r2 = await client.patch(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {gp}"},
        json={
            "progresses": [
                {
                    "deliverable_id": str(deliv.id),
                    "status": "done",
                    "percent_complete": 90,
                }
            ]
        },
    )
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_health_score_cached_persistido_no_project_apos_submit(
    client: AsyncClient, db_session
) -> None:
    """spec v3.1 §10.3: 'Recálculo a cada submissão de report' grava
    em Project.health_score_cached."""
    project = await _seed_project(db_session, gp_email="gp-cache@x.com")
    # antes: cache None
    assert project.health_score_cached is None

    report = await _seed_full_report(
        db_session,
        project=project,
        rag_p="G", rag_e="G", rag_q="G",
        deliverables_done=4, total_deliv=4,
    )
    breakdown = await health_score.compute_for_project(db_session, project.id)
    await health_score.cache_to_report(db_session, report, breakdown.score)
    await db_session.refresh(project)
    assert project.health_score_cached is not None
    assert abs(project.health_score_cached - breakdown.score) < 0.01


@pytest.mark.asyncio
async def test_portfolio_overview_so_pmo_e_operator(client: AsyncClient) -> None:
    gp = await _login(client, role="GP", email="gp4@x.com")
    r = await client.get("/portfolio", headers={"Authorization": f"Bearer {gp}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_portfolio_overview_pmo_lista_projetos(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(db_session, gp_email="gp5@x.com")
    pmo = await _login(client, role="PMO", email="pmo1@x.com")
    r = await client.get("/portfolio", headers={"Authorization": f"Bearer {pmo}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_projects"] >= 1
    assert any(p["project_id"] == str(project.id) for p in body["projects"])
    assert "counts_by_band" in body


@pytest.mark.asyncio
async def test_update_portfolio_config_so_pmo(client: AsyncClient) -> None:
    pmo = await _login(client, role="PMO", email="pmo2@x.com")
    op = await _login(client, role="OPERATOR", email="op1@x.com")

    valid_payload = {
        "health_score_weights": {
            "rag_avg": 0.35,
            "spi": 0.25,
            "risk_inverse": 0.20,
            "resolution_rate": 0.10,
            "stability": 0.10,
        }
    }
    # OPERATOR não pode editar
    r = await client.put(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {op}"},
        json=valid_payload,
    )
    assert r.status_code == 403

    # PMO pode editar
    r2 = await client.put(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {pmo}"},
        json=valid_payload,
    )
    assert r2.status_code == 200, r2.text
    weights = r2.json()["health_score_weights"]
    assert weights["rag_avg"] == 0.35
    assert weights["stability"] == 0.10

    # Soma fora de 1.00 ± 0.01 é rejeitada (validação no schema Pydantic)
    bad_payload = {
        "health_score_weights": {
            "rag_avg": 0.5,
            "spi": 0.5,
            "risk_inverse": 0.5,
            "resolution_rate": 0.5,
            "stability": 0.5,
        }
    }
    r3 = await client.put(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {pmo}"},
        json=bad_payload,
    )
    assert r3.status_code == 422  # Pydantic validation error
    assert "1.00" in r3.text or "soma" in r3.text.lower()


@pytest.mark.asyncio
async def test_patch_portfolio_config_alias_do_put(client: AsyncClient) -> None:
    """spec v3.1 §10.3 lista PATCH como verbo do update — alias do PUT."""
    pmo = await _login(client, role="PMO", email="pmo-patch@x.com")
    payload = {
        "health_score_weights": {
            "rag_avg": 0.40,
            "spi": 0.20,
            "risk_inverse": 0.20,
            "resolution_rate": 0.10,
            "stability": 0.10,
        }
    }
    r = await client.patch(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {pmo}"},
        json=payload,
    )
    assert r.status_code == 200, r.text
    assert r.json()["health_score_weights"]["rag_avg"] == 0.40


@pytest.mark.asyncio
async def test_health_score_breakdown_endpoint(
    client: AsyncClient, db_session
) -> None:
    """spec v3.1 §10.3: GET /projects/{id}/health-score-breakdown retorna
    componentes individuais para tooltip do gauge."""
    project = await _seed_project(db_session, gp_email="gp-bd@x.com")
    await _seed_full_report(
        db_session,
        project=project,
        rag_p="G", rag_e="A", rag_q="G",
    )
    pmo = await _login(client, role="PMO", email="pmo-bd@x.com")
    r = await client.get(
        f"/projects/{project.id}/health-score-breakdown",
        headers={"Authorization": f"Bearer {pmo}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "score" in body
    assert "band" in body
    assert set(body["components"].keys()) == {
        "rag_avg", "spi", "risk_inverse", "resolution_rate", "stability"
    }
    assert "weights_applied" in body


# ---------- Aprovação 3 estágios ----------


@pytest.mark.asyncio
async def test_aprovacao_pmo_avanca_para_pmo_approved(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(db_session, gp_email="gp6@x.com", client_email="cli6@x.com")
    report = await _seed_full_report(db_session, project=project)
    pmo = await _login(client, role="PMO", email="pmo3@x.com")

    r = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "approved", "comment": "ok"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "pmo"
    assert body["decision"] == "approved"

    # report agora PMO_APPROVED
    rep_get = await client.get(
        f"/reports/{report.id}", headers={"Authorization": f"Bearer {pmo}"}
    )
    assert rep_get.json()["status"] == "pmo_approved"


@pytest.mark.asyncio
async def test_aprovacao_pmo_requested_changes_exige_comentario(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(db_session, gp_email="gp7@x.com")
    report = await _seed_full_report(db_session, project=project)
    pmo = await _login(client, role="PMO", email="pmo4@x.com")

    r = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "requested_changes"},
    )
    assert r.status_code == 400
    assert "comentário" in r.text.lower()

    r2 = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "requested_changes", "comment": "RAG inconsistente"},
    )
    assert r2.status_code == 200
    rep_get = await client.get(
        f"/reports/{report.id}", headers={"Authorization": f"Bearer {pmo}"}
    )
    assert rep_get.json()["status"] == "needs_revision"


@pytest.mark.asyncio
async def test_aprovacao_pmo_com_comentario_exige_comment_e_libera_para_cliente(
    client: AsyncClient, db_session
) -> None:
    """AJUSTE A: APPROVED_WITH_COMMENT exige comment e segue para PMO_APPROVED."""
    project = await _seed_project(
        db_session, gp_email="gp-awc@x.com", client_email="cli-awc@x.com"
    )
    report = await _seed_full_report(db_session, project=project)
    pmo = await _login(client, role="PMO", email="pmo-awc@x.com")

    # Sem comment → 400
    r = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "approved_with_comment"},
    )
    assert r.status_code == 400, r.text
    assert "comentário" in r.text.lower()

    # Comment vazio → 400
    r2 = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "approved_with_comment", "comment": "   "},
    )
    assert r2.status_code == 400

    # Com comment → 200; status vai a PMO_APPROVED (mesmo destino de APPROVED)
    r3 = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={
            "decision": "approved_with_comment",
            "comment": "ok, mas atenção a X no próximo report",
        },
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["decision"] == "approved_with_comment"
    assert body["comment"] == "ok, mas atenção a X no próximo report"

    rep_get = await client.get(
        f"/reports/{report.id}", headers={"Authorization": f"Bearer {pmo}"}
    )
    assert rep_get.json()["status"] == "pmo_approved"


@pytest.mark.asyncio
async def test_cliente_nao_ve_comment_de_aprovacao_pmo(
    client: AsyncClient, db_session
) -> None:
    """AJUSTE A: o comment de APPROVED_WITH_COMMENT é nota interna ao GP/PMO,
    nunca aparece no payload do Portal do Cliente."""
    project = await _seed_project(
        db_session, gp_email="gp-noseg@x.com", client_email="cli-noseg@x.com"
    )
    report = await _seed_full_report(db_session, project=project)
    pmo = await _login(client, role="PMO", email="pmo-noseg@x.com")
    secret = "NOTA INTERNA — não pode vazar pro cliente"

    # PMO aprova com comentário
    r = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"decision": "approved_with_comment", "comment": secret},
    )
    assert r.status_code == 200, r.text

    # Cliente vê seu projeto: comment NÃO pode aparecer em lugar nenhum do payload
    cli = await _login(client, role="CLIENT", email="cli-noseg@x.com")
    r_list = await client.get(
        "/client/projects", headers={"Authorization": f"Bearer {cli}"}
    )
    assert r_list.status_code == 200
    assert secret not in r_list.text

    r_one = await client.get(
        f"/client/projects/{project.id}", headers={"Authorization": f"Bearer {cli}"}
    )
    assert r_one.status_code == 200
    assert secret not in r_one.text


@pytest.mark.asyncio
async def test_cliente_so_aprova_pos_pmo(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(db_session, gp_email="gp8@x.com", client_email="cli8@x.com")
    report = await _seed_full_report(db_session, project=project)
    cli = await _login(client, role="CLIENT", email="cli8@x.com")

    # Submitted ainda → cliente NÃO pode decidir
    r = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {cli}"},
        json={"decision": "approved"},
    )
    assert r.status_code == 403

    # Promove para PMO_APPROVED manualmente via DB
    report_db = await db_session.get(Report, report.id)
    report_db.status = ReportStatus.PMO_APPROVED
    await db_session.commit()

    r2 = await client.post(
        f"/reports/{report.id}/decide",
        headers={"Authorization": f"Bearer {cli}"},
        json={"decision": "approved"},
    )
    assert r2.status_code == 200
    rep_get = await client.get(
        f"/reports/{report.id}",
        headers={"Authorization": f"Bearer {await _login(client, role='PMO', email='pmo-x@x.com')}"},
    )
    assert rep_get.json()["status"] == "client_released"


# ---------- Portal Cliente ----------


@pytest.mark.asyncio
async def test_portal_cliente_so_ve_proprio_projeto(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(
        db_session, gp_email="gp9@x.com", client_email="cli9@x.com"
    )
    cli = await _login(client, role="CLIENT", email="cli9@x.com")
    r = await client.get("/client/projects", headers={"Authorization": f"Bearer {cli}"})
    assert r.status_code == 200
    body = r.json()
    assert any(p["id"] == str(project.id) for p in body)


@pytest.mark.asyncio
async def test_portal_cliente_recusa_outros_projetos(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(
        db_session, gp_email="gp10@x.com", client_email="cli10@x.com"
    )
    cli_outro = await _login(client, role="CLIENT", email="outro@x.com")
    r = await client.get(
        f"/client/projects/{project.id}",
        headers={"Authorization": f"Bearer {cli_outro}"},
    )
    assert r.status_code == 403


# ---------- Diff de baselines ----------


@pytest.mark.asyncio
async def test_diff_de_baselines_detecta_added_removed_changed(
    client: AsyncClient, db_session
) -> None:
    project = await _seed_project(db_session, gp_email="gp-diff@x.com")
    p1 = Proposal(
        project_id=project.id, version=1, file_url="a", file_sha256="a" * 64,
        original_filename="v1.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    p2 = Proposal(
        project_id=project.id, version=2, file_url="b", file_sha256="b" * 64,
        original_filename="v2.pdf", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=project.gp_user_id,
    )
    db_session.add_all([p1, p2])
    await db_session.flush()

    b1 = Baseline(project_id=project.id, proposal_id=p1.id, status=BaselineStatus.ACTIVE, payload={})
    b2 = Baseline(project_id=project.id, proposal_id=p2.id, status=BaselineStatus.DRAFT, payload={})
    db_session.add_all([b1, b2])
    await db_session.flush()
    db_session.add_all([
        Deliverable(baseline_id=b1.id, code="d-001", title="A", phase="f1"),
        Deliverable(baseline_id=b1.id, code="d-002", title="B", phase="f1"),
        Deliverable(baseline_id=b1.id, code="d-003", title="C antigo", phase="f1"),
        # b2: d-001 mantido, d-002 removido, d-003 mudou de título, d-004 NOVO
        Deliverable(baseline_id=b2.id, code="d-001", title="A", phase="f1"),
        Deliverable(baseline_id=b2.id, code="d-003", title="C novo", phase="f1"),
        Deliverable(baseline_id=b2.id, code="d-004", title="D adicional", phase="f2"),
    ])
    await db_session.commit()

    tok = await _login(client, role="GP", email="gp-diff@x.com")
    r = await client.get(
        f"/client/diff/{b1.id}/{b2.id}", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["added"]) == 1
    assert body["added"][0]["code"] == "d-004"
    assert len(body["removed"]) == 1
    assert body["removed"][0]["code"] == "d-002"
    assert len(body["changed"]) == 1
    assert body["changed"][0]["code"] == "d-003"
    # GET é read-only; não cria ScopeChanges. ScopeChanges são criados pelo worker
    # (ou via chamada explícita a `diff_baselines`).
    assert "scope_changes_created" not in body

    # Idempotência: chamar diff_baselines duas vezes não duplica ScopeChanges.
    # F5.2 commit 3: diff_baselines passou a cobrir MODIFIED (changed), então
    # neste cenário cria 3 ScopeChanges (1 added + 1 removed + 1 modified)
    # e usa baseline_to_id como chave de leitura (impact_baseline_id é legacy).
    from app.api.v1.client_portal import diff_baselines
    from app.models import ScopeChange
    from sqlalchemy import select as _select

    first = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert first["scope_changes_created"] == 3
    second = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert second["scope_changes_created"] == 0  # idempotente
    rows = (
        await db_session.execute(
            _select(ScopeChange).where(ScopeChange.baseline_to_id == b2.id)
        )
    ).scalars().all()
    assert len(rows) == 3


# ---------- Notificações ----------


@pytest.mark.asyncio
async def test_notifications_unread_count_e_mark_read(
    client: AsyncClient, db_session
) -> None:
    await _seed_project(db_session, gp_email="gp-not@x.com")
    pmo = await _login(client, role="PMO", email="pmo-not@x.com")

    # Submeter um report dispara notify_report_submitted (best-effort em testes)
    # Aqui só validamos os endpoints com seed manual de InAppNotification.
    from app.models import InAppNotification

    pmo_user = await db_session.execute(
        __import__("sqlalchemy").select(User).where(User.email == "pmo-not@x.com")
    )
    pmo_obj = pmo_user.scalar_one()
    n = InAppNotification(
        user_id=pmo_obj.id,
        kind="test",
        title="Olá",
        body="corpo",
    )
    db_session.add(n)
    await db_session.commit()

    r = await client.get("/notifications/unread-count", headers={"Authorization": f"Bearer {pmo}"})
    assert r.status_code == 200
    assert r.json()["unread"] >= 1

    r2 = await client.get("/notifications", headers={"Authorization": f"Bearer {pmo}"})
    assert r2.status_code == 200
    assert any(item["title"] == "Olá" for item in r2.json())

    r3 = await client.post(
        f"/notifications/{n.id}/read", headers={"Authorization": f"Bearer {pmo}"}
    )
    assert r3.status_code == 200
    assert r3.json()["read_at"] is not None

    r4 = await client.get("/notifications/unread-count", headers={"Authorization": f"Bearer {pmo}"})
    assert r4.json()["unread"] == 0


# ---------- Smoke do PortfolioConfig ----------


@pytest.mark.asyncio
async def test_portfolio_config_normaliza_quando_pesos_nao_somam_1(db_session) -> None:
    """Pesos 2/2/2/2/2 → soma 10; serviço normaliza para 0.2 cada e calcula corretamente.

    Defensivo: PortfolioConfig pode chegar com soma fora de 1.00 (migration de
    dados antigos, edição direta no DB). O serviço normaliza no momento do cálculo.
    """
    cfg = PortfolioConfig(
        id=1,
        health_score_weights={
            "rag_avg": 2.0,
            "spi": 2.0,
            "risk_inverse": 2.0,
            "resolution_rate": 2.0,
            "stability": 2.0,
        },
    )
    db_session.add(cfg)
    await db_session.commit()
    project = await _seed_project(db_session, gp_email="gp-cfg@x.com")
    breakdown = await health_score.compute_for_project(db_session, project.id)
    # Sem report → rag_avg=50, spi=100, risk_inv=100, res_rate=100, stab=50
    # Com pesos normalizados 0.2 cada: 0.2*(50+100+100+100+50) = 0.2*400 = 80
    assert abs(breakdown.score - 80.0) < 0.5
    # Pesos retornados pelo breakdown estão normalizados
    assert all(abs(w - 0.2) < 0.01 for w in breakdown.weights_applied.values())
