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
    RiskStatus,
    Role,
    Severity,
    User,
)
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
    sevs = ["critical"] * criticals + ["high"] * (risks - criticals)
    for s in sevs:
        db.add(Risk(report_id=report.id, description="r", severity=Severity(s), status=RiskStatus.OPEN))
    for _ in range(pending_client):
        db.add(
            PendingItem(
                report_id=report.id, description="p", owner_party="client", status=PendingItemStatus.OPEN
            )
        )
    await db.commit()
    return report


# ---------- Health Score ----------


@pytest.mark.asyncio
async def test_health_score_default_quando_sem_report(db_session) -> None:
    project = await _seed_project(db_session, gp_email="gp1@x.com")
    breakdown = await health_score.compute_for_project(db_session, project.id)
    # Sem report submetido → progress=50 (neutro), risks=100, pendings=100, schedule=100
    assert breakdown.progress == 50.0
    assert breakdown.risks == 100.0
    assert breakdown.score >= 70  # default config dá > 70 nessa situação


@pytest.mark.asyncio
async def test_health_score_band_red_com_riscos_criticos(db_session) -> None:
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
    assert breakdown.band == "red"
    assert breakdown.score < 40


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
    assert breakdown.band == "green"
    assert breakdown.score >= 70


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

    r = await client.put(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {op}"},
        json={"weight_progress": 0.5, "weight_risks": 0.2, "weight_pendings": 0.1, "weight_schedule": 0.2},
    )
    assert r.status_code == 403

    r2 = await client.put(
        "/portfolio/config",
        headers={"Authorization": f"Bearer {pmo}"},
        json={"weight_progress": 0.5, "weight_risks": 0.2, "weight_pendings": 0.1, "weight_schedule": 0.2},
    )
    assert r2.status_code == 200
    assert r2.json()["weight_progress"] == 0.5


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
    assert body["scope_changes_created"] == 2  # added + removed


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
    """Pesos 2/2/2/2 → soma 8; backend normaliza para 0.25 cada e calcula corretamente."""
    cfg = PortfolioConfig(
        id=1,
        weight_progress=2.0,
        weight_risks=2.0,
        weight_pendings=2.0,
        weight_schedule=2.0,
    )
    db_session.add(cfg)
    await db_session.commit()
    project = await _seed_project(db_session, gp_email="gp-cfg@x.com")
    breakdown = await health_score.compute_for_project(db_session, project.id)
    # Sem report → score = 0.25 * 50 + 0.25 * 100 + 0.25 * 100 + 0.25 * 100 = 87.5
    assert abs(breakdown.score - 87.5) < 0.5
