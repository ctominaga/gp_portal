#!/usr/bin/env bash
###############################################################################
# Backend start.sh — entrypoint do container produção Railway (F5.9a).
#
# Ordem:
#   1. Ajusta DATABASE_URL se vier do Railway Postgres addon sem driver async.
#   2. Roda alembic upgrade head (idempotente — no-op se já em head).
#   3. (Commit 3 adiciona seed condicional aqui.)
#   4. Inicia uvicorn com 2 workers (suficiente para piloto Bradesco; ajustar
#      em F6 baseado em carga real).
###############################################################################
set -euo pipefail

# Railway Postgres addon entrega DATABASE_URL como `postgresql://...` (driver
# psycopg padrão). SQLAlchemy async com asyncpg precisa do schema explícito
# `postgresql+asyncpg://`. Convertemos aqui em vez de no código para que
# alembic (sync, usa psycopg2/asyncpg pela env) e backend (async) vejam o
# valor correto sem branching.
if [[ "${DATABASE_URL:-}" == postgresql://* ]]; then
  export DATABASE_URL="postgresql+asyncpg://${DATABASE_URL#postgresql://}"
fi

echo "[start.sh] alembic upgrade head"
alembic upgrade head

# Seed condicional: só em ambientes de smoke (dev/beta/staging), nunca em prod.
# Falha não bloqueia a subida do backend — log informativo + continue.
# PYTHONPATH=/app é necessário porque o pacote `app` está em /app/app (copiado
# direto, não instalado em site-packages). Python ao executar `python script.py`
# coloca apenas o DIR DO SCRIPT no sys.path, não o CWD — sem PYTHONPATH explícito,
# `from app.core.security import hash_password` falha com ModuleNotFoundError.
if [[ "${ENVIRONMENT:-dev}" =~ ^(dev|beta|staging)$ ]] && [[ "${SEED_ON_STARTUP:-false}" == "true" ]]; then
  echo "[start.sh] seed_pilot.py (ENVIRONMENT=${ENVIRONMENT})"
  PYTHONPATH=/app python scripts/seed_pilot.py || echo "[start.sh] seed falhou (continuando)"
fi

echo "[start.sh] starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --proxy-headers \
  --forwarded-allow-ips='*'
