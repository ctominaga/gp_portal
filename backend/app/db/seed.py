"""Seed de usuários para desenvolvimento.

Uso:
    python -m app.db.seed
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User

SEED_PASSWORD = os.environ.get("DEV_SEED_PASSWORD", "JumpDev123!")

SEED_USERS: list[dict[str, str | Role]] = [
    {"name": "Ana PMO", "email": "ana.pmo@jumplabel.com.br", "role": Role.PMO},
    {"name": "GP Bradesco", "email": "gp.bradesco@jumplabel.com.br", "role": Role.GP},
    {"name": "Cliente Bradesco", "email": "cliente.bradesco@bradesco.com.br", "role": Role.CLIENT},
    {"name": "Operador Worker", "email": "operador@jumplabel.com.br", "role": Role.OPERATOR},
]


async def main() -> None:
    async with SessionLocal() as db:
        for spec in SEED_USERS:
            email = str(spec["email"]).lower()
            existing = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if existing:
                print(f"skip {email} (already exists)")
                continue
            user = User(
                name=str(spec["name"]),
                email=email,
                password_hash=hash_password(SEED_PASSWORD),
                role=spec["role"],  # type: ignore[arg-type]
            )
            db.add(user)
            print(f"create {email} role={spec['role'].value}")  # type: ignore[union-attr]
        await db.commit()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
