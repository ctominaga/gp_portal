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

    # Idempotência: chamar diff_baselines duas vezes não duplica ScopeChanges
    from app.api.v1.client_portal import diff_baselines
    from app.models import ScopeChange
    from sqlalchemy import select as _select

    first = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert first["scope_changes_created"] == 2
    second = await diff_baselines(
        db_session, project_id=project.id, base_baseline=b1, new_baseline=b2
    )
    assert second["scope_changes_created"] == 0  # idempotente
    rows = (
        await db_session.execute(
            _select(ScopeChange).where(ScopeChange.impact_baseline_id == b2.id)
        )
    ).scalars().all()
    assert len(rows) == 2


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
