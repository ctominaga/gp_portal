"""F5.7 — GET /me/data-export.

4 cenários (briefing Commit 2):
  - smoke: ZIP não-vazio + headers application/zip + arquivos esperados
  - cobertura: 1 entrada por entidade vinculada (Project/Baseline/Deliverable/
    Report/Risk/PendingItem/ActionPlan/DeliveryProgress/Approval/ScopeChange/
    AgentRunLog/DataProcessingRecord) + log síncrono da extração
  - RBAC: 401 sem token; titulares distintos veem APENAS seus próprios dados
  - filtro CLIENT: não vaza Reports DRAFT/SUBMITTED, não vaza Approvals de
    outros aprovadores, não vaza AgentRunLog, não vaza projetos de terceiros
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.models import (
    ActionPlan,
    AgentRunLog,
    AgentRunStatus,
    ApprovalDecision,
    ApprovalStage,
    Baseline,
    BaselineStatus,
    DataProcessingRecord,
    Deliverable,
    DeliverableComplexity,
    DeliveryProgress,
    DPRequestStatus,
    DPRequestType,
    PendingItem,
    PendingItemStatus,
    ProgressStatus,
    Project,
    Proposal,
    ProposalStatus,
    Report,
    ReportApproval,
    ReportStatus,
    Risk,
    RiskImpact,
    RiskProbability,
    RiskStatus,
    Role,
    ScopeChange,
    ScopeChangeStatus,
    ScopeChangeType,
    TaskType,
    User,
)


# ---------- helpers ----------


async def _register_and_login(
    client: AsyncClient, *, name: str, email: str, role: str
) -> str:
    """Cria usuário (ou ignora 409) e devolve o JWT."""
    await client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": "JumpDev123!",
            "role": role,
        },
    )
    r = await client.post(
        "/auth/login", json={"email": email, "password": "JumpDev123!"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _open_zip(payload: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


# ---------- smoke ----------


@pytest.mark.asyncio
async def test_export_smoke_zip_basico(client: AsyncClient) -> None:
    """ZIP volta com Content-Type correto e contém os 5 arquivos canônicos."""
    tok = await _register_and_login(
        client, name="Alice", email="alice@example.com", role="GP"
    )

    r = await client.get(
        "/me/data-export", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/zip")
    assert "attachment" in r.headers["content-disposition"].lower()
    assert ".zip" in r.headers["content-disposition"].lower()

    files = _open_zip(r.content)
    assert set(files) == {
        "README.txt",
        "data_processing_records.json",
        "me.json",
        "projects_as_client.json",
        "projects_as_gp.json",
    }

    me = json.loads(files["me.json"])
    assert me["email"] == "alice@example.com"
    assert me["role"] == "GP"
    assert me["anonymized_at"] is None

    # Sem projetos seedados, as listas vêm vazias.
    assert json.loads(files["projects_as_gp.json"]) == []
    assert json.loads(files["projects_as_client.json"]) == []

    # README.txt menciona a política e o DPO designado.
    readme = files["README.txt"].decode("utf-8")
    assert "docs/lgpd.md" in readme
    assert "christopher.tominaga@jumplabel.com.br" in readme


# ---------- cobertura ----------


async def _seed_full_gp_dataset(db_session, *, gp_email: str) -> dict:
    """Cria 1 GP titular + 1 Project + 1 Baseline + 1 Deliverable +
    1 Report (com Risk/Pending/Action/Progress) + 1 Approval +
    1 ScopeChange + 1 AgentRunLog + 1 DataProcessingRecord pretérito.
    Retorna ids para asserções."""
    gp = User(
        name="GP Cob",
        email=gp_email,
        password_hash=hash_password("JumpDev123!"),
        role=Role.GP,
    )
    pmo = User(
        name="PMO",
        email="pmo-cob@x.com",
        password_hash=hash_password("JumpDev123!"),
        role=Role.PMO,
    )
    db_session.add_all([gp, pmo])
    await db_session.flush()

    project = Project(
        name="Projeto Cob",
        client_name="Cliente Cob",
        gp_user_id=gp.id,
    )
    db_session.add(project)
    await db_session.flush()

    proposal = Proposal(
        project_id=project.id,
        version=1,
        file_url="p.pdf",
        file_sha256="a" * 64,
        original_filename="p.pdf",
        size_bytes=1,
        status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db_session.add(proposal)
    await db_session.flush()

    baseline = Baseline(
        project_id=project.id,
        proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE,
        payload={"summary": "ok"},
    )
    db_session.add(baseline)
    await db_session.flush()

    deliverable = Deliverable(
        baseline_id=baseline.id,
        code="d-001",
        title="Migrar A",
        complexity=DeliverableComplexity.LOW,
    )
    db_session.add(deliverable)

    report = Report(
        project_id=project.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 7),
        status=ReportStatus.SUBMITTED,
        created_by_id=gp.id,
    )
    db_session.add(report)
    await db_session.flush()

    risk = Risk(
        report_id=report.id,
        description="Risco X",
        probability=RiskProbability.MEDIA,
        impact=RiskImpact.MEDIO,
        status=RiskStatus.IDENTIFIED,
    )
    pending = PendingItem(
        report_id=report.id,
        description="Pendência Y",
        owner_party="client",
        status=PendingItemStatus.OPEN,
    )
    action = ActionPlan(
        report_id=report.id,
        description="Ação Z",
        objective="Mitigar X",
    )
    progress = DeliveryProgress(
        report_id=report.id,
        deliverable_id=deliverable.id,
        status=ProgressStatus.IN_PROGRESS,
        percent_complete=40,
    )
    approval = ReportApproval(
        report_id=report.id,
        approver_id=pmo.id,
        stage=ApprovalStage.PMO,
        decision=ApprovalDecision.APPROVED,
    )
    scope_change = ScopeChange(
        project_id=project.id,
        description="Adicionado: novo entregável",
        baseline_to_id=baseline.id,
        change_type=ScopeChangeType.ADDED,
        deliverable_code="d-002",
        status=ScopeChangeStatus.PROPOSED,
    )
    agent_log = AgentRunLog(
        run_id="run-cob-1",
        task_type=TaskType.REPORT_ANALYSIS,
        project_id=project.id,
        report_id=report.id,
        engine_used="claude",
        status=AgentRunStatus.DONE,
    )
    dp_old = DataProcessingRecord(
        subject_user_id=gp.id,
        request_type=DPRequestType.ACCESS,
        status=DPRequestStatus.FULFILLED,
        notes="Pedido anterior fictício.",
    )
    db_session.add_all([
        risk, pending, action, progress, approval, scope_change, agent_log, dp_old
    ])
    await db_session.commit()

    return {
        "gp_id": gp.id,
        "project_id": project.id,
        "baseline_id": baseline.id,
        "deliverable_id": deliverable.id,
        "report_id": report.id,
        "risk_id": risk.id,
        "pending_id": pending.id,
        "action_id": action.id,
        "progress_id": progress.id,
        "approval_id": approval.id,
        "scope_change_id": scope_change.id,
        "agent_run_id": agent_log.run_id,
        "dp_old_id": dp_old.id,
    }


@pytest.mark.asyncio
async def test_export_cobertura_uma_entrada_por_entidade(
    client: AsyncClient, db_session
) -> None:
    ids = await _seed_full_gp_dataset(db_session, gp_email="gp-cob@x.com")
    tok = await _register_and_login(
        client, name="GP Cob", email="gp-cob@x.com", role="GP"
    )

    r = await client.get(
        "/me/data-export", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    files = _open_zip(r.content)

    projects_gp = json.loads(files["projects_as_gp.json"])
    assert len(projects_gp) == 1
    proj = projects_gp[0]
    assert proj["id"] == str(ids["project_id"])

    assert len(proj["baselines"]) == 1
    assert proj["baselines"][0]["id"] == str(ids["baseline_id"])
    assert len(proj["baselines"][0]["deliverables"]) == 1
    assert proj["baselines"][0]["deliverables"][0]["id"] == str(ids["deliverable_id"])

    assert len(proj["reports"]) == 1
    rep = proj["reports"][0]
    assert rep["id"] == str(ids["report_id"])
    assert len(rep["risks"]) == 1
    assert rep["risks"][0]["id"] == str(ids["risk_id"])
    assert len(rep["pending_items"]) == 1
    assert rep["pending_items"][0]["id"] == str(ids["pending_id"])
    assert len(rep["action_plans"]) == 1
    assert rep["action_plans"][0]["id"] == str(ids["action_id"])
    assert len(rep["delivery_progresses"]) == 1
    assert rep["delivery_progresses"][0]["id"] == str(ids["progress_id"])

    assert len(proj["approvals"]) == 1
    assert proj["approvals"][0]["id"] == str(ids["approval_id"])
    assert len(proj["scope_changes"]) == 1
    assert proj["scope_changes"][0]["id"] == str(ids["scope_change_id"])
    assert len(proj["agent_run_logs"]) == 1
    assert proj["agent_run_logs"][0]["run_id"] == ids["agent_run_id"]

    # O export é um snapshot do estado ANTES desta requisição. O log de
    # auditoria DESTE pedido (request_type=EXPORT) é criado pelo endpoint
    # depois do snapshot — fica no banco, fora do ZIP. Aparecerá em
    # exports subsequentes (auditoria recursiva, vide endpoint).
    dp = json.loads(files["data_processing_records.json"])
    assert len(dp) == 1
    assert dp[0]["request_type"] == "access"

    # Auditoria persistida: o pré-existente continua + o novo EXPORT registrado
    # no banco como FULFILLED, com handled_by_id == próprio titular.
    rows = list(
        (
            await db_session.execute(
                select(DataProcessingRecord).where(
                    DataProcessingRecord.subject_user_id == ids["gp_id"]
                )
            )
        ).scalars().all()
    )
    assert len(rows) == 2
    new_row = next(
        r for r in rows if r.request_type == DPRequestType.EXPORT
    )
    assert new_row.status == DPRequestStatus.FULFILLED
    assert new_row.fulfilled_at is not None
    assert new_row.handled_by_id == ids["gp_id"]


# ---------- RBAC ----------


@pytest.mark.asyncio
async def test_export_sem_token_devolve_401(client: AsyncClient) -> None:
    r = await client.get("/me/data-export")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_export_cross_user_so_devolve_proprios_dados(
    client: AsyncClient, db_session
) -> None:
    """Dois GPs distintos, cada um com seu projeto. Cada token só puxa o seu.

    Garante que `/me/data-export` é resolvido pelo JWT (subject), não por
    parâmetro de query ou request body — não há vetor de cross-user.
    """
    gp_a = User(
        name="GP A", email="gp-a@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    gp_b = User(
        name="GP B", email="gp-b@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    db_session.add_all([gp_a, gp_b])
    await db_session.flush()
    proj_a = Project(name="P-A", client_name="C-A", gp_user_id=gp_a.id)
    proj_b = Project(name="P-B", client_name="C-B", gp_user_id=gp_b.id)
    db_session.add_all([proj_a, proj_b])
    await db_session.commit()

    tok_a = await _register_and_login(
        client, name="GP A", email="gp-a@x.com", role="GP"
    )
    tok_b = await _register_and_login(
        client, name="GP B", email="gp-b@x.com", role="GP"
    )

    rA = await client.get(
        "/me/data-export", headers={"Authorization": f"Bearer {tok_a}"}
    )
    rB = await client.get(
        "/me/data-export", headers={"Authorization": f"Bearer {tok_b}"}
    )
    assert rA.status_code == 200 and rB.status_code == 200

    pA = json.loads(_open_zip(rA.content)["projects_as_gp.json"])
    pB = json.loads(_open_zip(rB.content)["projects_as_gp.json"])
    assert len(pA) == 1 and pA[0]["name"] == "P-A"
    assert len(pB) == 1 and pB[0]["name"] == "P-B"


# ---------- filtro CLIENT ----------


@pytest.mark.asyncio
async def test_export_filtro_client_minimiza_corretamente(
    client: AsyncClient, db_session
) -> None:
    """No papel de cliente, o export NÃO pode trazer:
       - Reports em status DRAFT/SUBMITTED/PMO_APPROVED/NEEDS_REVISION
       - Approvals em que o titular não foi o aprovador
       - AgentRunLog (uso interno do Sistema)
       - Projetos onde o titular não é client_user_id
    """
    gp = User(
        name="GP F", email="gp-f@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    pmo = User(
        name="PMO F", email="pmo-f@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.PMO,
    )
    cliente = User(
        name="Cliente F", email="cliente-f@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.CLIENT,
    )
    outro_cliente = User(
        name="Outro Cliente", email="outro@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.CLIENT,
    )
    db_session.add_all([gp, pmo, cliente, outro_cliente])
    await db_session.flush()

    proj_visivel = Project(
        name="Projeto do Cliente",
        client_name="Empresa F",
        gp_user_id=gp.id,
        client_user_id=cliente.id,
    )
    proj_outro = Project(
        name="Projeto de Terceiro",
        client_name="Outra Empresa",
        gp_user_id=gp.id,
        client_user_id=outro_cliente.id,
    )
    db_session.add_all([proj_visivel, proj_outro])
    await db_session.flush()

    rep_draft = Report(
        project_id=proj_visivel.id,
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 7),
        status=ReportStatus.DRAFT, created_by_id=gp.id,
    )
    rep_submitted = Report(
        project_id=proj_visivel.id,
        period_start=date(2026, 4, 8), period_end=date(2026, 4, 14),
        status=ReportStatus.SUBMITTED, created_by_id=gp.id,
    )
    rep_released = Report(
        project_id=proj_visivel.id,
        period_start=date(2026, 4, 15), period_end=date(2026, 4, 21),
        status=ReportStatus.CLIENT_RELEASED, created_by_id=gp.id,
    )
    rep_outro_proj = Report(
        project_id=proj_outro.id,
        period_start=date(2026, 4, 22), period_end=date(2026, 4, 28),
        status=ReportStatus.CLIENT_RELEASED, created_by_id=gp.id,
    )
    db_session.add_all([rep_draft, rep_submitted, rep_released, rep_outro_proj])
    await db_session.flush()

    appr_do_cliente = ReportApproval(
        report_id=rep_released.id, approver_id=cliente.id,
        stage=ApprovalStage.CLIENT, decision=ApprovalDecision.APPROVED,
    )
    appr_do_pmo = ReportApproval(
        report_id=rep_released.id, approver_id=pmo.id,
        stage=ApprovalStage.PMO, decision=ApprovalDecision.APPROVED,
    )
    agent_log = AgentRunLog(
        run_id="run-internal-1",
        task_type=TaskType.REPORT_ANALYSIS,
        project_id=proj_visivel.id,
        report_id=rep_released.id,
        status=AgentRunStatus.DONE,
    )
    db_session.add_all([appr_do_cliente, appr_do_pmo, agent_log])
    await db_session.commit()

    tok = await _register_and_login(
        client, name="Cliente F", email="cliente-f@x.com", role="CLIENT"
    )
    r = await client.get(
        "/me/data-export", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200, r.text
    files = _open_zip(r.content)

    # cliente nunca é GP — projects_as_gp vazio.
    assert json.loads(files["projects_as_gp.json"]) == []

    # projects_as_client: somente o projeto onde o titular é client_user_id.
    projects_client = json.loads(files["projects_as_client.json"])
    assert len(projects_client) == 1
    proj = projects_client[0]
    assert proj["id"] == str(proj_visivel.id)

    # Apenas 1 Report (o CLIENT_RELEASED). DRAFT/SUBMITTED ficam de fora.
    report_ids = [rep["id"] for rep in proj["reports"]]
    assert report_ids == [str(rep_released.id)]
    assert all(
        rep["status"] in ("client_released", "archived") for rep in proj["reports"]
    )

    # Apenas a aprovação do próprio cliente — não a do PMO.
    approver_ids = [a["approver_id"] for a in proj["approvals"]]
    assert approver_ids == [str(cliente.id)]

    # Nenhuma chave/atributo de AgentRunLog vaza para a visão CLIENT.
    assert "agent_run_logs" not in proj
    assert b"run-internal-1" not in files["projects_as_client.json"]
