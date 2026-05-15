# Runbook — Deploy do Jump GP Portal no Railway

**Status:** piloto Bradesco (F5.9). **Última revisão:** 2026-05-15.
**Executor:** Christopher Tominaga (DPO + dono operacional do produto).

Este runbook cobre o deploy beta no Railway. Worker continua local no WSL
(decisão F5.6a.Y + F5.9a — vide `docs/runbooks/operacao-piloto.md`); o
Railway hospeda backend FastAPI, frontend Next.js, Postgres, Redis.

---

## 1. Pré-requisitos

- [ ] Railway CLI instalado (`npm install -g @railway/cli`).
- [ ] Workspace Railway "Jump Label" criado (ou similar).
- [ ] Repo `ctominaga-jump/gp_portal` push para `main` em estado verde
  (pytest backend 221+, vitest frontend 108+, sem regressão).
- [ ] `.env.production` preparado localmente (NÃO commitado) usando
  `.env.production.example` como base.
- [ ] Resend: domínio `jumplabel.com.br` verificado, API key gerada.
- [ ] Storage: decidir entre R2 (recomendado) ou volume Railway (vide §6).
- [ ] DNS: subdomain `*.up.railway.app` (zero config) — confirmado pelo
  Christopher em 2026-05-15.

## 2. Login e criação do projeto

```bash
railway login                              # browser OAuth
railway init --name jump-gp-portal         # ou: railway link (projeto existente)
```

## 3. Provisionar Postgres + Redis (addons gerenciados)

Via dashboard Railway:
1. **+ New** → **Database** → **PostgreSQL**. Railway injeta `DATABASE_URL`
   automaticamente nas services do projeto.
2. **+ New** → **Database** → **Redis**. Railway injeta `REDIS_URL`. Se a
   conexão exigir TLS (Railway entrega `rediss://`), o worker local
   já suporta (vide F5.9b).

Versões: Postgres 16, Redis 7. Backups automáticos do Postgres ficam
ativados por padrão (planos pagos).

## 4. Criar o service `backend`

1. **+ New** → **Empty Service** → nome "backend".
2. Em **Settings → Source**: conectar ao repo `ctominaga-jump/gp_portal`,
   branch `main`.
3. Em **Settings → Build**:
   - **Root Directory**: deixar vazio (raiz do monorepo). O Dockerfile do
     backend precisa acessar `jump_storage/` (sibling), então o build
     context PRECISA ser a raiz.
   - **Builder**: `Dockerfile`.
   - **Dockerfile Path**: `backend/Dockerfile` (relativo à raiz).
   - `railway.json` na raiz já contém `healthcheckPath: /health` etc.
4. Em **Settings → Networking**: gerar **Generate Domain** — Railway
   atribui `https://backend-<hash>.up.railway.app`. Anotar.
5. Em **Variables**: setar todas do `.env.production.example`:
   ```
   railway variables set ENVIRONMENT=beta
   railway variables set JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   railway variables set WORKER_SHARED_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   railway variables set WORKER_HMAC_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   railway variables set RESEND_API_KEY=...
   railway variables set RESEND_FROM_EMAIL=notificacoes@jumplabel.com.br
   # R2 ou storage local — vide §6
   railway variables set CORS_ORIGINS=https://frontend-<hash>.up.railway.app
   railway variables set SEED_ON_STARTUP=true
   railway variables set SEED_PMO_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(16))")
   railway variables set SEED_GP_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(16))")
   railway variables set SEED_CLIENT_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(16))")
   ```
   **ANOTAR** as senhas SEED_*_PASSWORD geradas — única chance.
6. `DATABASE_URL` e `REDIS_URL` são injetados automaticamente pelos
   addons. `start.sh` converte `postgresql://` → `postgresql+asyncpg://`
   em runtime.

## 5. Criar o service `frontend`

1. **+ New** → **Empty Service** → nome "frontend".
2. Em **Settings → Source**: mesmo repo, mesmo branch.
3. Em **Settings → Build**:
   - **Root Directory**: `frontend`.
   - **Builder**: `Dockerfile`.
   - **Dockerfile Path**: `Dockerfile` (relativo a `frontend/`).
   - `frontend/railway.json` já está configurado.
4. Em **Variables**:
   ```
   railway variables set --service frontend NEXT_PUBLIC_API_URL=https://backend-<hash>.up.railway.app
   ```
   `NEXT_PUBLIC_API_URL` é build-time no Next.js. Mudar exige rebuild
   (não basta redeploy).
5. **Generate Domain** → anotar URL frontend prod.
6. **Voltar ao backend** e atualizar `CORS_ORIGINS` com a URL exata do
   frontend (NÃO `*` — backend bloqueia com ValidationError em prod).

