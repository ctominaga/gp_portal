###############################################################################
# Backend Dockerfile — multi-stage, produção Railway (F5.9a).
#
# IMPORTANTE: build context = raiz do monorepo (`jump-report/`), NÃO `backend/`.
# Justificativa: o backend depende de `jump_storage` (pacote local, NÃO no
# PyPI), declarado em pyproject.toml. Para alcançar a sibling `jump_storage/`,
# o Dockerfile precisa rodar com contexto = repo root.
#
# Em Railway, configurar a service "backend" como:
#   - Root Directory: vazio (raiz do repo)
#   - Dockerfile Path: backend/Dockerfile
#
# Em build local equivalente:
#   docker build -f backend/Dockerfile -t jump-backend .
###############################################################################

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 1) Instalar jump_storage primeiro a partir do path local (não está no PyPI).
COPY jump_storage /build/jump_storage
RUN pip install --upgrade pip && pip install --no-cache-dir /build/jump_storage

# 2) Instalar o backend. `jump-storage` em pyproject.toml já está satisfeito.
#    Demais deps (fastapi, sqlalchemy, etc.) vêm do PyPI. Não usar `-e`:
#    o stage runner copia só site-packages, não o source path.
COPY backend/pyproject.toml /build/backend/
RUN pip install --no-cache-dir /build/backend

###############################################################################
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# curl só para o HEALTHCHECK interno; sem build-essential aqui (imagem mínima).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root (uid/gid 1001).
RUN groupadd --system --gid 1001 jump \
 && useradd --system --uid 1001 --gid 1001 --no-create-home --shell /usr/sbin/nologin appuser

# Copia deps Python instaladas no builder. Não traz build-essential/curl-dev/etc.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Código da aplicação (mantém estrutura para alembic.ini achar `alembic/`).
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts

RUN chmod +x scripts/start.sh \
 && chown -R appuser:jump /app

USER appuser

EXPOSE 8000

# Liveness probe. `/health` retorna 200 sempre que o processo Python está vivo,
# sem tocar DB/Redis (essas têm endpoints dedicados em /health/db e /health/redis).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["./scripts/start.sh"]
