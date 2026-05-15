"""F5.7 — POST /me/data-deletion-request + /admin/data-requests + login guard.

6 cenários (briefing Commit 3):
  1. titular logado cria pedido + dispara notificações dry-run (DPO + recibo)
  2. PMO cria pedido manual com subject_external_email
  3. fulfill anonimiza User corretamente (todos os campos zerados)
  4. fulfill é idempotente — chamar 2x não muda nada
  5. login pós-anonimização: 401 com texto IDÊNTICO ao de senha errada
  6. RBAC: CLIENT/GP não acessam /admin/data-requests
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import admin_data_requests as admin_module
from app.api.v1 import me as me_module
from app.core.security import hash_password
from app.models import (
    DataProcessingRecord,
    DPRequestStatus,
    DPRequestType,
    Role,
    User,
)


async def _register_and_login(
    client: AsyncClient, *, name: str, email: str, role: str
) -> str:
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


class _EmailRecorder:
    """Recolhe chamadas a _send_email — substitui o módulo Resend durante o teste."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, *, to: str, subject: str, body: str) -> None:
        self.calls.append({"to": to, "subject": subject, "body": body})


# ---------- 1. titular cria pedido + notificação dry-run ----------


@pytest.mark.asyncio
async def test_titular_cria_pedido_de_eliminacao_e_dispara_emails(
    client: AsyncClient, db_session, monkeypatch
) -> None:
    rec = _EmailRecorder()
    monkeypatch.setattr(me_module, "_send_email", rec)

    tok = await _register_and_login(
        client, name="Ana", email="ana-del@example.com", role="GP"
    )

    r = await client.post(
        "/me/data-deletion-request",
        headers={"Authorization": f"Bearer {tok}"},
        json={"notes": "Quero meus dados removidos."},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["request_type"] == "deletion"
    assert body["status"] == "pending"
    assert body["subject_external_email"] is None
    assert body["subject_user_id"] is not None
    assert body["notes"] == "Quero meus dados removidos."

    # 1 e-mail pro DPO, 1 e-mail neutro pro titular.
    assert len(rec.calls) == 2
    to_addrs = {c["to"] for c in rec.calls}
    assert "christopher.tominaga@jumplabel.com.br" in to_addrs
    assert "ana-del@example.com" in to_addrs
    titular_call = next(
        c for c in rec.calls if c["to"] == "ana-del@example.com"
    )
    # Recibo NÃO promete outcome — só confirma recebimento e SLA.
    assert titular_call["subject"] == "Pedido recebido"
    assert "retornaremos em até 15 dias úteis" in titular_call["body"]
    assert "anonimização" not in titular_call["body"].lower()
    assert "removed" not in titular_call["body"].lower()

    # Persistência: registro existe com PENDING + subject_user_id == ana.
    rows = list(
        (
            await db_session.execute(
                select(DataProcessingRecord)
                .where(DataProcessingRecord.request_type == DPRequestType.DELETION)
            )
        ).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].status == DPRequestStatus.PENDING
    assert rows[0].fulfilled_at is None


# ---------- 2. PMO cria pedido manual com subject_external_email ----------


@pytest.mark.asyncio
async def test_pmo_cria_pedido_manual_com_email_externo(
    client: AsyncClient, db_session
) -> None:
    tok = await _register_and_login(
        client, name="PMO Manual", email="pmo-manual@x.com", role="PMO"
    )

    r = await client.post(
        "/admin/data-requests",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "subject_external_email": "Externo@Cliente.Com",
            "request_type": "deletion",
            "notes": "Recebido por e-mail em 2026-05-15.",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # E-mail externo persiste em lowercase (mesma convenção do auth).
    assert body["subject_external_email"] == "externo@cliente.com"
    assert body["subject_user_id"] is None
    assert body["status"] == "pending"
    assert body["request_type"] == "deletion"

    rows = list(
        (await db_session.execute(select(DataProcessingRecord))).scalars().all()
    )
    assert len(rows) == 1
    assert rows[0].subject_external_email == "externo@cliente.com"


# ---------- 3. fulfill anonimiza User ----------


async def _seed_user_with_deletion_request(
    db_session, *, email: str
) -> tuple[User, DataProcessingRecord]:
    titular = User(
        name="Titular Real",
        email=email,
        password_hash=hash_password("JumpDev123!"),
        role=Role.CLIENT,
    )
    db_session.add(titular)
    await db_session.flush()
    record = DataProcessingRecord(
        subject_user_id=titular.id,
        request_type=DPRequestType.DELETION,
        status=DPRequestStatus.PENDING,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(titular)
    await db_session.refresh(record)
    return titular, record


@pytest.mark.asyncio
async def test_fulfill_anonimiza_user_completamente(
    client: AsyncClient, db_session
) -> None:
    titular, record = await _seed_user_with_deletion_request(
        db_session, email="vai-anonimizar@x.com"
    )
    tok = await _register_and_login(
        client, name="PMO Fulfill", email="pmo-fulfill@x.com", role="PMO"
    )

    r = await client.post(
        f"/admin/data-requests/{record.id}/fulfill",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "fulfilled"
    assert body["fulfilled_at"] is not None
    assert body["handled_by_id"] is not None

    # Estado do User após anonimização — todos os campos sensíveis zerados.
    await db_session.refresh(titular)
    assert titular.name == "Titular removido"
    assert titular.email == f"anonymized_{titular.id}@removed.local"
    assert titular.password_hash == ""
    assert titular.anonymized_at is not None
    # Role NÃO é alterado — necessário para integridade referencial
    # das FKs (ex: Project.gp_user_id continua apontando para o registro).
    assert titular.role == Role.CLIENT


# ---------- 4. fulfill idempotente ----------


@pytest.mark.asyncio
async def test_fulfill_eh_idempotente(client: AsyncClient, db_session) -> None:
    titular, record = await _seed_user_with_deletion_request(
        db_session, email="ja-anonimizado@x.com"
    )
    tok = await _register_and_login(
        client, name="PMO Idemp", email="pmo-idemp@x.com", role="PMO"
    )

    r1 = await client.post(
        f"/admin/data-requests/{record.id}/fulfill",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r1.status_code == 200

    # Captura estado pós-primeiro fulfill.
    await db_session.refresh(titular)
    anonymized_at_first = titular.anonymized_at
    email_first = titular.email
    name_first = titular.name

    # Segunda chamada: não muda nada.
    r2 = await client.post(
        f"/admin/data-requests/{record.id}/fulfill",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "fulfilled"

    await db_session.refresh(titular)
    assert titular.anonymized_at == anonymized_at_first
    assert titular.email == email_first
    assert titular.name == name_first


# ---------- 5. login pós-anonimização: 401 idêntico ----------


@pytest.mark.asyncio
async def test_login_pos_anonimizacao_retorna_texto_identico_ao_de_senha_errada(
    client: AsyncClient, db_session
) -> None:
    titular, record = await _seed_user_with_deletion_request(
        db_session, email="pre-anon@x.com"
    )
    tok = await _register_and_login(
        client, name="PMO Login", email="pmo-login@x.com", role="PMO"
    )
    rfulfill = await client.post(
        f"/admin/data-requests/{record.id}/fulfill",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert rfulfill.status_code == 200

    # 5a — tentativa de login com a credencial original (que agora é anonimizada).
    r_anon = await client.post(
        "/auth/login",
        json={"email": "pre-anon@x.com", "password": "JumpDev123!"},
    )
    assert r_anon.status_code == 401
    body_anon = r_anon.json()

    # 5b — tentativa de login com senha errada em conta diferente, ativa.
    r_wrong = await client.post(
        "/auth/login",
        json={"email": "pmo-login@x.com", "password": "errada!!"},
    )
    assert r_wrong.status_code == 401
    body_wrong = r_wrong.json()

    # Texto deve ser INDISTINGUÍVEL — não pode vazar a anonimização.
    assert body_anon == body_wrong
    assert body_anon["detail"] == "credenciais inválidas"


# ---------- 6. RBAC: CLIENT/GP não acessam /admin/data-requests ----------


@pytest.mark.asyncio
async def test_rbac_client_e_gp_recebem_403_no_admin(
    client: AsyncClient,
) -> None:
    tok_client = await _register_and_login(
        client, name="Cli RBAC", email="cli-rbac@x.com", role="CLIENT"
    )
    tok_gp = await _register_and_login(
        client, name="GP RBAC", email="gp-rbac@x.com", role="GP"
    )

    for tok in (tok_client, tok_gp):
        # GET list
        r1 = await client.get(
            "/admin/data-requests",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r1.status_code == 403, r1.text
        # POST create
        r2 = await client.post(
            "/admin/data-requests",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "subject_external_email": "x@y.com",
                "request_type": "deletion",
            },
        )
        assert r2.status_code == 403


# ---------- sanity check: o módulo admin_data_requests é registrado ----------


def test_admin_module_export() -> None:
    """Garante que o router está exposto — evita drift entre o admin_module
    e o main.py em refactors futuros."""
    assert hasattr(admin_module, "router")
    assert any(
        r.path.startswith("/admin/data-requests") for r in admin_module.router.routes
    )
