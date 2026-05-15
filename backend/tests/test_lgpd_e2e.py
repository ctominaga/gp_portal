"""F5.7 — Fluxo E2E LGPD piloto.

Cobre o caminho feliz inteiro descrito em docs/lgpd.md §"Eliminação":

  1. Titular registra conta e pede eliminação via /me/data-deletion-request.
  2. Notificação ao DPO sai (dry-run) — christopher.tominaga@jumplabel.com.br.
  3. Recibo neutro chega ao titular sem prometer outcome.
  4. PMO faz login e atende o pedido via /admin/data-requests/{id}/fulfill.
  5. Titular tenta logar de novo — recebe 401 idêntico ao de senha errada.

Não inclui o caminho do export (já coberto em test_lgpd_export.py) nem o
caminho do criador externo (test_lgpd_deletion.py). Objetivo aqui é a
"costura" entre os 3 endpoints + login guard num cenário único.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import me as me_module
from app.models import (
    DataProcessingRecord,
    DPRequestStatus,
    DPRequestType,
    User,
)


@pytest.mark.asyncio
async def test_fluxo_e2e_titular_pede_pmo_atende_login_bloqueia(
    client: AsyncClient, db_session, monkeypatch
) -> None:
    sent_emails: list[dict[str, str]] = []

    def _capture(*, to: str, subject: str, body: str) -> None:
        sent_emails.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(me_module, "_send_email", _capture)

    # 1. Titular registra e loga.
    r_reg = await client.post(
        "/auth/register",
        json={
            "name": "Joana Titular",
            "email": "joana@example.com",
            "password": "JumpDev123!",
            "role": "CLIENT",
        },
    )
    assert r_reg.status_code == 201, r_reg.text
    r_login = await client.post(
        "/auth/login",
        json={"email": "joana@example.com", "password": "JumpDev123!"},
    )
    assert r_login.status_code == 200, r_login.text
    titular_tok = r_login.json()["access_token"]

    # 2. Titular pede eliminação.
    r_req = await client.post(
        "/me/data-deletion-request",
        headers={"Authorization": f"Bearer {titular_tok}"},
        json={"notes": "Encerramento do contrato em 2026-05-15."},
    )
    assert r_req.status_code == 201, r_req.text
    pedido = r_req.json()
    assert pedido["status"] == "pending"
    assert pedido["request_type"] == "deletion"
    pedido_id = pedido["id"]

    # 3. As 2 notificações saíram em dry-run.
    addrs = {e["to"] for e in sent_emails}
    assert "christopher.tominaga@jumplabel.com.br" in addrs
    assert "joana@example.com" in addrs
    titular_email = next(e for e in sent_emails if e["to"] == "joana@example.com")
    assert titular_email["subject"] == "Pedido recebido"
    # Recibo NÃO promete outcome — só confirma e dá SLA.
    assert "anonimização" not in titular_email["body"].lower()

    # 4. PMO loga e atende o pedido.
    await client.post(
        "/auth/register",
        json={
            "name": "PMO E2E",
            "email": "pmo-e2e@example.com",
            "password": "JumpDev123!",
            "role": "PMO",
        },
    )
    r_pmo = await client.post(
        "/auth/login",
        json={"email": "pmo-e2e@example.com", "password": "JumpDev123!"},
    )
    assert r_pmo.status_code == 200, r_pmo.text
    pmo_tok = r_pmo.json()["access_token"]

    r_fulfill = await client.post(
        f"/admin/data-requests/{pedido_id}/fulfill",
        headers={"Authorization": f"Bearer {pmo_tok}"},
    )
    assert r_fulfill.status_code == 200, r_fulfill.text
    final_record = r_fulfill.json()
    assert final_record["status"] == "fulfilled"
    assert final_record["fulfilled_at"] is not None
    assert final_record["handled_by_id"] is not None

    # Estado persistido: User anonimizado, request marcado FULFILLED.
    subject_uuid = uuid.UUID(final_record["subject_user_id"])
    refreshed = (
        await db_session.execute(
            select(User).where(User.id == subject_uuid)
        )
    ).scalar_one()
    assert refreshed.name == "Titular removido"
    assert refreshed.email == f"anonymized_{refreshed.id}@removed.local"
    assert refreshed.password_hash == ""
    assert refreshed.anonymized_at is not None

    pedido_uuid = uuid.UUID(pedido_id)
    dp_row = (
        await db_session.execute(
            select(DataProcessingRecord).where(
                DataProcessingRecord.id == pedido_uuid
            )
        )
    ).scalar_one()
    assert dp_row.status == DPRequestStatus.FULFILLED
    assert dp_row.request_type == DPRequestType.DELETION

    # 5. Titular tenta logar de novo — 401 com texto idêntico ao de
    # senha errada (não vazar a anonimização).
    r_relogin = await client.post(
        "/auth/login",
        json={"email": "joana@example.com", "password": "JumpDev123!"},
    )
    assert r_relogin.status_code == 401
    # Cross-check: erro de senha em outra conta tem o MESMO body.
    r_wrong = await client.post(
        "/auth/login",
        json={"email": "pmo-e2e@example.com", "password": "errada"},
    )
    assert r_wrong.status_code == 401
    assert r_relogin.json() == r_wrong.json()
    assert r_relogin.json()["detail"] == "credenciais inválidas"
