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
- [ ] Resend: **opcional no piloto inicial** — domínio `jumplabel.com.br`
  ainda não verificado. Aceitar `RESEND_API_KEY` vazio = dry-run
  (notificações operacionais ficam in-app; recibo LGPD ao titular
  NÃO sai por email). Ativar quando F5.9.Resend fechar. Vide ADR
  `2026-05-15 — F5.9 / Resend em dry-run durante piloto inicial`.
- [ ] Storage: **volume Railway** (decisão F5.9.bonus) criado em `/data`
  ANTES do primeiro `railway up` (vide §6.1).
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
   # Resend em dry-run (decisão F5.9.bonus). Manter vazio até DNS
   # jumplabel.com.br ser verificado — F5.9.Resend.
   railway variables set RESEND_API_KEY=
   railway variables set RESEND_FROM_EMAIL=notificacoes@jumplabel.com.br
   # Storage local com volume Railway — vide §6 (caminho oficial F5.9.bonus)
   railway variables set OBJECT_STORAGE_BACKEND=local
   railway variables set LOCAL_STORAGE_ROOT=/data
   railway variables set LOCAL_STORAGE_BASE_URL=https://<backend-service>.up.railway.app
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

## 6. Storage de arquivos — LocalStorage com volume Railway (oficial F5.9.bonus)

Decisão F5.9.bonus (2026-05-15, ADR `2026-05-15 — F5.9 / Storage backend
mudou para LocalStorage com volume Railway`): o piloto adota
LocalStorage com volume Railway. Concentra billing no Railway, dispensa
conta de operador externo e cobre o volume previsível do piloto
Bradesco (3 PDFs ~73+10+8 MB + ZIPs do worker e do export LGPD).

### 6.1 Criar o volume (ANTES do primeiro `railway up`)

No dashboard Railway → Service backend → **Settings → Volumes → Add**:
1. **Mount Path**: `/data`.
2. **Size**: começar com 10 GB. Pode crescer depois pelo dashboard.

O `railway.json` na raiz já declara o mount; o passo manual provê o
volume físico subjacente. Sem o volume criado, o deploy sobe mas o
backend falha em qualquer upload (`/data` inexistente).

### 6.2 Variáveis no Railway (service backend)

```
railway variables set OBJECT_STORAGE_BACKEND=local
railway variables set LOCAL_STORAGE_ROOT=/data
railway variables set LOCAL_STORAGE_BASE_URL=https://<backend-service>.up.railway.app
# R2_* ficam vazios (jump_storage ignora quando OBJECT_STORAGE_BACKEND=local).
```

`LOCAL_STORAGE_SIGNING_SECRET` cai para `JWT_SECRET` por convenção do
`jump_storage.factory` — não precisa definir separadamente, salvo
desejo explícito de chave isolada (recomendado em F6).

### 6.3 Backup do volume (manual no piloto)

Volume Railway é region-locked e o snapshot automático é responsabilidade
do operador. No piloto:
- 1ª opção (recomendada): job mensal externo que baixa o conteúdo via
  `railway run --service backend tar -czf /tmp/data-$(date +%F).tar.gz /data`
  e copia para storage frio.
- 2ª opção: snapshot manual via dashboard Railway (quando feature ficar
  disponível para o plano).

A automação do backup é débito formal **F5.9.Y** (vide
`docs/decisoes.md` ADR `2026-05-15 — F5.9 / Storage backend mudou…`).

### 6.4 Alternativa Cloudflare R2 (apenas se reativada em F6)

O backend R2 permanece como código vivo em `jump_storage/r2.py`. Para
reativar (ex.: ao escalar para múltiplas instâncias backend, quando o
volume único fica restritivo):
1. Criar bucket + API tokens no console R2.
2. Configurar `OBJECT_STORAGE_BACKEND=r2` + as vars `R2_*`.
3. Migrar dados existentes do volume para o bucket (script manual; não
   há migração automatizada).
4. Atualizar `docs/lgpd.md` §2 incluindo Cloudflare R2 como operador
   ativo de novo — exige reassinatura do DPO.

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