## 6. Decisão pendente — Storage de arquivos (Proposals)

**Opção A — Cloudflare R2 (recomendada):**
1. Criar bucket `jump-report-proposals` no console R2.
2. Gerar API token R/W. Anotar `R2_ACCOUNT_ID`, `R2_ACCESS_KEY`,
   `R2_SECRET_KEY`.
3. Configurar variáveis no backend:
   ```
   railway variables set R2_ACCOUNT_ID=...
   railway variables set R2_ACCESS_KEY=...
   railway variables set R2_SECRET_KEY=...
   railway variables set R2_BUCKET=jump-report-proposals
   railway variables set R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

**Opção B — Volume Railway (fallback):**
1. No service backend, **Settings → Volumes → Add** → mount path
   `/data`. Tamanho inicial 5 GB (suficiente para piloto Bradesco;
   3 PDFs ~73+10+8 MB).
2. Variáveis:
   ```
   railway variables set STORAGE_BACKEND=local
   railway variables set STORAGE_LOCAL_PATH=/data
   railway variables set R2_*=  # vazios; jump_storage cai para fs local
   ```
3. **Limitação**: volume único; se backend escalar para múltiplas
   instâncias, propostas de um pod não são visíveis no outro. Aceitável
   para piloto (1 instância); migrar para R2 ao escalar.

Em 2026-05-15, Christopher AINDA NÃO decidiu entre A e B. Recomendação:
A (R2) por melhor TCO ao escalar. Migração A→B ou B→A é viável (jump_storage
abstrai), mas dados não migram automaticamente.

## 7. Deploy

```bash
# Push para main já dispara auto-deploy se os services estão linkados ao
# repo. Para forçar:
railway up --service backend
railway up --service frontend
```

`start.sh` no backend executa: alembic upgrade head → seed condicional
(se ENVIRONMENT em {dev,beta,staging} + SEED_ON_STARTUP=true) → uvicorn.

## 8. Healthchecks pós-deploy

```bash
curl https://backend-<hash>.up.railway.app/health
# {"status":"ok","version":"0.1.0"}

curl https://backend-<hash>.up.railway.app/health/db
# {"status":"ok"}

curl https://backend-<hash>.up.railway.app/health/redis
# {"status":"ok"}

curl https://backend-<hash>.up.railway.app/health/full
# {"status":"ok","db":"ok","redis":"ok","version":"0.1.0"}
```

## 9. Smoke pós-deploy

1. Browser: abrir `https://frontend-<hash>.up.railway.app/login`.
2. Login com `pmo@jumplabel.com.br` + senha SEED_PMO_PASSWORD anotada.
3. Verificar dashboard PMO carrega.
4. Smoke ponta-a-ponta automatizado vem em F5.9b (`scripts/smoke_production.py`).

## 10. Logs e troubleshooting

```bash
railway logs --service backend            # streaming
railway logs --service backend | tail -100
railway logs --service frontend
```

Erros comuns:
- **CORS_ORIGINS=* em prod** → backend falha no startup (ValidationError
  no Settings). Solução: setar URL exata do frontend.
- **DATABASE_URL ausente** → service não consegue migrar. Confirme que o
  Postgres addon está provisionado e a variável está com `${{Postgres.DATABASE_URL}}`.
- **NEXT_PUBLIC_API_URL apontando para localhost** → frontend gera bundle
  com URL errada. Lembrar que é build-time — exige redeploy do frontend
  após mudar.

## 11. Rotação de secrets

```bash
railway variables set --service backend JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# Trigger redeploy. JWTs emitidos antes ficam inválidos — usuários precisam relogar.

railway variables set --service backend WORKER_SHARED_SECRET=...
railway variables set --service backend WORKER_HMAC_KEY=...
# Sincronizar com worker local em ~/.jump-runner/.env.worker antes do redeploy.
```

## 12. Rollback

```bash
railway redeploy --service backend <commit_anterior_sha>
# Ou via dashboard: Deployments → 3-dots → Redeploy
```

Em incidente:
1. Identificar deploy ruim em **Deployments**.
2. **Redeploy** o deploy anterior (1 clique).
3. Investigar causa em logs antes de novo push.

## 13. Custos esperados (piloto)

- Backend: 1 instância 512MB → ~$5-10/mês.
- Frontend: 1 instância 512MB → ~$5/mês.
- Postgres: shared, ~$5/mês (free tier suficiente no piloto).
- Redis: shared, ~$5/mês.
- Total piloto Bradesco: ~$20-30/mês.

Escala (F6+): worker em container, múltiplas instâncias backend, Postgres
HA → ~$80-150/mês.

---

**Próximo passo após este runbook:** F5.9b — smoke produção end-to-end
com `scripts/smoke_production.py` rodando contra Railway com worker local.
