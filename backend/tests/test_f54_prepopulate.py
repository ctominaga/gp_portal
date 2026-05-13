"""F5.4 commit 1 — service prepopulate_report (spec v3.1 §10.2).

Cobre:
  - Happy path com report anterior + baseline ACTIVE: herda Risks/PendingItems
    abertos, cria DeliveryProgress placeholders por janela.
  - Sem report anterior: cria report vazio (apenas DeliveryProgress da janela).
  - Sem baseline ACTIVE: 409 (PrepopulateConflict).
  - Idempotência: 2ª chamada no mesmo período levanta 409 com link.
  - Filtro Risk: só IDENTIFIED e MONITORING (não MATERIALIZED/MITIGATED).
  - Filtro PendingItem: só OPEN (não IN_PROGRESS/RESOLVED).
  - Janela DeliveryProgress: due_date dentro de [start - 30d, end].
  - Flags `is_prepopulated=True` em todos os filhos copiados.
  - Não-herança de ActionPlan (decisão Q5 = b).
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import (
    ActionPlan,
    ActionPlanStatus,
    Baseline,
    BaselineStatus,
    Deliverable,
    DeliveryProgress,
    PendingItem,
    PendingItemStatus,
    Project,
    Proposal,
    ProposalStatus,
    Report,
    ReportStatus,
    Risk,
    RiskImpact,
    RiskProbability,
    RiskStatus,
    Role,
    User,
)
from app.services.prepopulate import (
    PrepopulateConflict,
    PrepopulateError,
    prepopulate_report,
)


async def _seed_project_active_baseline(
    db, *, gp_email: str, with_deliverables: list[date] | None = None,
) -> tuple[Project, User, Baseline]:
    """Cria Project + GP + Baseline ACTIVE. Deliverables opcionais com due_date
    para exercitar a janela do DeliveryProgress.
    """
    gp = User(
        name="GP", email=gp_email.lower(),
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    db.add(gp)
    await db.flush()
    project = Project(name="P", client_name="C", gp_user_id=gp.id)
    db.add(project)
    await db.flush()
    proposal = Proposal(
        project_id=project.id, version=1, file_url="x", file_sha256="a" * 64,
        original_filename="p", size_bytes=1, status=ProposalStatus.EXTRACTED,
        uploaded_by_id=gp.id,
    )
    db.add(proposal)
    await db.flush()
    baseline = Baseline(
        project_id=project.id, proposal_id=proposal.id,
        status=BaselineStatus.ACTIVE, payload={},
    )
    db.add(baseline)
    await db.flush()
    for i, dd in enumerate(with_deliverables or []):
        db.add(
            Deliverable(
                baseline_id=baseline.id,
                code=f"d-{i:03d}",
                title=f"Entregavel {i}",
                due_date=dd,
            )
        )
    await db.commit()
    return project, gp, baseline


async def _seed_previous_report(
    db, *, project: Project, gp: User, period_start: date, period_end: date,
    risks: list[tuple[str, RiskStatus]] | None = None,
    pendings: list[tuple[str, PendingItemStatus]] | None = None,
) -> Report:
    report = Report(
        project_id=project.id, period_start=period_start, period_end=period_end,
        status=ReportStatus.CLIENT_RELEASED, created_by_id=gp.id,
    )
    db.add(report)
    await db.flush()
    for desc, st in (risks or []):
        db.add(
            Risk(
                report_id=report.id, description=desc,
                probability=RiskProbability.MEDIA, impact=RiskImpact.MEDIO,
                status=st,
            )
        )
    for desc, st in (pendings or []):
        db.add(
            PendingItem(
                report_id=report.id, description=desc, status=st,
                owner_party="client" if "cliente" in desc.lower() else "jump",
            )
        )
    await db.commit()
    return report


# ---------- Happy path ----------


@pytest.mark.asyncio
async def test_prepopulate_inherits_open_risks_and_open_pendings(db_session) -> None:
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-h1@x.com"
    )
    # Report anterior com 4 risks (2 abertos + MATERIALIZED + MITIGATED) e 3
    # pendings (2 OPEN + 1 RESOLVED).
    await _seed_previous_report(
        db_session, project=project, gp=gp,
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        risks=[
            ("Risk identificado", RiskStatus.IDENTIFIED),
            ("Risk monitorando", RiskStatus.MONITORING),
            ("Risk materializado", RiskStatus.MATERIALIZED),  # NÃO herda
            ("Risk mitigado", RiskStatus.MITIGATED),          # NÃO herda
        ],
        pendings=[
            ("Pendência cliente A", PendingItemStatus.OPEN),
            ("Pendência jump B", PendingItemStatus.OPEN),
            ("Pendência resolvida", PendingItemStatus.RESOLVED),  # NÃO herda
        ],
    )

    new_report = await prepopulate_report(
        db_session, project=project,
        period_start=date(2026, 4, 16), period_end=date(2026, 4, 30),
        creator_user_id=gp.id,
    )

    assert new_report.status == ReportStatus.DRAFT
    assert new_report.created_by_id == gp.id

    # 2 Risks herdados (só os abertos), todos is_prepopulated=True.
    inherited_risks = list(
        (
            await db_session.execute(
                select(Risk).where(Risk.report_id == new_report.id)
            )
        ).scalars().all()
    )
    assert len(inherited_risks) == 2
    assert all(r.is_prepopulated is True for r in inherited_risks)
    descs = {r.description for r in inherited_risks}
    assert descs == {"Risk identificado", "Risk monitorando"}

    # 2 PendingItems herdados (só os OPEN), todos is_prepopulated=True.
    inherited_pendings = list(
        (
            await db_session.execute(
                select(PendingItem).where(PendingItem.report_id == new_report.id)
            )
        ).scalars().all()
    )
    assert len(inherited_pendings) == 2
    assert all(p.is_prepopulated is True for p in inherited_pendings)
    # Owner_party preserved (briefing D).
    by_desc = {p.description: p for p in inherited_pendings}
    assert by_desc["Pendência cliente A"].owner_party == "client"
    assert by_desc["Pendência jump B"].owner_party == "jump"


@pytest.mark.asyncio
async def test_prepopulate_no_previous_report_returns_empty_except_deliv(
    db_session,
) -> None:
    """Primeiro report do projeto: zero Risks/Pendings herdados, mas
    placeholders de DeliveryProgress vêm da janela do baseline."""
    period_start = date(2026, 5, 1)
    period_end = date(2026, 5, 15)
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-h2@x.com",
        with_deliverables=[period_start + timedelta(days=5)],  # 1 deliverable na janela
    )

    new_report = await prepopulate_report(
        db_session, project=project,
        period_start=period_start, period_end=period_end,
        creator_user_id=gp.id,
    )

    risks_count = (
        await db_session.execute(select(Risk).where(Risk.report_id == new_report.id))
    ).scalars().all()
    pendings_count = (
        await db_session.execute(select(PendingItem).where(PendingItem.report_id == new_report.id))
    ).scalars().all()
    progs = list(
        (
            await db_session.execute(
                select(DeliveryProgress).where(DeliveryProgress.report_id == new_report.id)
            )
        ).scalars().all()
    )
    assert len(list(risks_count)) == 0
    assert len(list(pendings_count)) == 0
    assert len(progs) == 1
    assert progs[0].is_prepopulated is True


# ---------- Janela DeliveryProgress ----------


@pytest.mark.asyncio
async def test_prepopulate_deliv_window_includes_overdue_recent(db_session) -> None:
    """due_date 10 dias antes do period_start é incluído (dentro de 30d)."""
    period_start = date(2026, 5, 1)
    period_end = date(2026, 5, 15)
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-win@x.com",
        with_deliverables=[
            period_start - timedelta(days=10),  # atrasado recente: INCLUI
            period_start - timedelta(days=45),  # atrasado antigo: EXCLUI
            period_start + timedelta(days=5),   # dentro do período: INCLUI
            period_end + timedelta(days=1),     # depois do fim: EXCLUI
        ],
    )

    new_report = await prepopulate_report(
        db_session, project=project,
        period_start=period_start, period_end=period_end,
        creator_user_id=gp.id,
    )

    progs = list(
        (
            await db_session.execute(
                select(DeliveryProgress).where(DeliveryProgress.report_id == new_report.id)
            )
        ).scalars().all()
    )
    assert len(progs) == 2  # 2 dos 4 deliverables entram na janela


# ---------- Erros / cascata ----------


@pytest.mark.asyncio
async def test_prepopulate_idempotent_returns_409_on_duplicate_period(
    db_session,
) -> None:
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-idem@x.com"
    )
    period_start, period_end = date(2026, 5, 1), date(2026, 5, 15)
    # 1ª chamada OK.
    await prepopulate_report(
        db_session, project=project,
        period_start=period_start, period_end=period_end,
        creator_user_id=gp.id,
    )
    # 2ª chamada deve falhar.
    with pytest.raises(PrepopulateConflict) as exc:
        await prepopulate_report(
            db_session, project=project,
            period_start=period_start, period_end=period_end,
            creator_user_id=gp.id,
        )
    assert exc.value.http_status == 409
    assert "/reports/" in str(exc.value)  # mensagem contém link


@pytest.mark.asyncio
async def test_prepopulate_no_active_baseline_returns_409(db_session) -> None:
    # Cria projeto SEM baseline ativo
    gp = User(
        name="GP", email="gp-nbl@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="P sem baseline", client_name="C", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.commit()

    with pytest.raises(PrepopulateConflict) as exc:
        await prepopulate_report(
            db_session, project=project,
            period_start=date(2026, 5, 1), period_end=date(2026, 5, 15),
            creator_user_id=gp.id,
        )
    assert exc.value.http_status == 409
    assert "baseline ativo" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_prepopulate_period_start_after_end_returns_error(db_session) -> None:
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-bad@x.com"
    )
    with pytest.raises(PrepopulateError) as exc:
        await prepopulate_report(
            db_session, project=project,
            period_start=date(2026, 5, 20), period_end=date(2026, 5, 1),
            creator_user_id=gp.id,
        )
    assert exc.value.http_status == 400


# ---------- Não-herança de ActionPlan ----------


@pytest.mark.asyncio
async def test_prepopulate_does_not_inherit_action_plans(db_session) -> None:
    """ActionPlan abertos no report anterior NÃO entram no novo (decisão Q5 = b)."""
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-pp-ap@x.com"
    )
    prev = await _seed_previous_report(
        db_session, project=project, gp=gp,
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        risks=[("Risk", RiskStatus.IDENTIFIED)],
    )
    # ActionPlan aberto no anterior — não deve herdar.
    db_session.add(
        ActionPlan(
            report_id=prev.id, description="Plano A", objective="Mitigar",
            status=ActionPlanStatus.OPEN,
        )
    )
    await db_session.commit()

    new_report = await prepopulate_report(
        db_session, project=project,
        period_start=date(2026, 4, 16), period_end=date(2026, 4, 30),
        creator_user_id=gp.id,
    )
    aps = list(
        (
            await db_session.execute(
                select(ActionPlan).where(ActionPlan.report_id == new_report.id)
            )
        ).scalars().all()
    )
    assert aps == []


# ---------- Default da flag em criação manual ----------


# ---------- Endpoint POST /projects/{id}/reports/prepopulate ----------


async def _login(client, *, role: str, email: str) -> str:
    await client.post(
        "/auth/register",
        json={"name": role.title(), "email": email, "password": "JumpDev123!", "role": role},
    )
    r = await client.post("/auth/login", json={"email": email, "password": "JumpDev123!"})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_endpoint_prepopulate_happy_path(client, db_session) -> None:
    """201 Created retornando ReportPublic com filhos populados."""
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-ep-h@x.com",
        with_deliverables=[date(2026, 5, 5)],
    )
    await _seed_previous_report(
        db_session, project=project, gp=gp,
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        risks=[("Risk antigo", RiskStatus.MONITORING)],
        pendings=[("Pendência antiga", PendingItemStatus.OPEN)],
    )
    tok = await _login(client, role="GP", email="gp-ep-h@x.com")

    r = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"},
        json={"period_start": "2026-05-01", "period_end": "2026-05-15"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["period_start"] == "2026-05-01"
    assert len(body["risks"]) == 1
    assert body["risks"][0]["is_prepopulated"] is True
    assert len(body["pending_items"]) == 1
    assert body["pending_items"][0]["is_prepopulated"] is True
    assert len(body["progresses"]) == 1
    assert body["progresses"][0]["is_prepopulated"] is True


@pytest.mark.asyncio
async def test_endpoint_prepopulate_409_when_period_exists(client, db_session) -> None:
    """409 ao chamar 2x no mesmo período — mensagem contém link."""
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-ep-409d@x.com"
    )
    tok = await _login(client, role="GP", email="gp-ep-409d@x.com")
    body = {"period_start": "2026-05-01", "period_end": "2026-05-15"}
    r1 = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"}, json=body,
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"}, json=body,
    )
    assert r2.status_code == 409
    assert "/reports/" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_endpoint_prepopulate_409_when_no_active_baseline(
    client, db_session
) -> None:
    """Projeto sem baseline ACTIVE → 409 com mensagem clara."""
    gp = User(
        name="GP", email="gp-ep-nb@x.com",
        password_hash=hash_password("JumpDev123!"), role=Role.GP,
    )
    db_session.add(gp)
    await db_session.flush()
    project = Project(name="P", client_name="C", gp_user_id=gp.id)
    db_session.add(project)
    await db_session.commit()
    tok = await _login(client, role="GP", email="gp-ep-nb@x.com")

    r = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"},
        json={"period_start": "2026-05-01", "period_end": "2026-05-15"},
    )
    assert r.status_code == 409
    assert "baseline ativo" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_endpoint_prepopulate_403_for_non_owner_gp(client, db_session) -> None:
    project, _, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-ep-own@x.com"
    )
    other_tok = await _login(client, role="GP", email="gp-ep-other@x.com")
    r = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {other_tok}"},
        json={"period_start": "2026-05-01", "period_end": "2026-05-15"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_endpoint_prepopulate_400_when_start_after_end(
    client, db_session
) -> None:
    project, _, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-ep-400@x.com"
    )
    tok = await _login(client, role="GP", email="gp-ep-400@x.com")
    r = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"},
        json={"period_start": "2026-05-20", "period_end": "2026-05-01"},
    )
    assert r.status_code == 400


# ---------- Auto-zero da flag no PATCH (Commit 3) ----------


async def _seed_full_for_patch(client, db_session, *, gp_email: str):
    """Cria projeto + baseline + report pré-populado com 1 Risk, 1 PendingItem
    e 1 DeliveryProgress (todos is_prepopulated=True). Retorna report_id e token GP."""
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email=gp_email,
        with_deliverables=[date(2026, 5, 5)],
    )
    # Report anterior dá origem aos risks/pendings herdados.
    await _seed_previous_report(
        db_session, project=project, gp=gp,
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 15),
        risks=[("Risk herdado", RiskStatus.MONITORING)],
        pendings=[("Pendência herdada cliente", PendingItemStatus.OPEN)],
    )
    tok = await _login(client, role="GP", email=gp_email)
    r = await client.post(
        f"/projects/{project.id}/reports/prepopulate",
        headers={"Authorization": f"Bearer {tok}"},
        json={"period_start": "2026-05-01", "period_end": "2026-05-15"},
    )
    assert r.status_code == 201
    return r.json(), tok


@pytest.mark.asyncio
async def test_patch_keeps_flag_when_no_significant_change(client, db_session) -> None:
    """Re-send da lista sem alterar campos significativos preserva is_prepopulated."""
    rep, tok = await _seed_full_for_patch(client, db_session, gp_email="gp-az-1@x.com")
    # Re-envia exatamente o mesmo risco (sem mudar nada).
    original_risk = rep["risks"][0]
    r = await client.patch(
        f"/reports/{rep['id']}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"risks": [{
            "description": original_risk["description"],
            "probability": original_risk["probability"],
            "impact": original_risk["impact"],
            "mitigation_plan": original_risk["mitigation_plan"],
            "owner_id": original_risk["owner_id"],
            "due_date": original_risk["due_date"],
            "status": original_risk["status"],
        }]},
    )
    assert r.status_code == 200
    risks = r.json()["risks"]
    assert len(risks) == 1
    assert risks[0]["is_prepopulated"] is True  # preservada


@pytest.mark.asyncio
async def test_patch_zeros_flag_on_risk_description_edit(client, db_session) -> None:
    rep, tok = await _seed_full_for_patch(client, db_session, gp_email="gp-az-2@x.com")
    original_risk = rep["risks"][0]
    r = await client.patch(
        f"/reports/{rep['id']}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"risks": [{
            **{k: original_risk[k] for k in (
                "probability", "impact", "mitigation_plan", "owner_id", "due_date", "status"
            )},
            "description": "Risco re-redigido pelo GP",
        }]},
    )
    assert r.status_code == 200
    assert r.json()["risks"][0]["is_prepopulated"] is False


@pytest.mark.asyncio
async def test_patch_zeros_flag_on_pending_impact_edit(client, db_session) -> None:
    rep, tok = await _seed_full_for_patch(client, db_session, gp_email="gp-az-3@x.com")
    original = rep["pending_items"][0]
    r = await client.patch(
        f"/reports/{rep['id']}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"pending_items": [{
            "description": original["description"],
            "owner_party": original["owner_party"],
            "due_date": original["due_date"],
            "status": original["status"],
            "impact": "Bloqueia release de sprint 5",
        }]},
    )
    assert r.status_code == 200
    assert r.json()["pending_items"][0]["is_prepopulated"] is False


@pytest.mark.asyncio
async def test_patch_zeros_flag_on_progress_percent_edit(client, db_session) -> None:
    rep, tok = await _seed_full_for_patch(client, db_session, gp_email="gp-az-4@x.com")
    original = rep["progresses"][0]
    r = await client.patch(
        f"/reports/{rep['id']}",
        headers={"Authorization": f"Bearer {tok}"},
        json={"progresses": [{
            "deliverable_id": original["deliverable_id"],
            "status": "in_progress",
            "percent_complete": 50,
            "comment": None,
            "revised_date": None,
            "acceptance_confirmed": None,
        }]},
    )
    assert r.status_code == 200
    assert r.json()["progresses"][0]["is_prepopulated"] is False


@pytest.mark.asyncio
async def test_default_is_prepopulated_false_on_manual_create(db_session) -> None:
    """Garante que registros criados pelo fluxo normal (não-prepopulate) vêm
    com is_prepopulated=False. Defesa contra mudança acidental do default."""
    project, gp, _ = await _seed_project_active_baseline(
        db_session, gp_email="gp-default@x.com"
    )
    report = Report(
        project_id=project.id, period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 15), status=ReportStatus.DRAFT, created_by_id=gp.id,
    )
    db_session.add(report)
    await db_session.flush()
    risk = Risk(
        report_id=report.id, description="manual",
        probability=RiskProbability.MEDIA, impact=RiskImpact.MEDIO,
        status=RiskStatus.IDENTIFIED,
    )
    db_session.add(risk)
    await db_session.commit()
    await db_session.refresh(risk)
    assert risk.is_prepopulated is False
