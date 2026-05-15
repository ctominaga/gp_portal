"""Seed idempotente do piloto (F5.9a Commit 3).

Cria 3 usuários canônicos para smoke imediato após deploy beta:
  - PMO Jump      → pmo@jumplabel.com.br        (role PMO)
  - GP Jump       → gp.bradesco@jumplabel.com.br (role GP)
  - CLIENT Dev    → cliente@bradesco-dev.local   (role CLIENT, domínio .local
                                                  sinaliza ambiente de teste)

Idempotente: cada email é checado via SELECT antes do INSERT — rodar 2x é
no-op (não recria, não altera senha existente).

Senhas vêm de env vars `SEED_PMO_PASSWORD`, `SEED_GP_PASSWORD`,
`SEED_CLIENT_PASSWORD`. Se vazias, geramos uma senha random e ECOAMOS no
log — operador precisa anotar. Default fixo é proibido (criar conta com
senha conhecida em produção é incidente de segurança).

Proteção contra prod real: o hook em `start.sh` SÓ chama este script
quando `ENVIRONMENT` em `{dev, beta, staging}` E `SEED_ON_STARTUP=true`.
Em `ENVIRONMENT=prod` o script ainda pode rodar via CLI direto, mas
emite um warning antes.

Uso:
  python scripts/seed_pilot.py                # idempotente, sai 0
  ENVIRONMENT=prod python scripts/seed_pilot.py  # avisa e prossegue
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


@dataclass(frozen=True)
class SeedSpec:
    name: str
    email: str
    role: Role
    password_env: str


_SEED_USERS: tuple[SeedSpec, ...] = (
    SeedSpec(
        name="PMO Jump (seed piloto)",
        email="pmo@jumplabel.com.br",
        role=Role.PMO,
        password_env="SEED_PMO_PASSWORD",
    ),
    SeedSpec(
        name="GP Bradesco (seed piloto)",
        email="gp.bradesco@jumplabel.com.br",
        role=Role.GP,
        password_env="SEED_GP_PASSWORD",
    ),
    SeedSpec(
        name="Cliente Bradesco Dev (seed piloto)",
        email="cliente@bradesco-dev.local",
        role=Role.CLIENT,
        password_env="SEED_CLIENT_PASSWORD",
    ),
)


def _resolve_password(env_name: str) -> tuple[str, bool]:
    """Retorna (senha, foi_gerada_random)."""
    val = os.environ.get(env_name, "").strip()
    if val:
        return val, False
    # Gera 24 bytes URL-safe (~32 chars). Operador anota do log e troca depois.
    return secrets.token_urlsafe(24), True


async def _seed_one(db: AsyncSession, spec: SeedSpec) -> dict:
    existing = (
        await db.execute(select(User).where(User.email == spec.email.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "email": spec.email,
            "action": "skipped",
            "reason": "already exists",
        }

    password, generated = _resolve_password(spec.password_env)
    user = User(
        name=spec.name,
        email=spec.email.lower(),
        password_hash=hash_password(password),
        role=spec.role,
    )
    db.add(user)
    await db.flush()
    return {
        "email": spec.email,
        "action": "created",
        "role": spec.role.value,
        "password_generated": generated,
        # Se geramos a senha, ecoamos AGORA (única chance). Não fica no DB
        # em texto plano — só na stdout do container/log do CI.
        "password_to_record": password if generated else None,
    }


async def run_seed() -> list[dict]:
    env = os.environ.get("ENVIRONMENT", "dev")
    if env == "prod":
        print(
            "[seed_pilot] WARNING: ENVIRONMENT=prod. Rodando seed mesmo "
            "assim (modo manual). O hook start.sh PULA prod automaticamente; "
            "se você chegou aqui via CLI, confirme que isto é intencional.",
            file=sys.stderr,
        )

    results: list[dict] = []
    async with SessionLocal() as session:
        for spec in _SEED_USERS:
            results.append(await _seed_one(session, spec))
        await session.commit()
    return results


def main() -> int:
    results = asyncio.run(run_seed())
    for r in results:
        if r["action"] == "skipped":
            print(f"[seed_pilot] {r['email']}: já existe — no-op")
        else:
            print(
                f"[seed_pilot] {r['email']} criado (role={r['role']})"
            )
            if r.get("password_generated"):
                print(
                    f"[seed_pilot] ⚠ senha gerada (anote): "
                    f"{r['password_to_record']}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
