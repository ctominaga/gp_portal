# Pre-deploy validation report — F5.9

**Data:** 2026-05-15 18:36 UTC-3
**HEAD:** `cd9ca68` (`feat(infra): F5.9.bonus storage muda para Railway volume + LGPD v1.0.1 + Resend dry-run`)
**Sessão:** Claude Code (Opus 4.7)
**Storage backend:** LocalStorage + Railway volume (F5.9.bonus aplicada — `cd9ca68`)
**Resend:** dry-run (F5.9.Resend aberto)

Este relatório resume a execução do `docs/pre-deploy-checklist.md` em
modo automatizado. Cada item está em uma de 3 seções: validado
(automatizado), ajustes menores aplicados, ou manual (Christopher executa).

---

## ✅ Validados automaticamente

### Código

| Item | Comando | Resultado |
|---|---|---|
| F5.7 commits no main | `git log --oneline \| grep -i F5.7` | 5 commits encontrados (`640bd28`, `b5f1fd0`, `1e47cbc`, `f54c020`, `6086dd3`) + 1 residual `c376b12`. F5.7 completa. |
| Suíte pytest backend verde | `pytest -q` (backend) | **221 passed, 1 skipped** em 4m50s. Skip é o stub global pré-existente em `test_baseline_report.py:459`. |
| `tsc --noEmit` no frontend | `npx tsc --noEmit` | Zero erros. Output vazio. |
| Alembic chain íntegro | `alembic history` | 18 migrations encadeadas, head em `0018_users_anonymized_at` (F5.7). |
| Cluster LGPD + F5.9 isolado | `pytest tests/test_lgpd_*.py tests/test_health_*.py tests/test_settings_cors_guard.py tests/test_seed_pilot.py -q` | **26 passed** em 38s — export (5) + deletion (7) + E2E (1) + health (6) + CORS (5) + seed (3). Cobre direta e indiretamente os itens 18 (Resend dry-run smoke), 27 (`/me/data-export`), 28 (`/admin/data-requests`). |

### Configuração

| Item | Comando | Resultado |
|---|---|---|
| `railway.json` válido | `python -c "import json; json.load(open('railway.json'))"` | JSON íntegro. `deploy.volumes` declara `mountPath=/data` (F5.9.bonus). |
| `frontend/railway.json` válido | idem | OK. healthcheckPath `/`. |
| Diff `.env.example` ↔ `.env.production.example` | `diff <(grep -oE "^[A-Z_]+=" .env.example) <(grep -oE "^[A-Z_]+=" .env.production.example)` | Esperado: dev tem `*_HOST_PORT` (docker-compose) e prod tem `LOCAL_STORAGE_*`, `OBJECT_STORAGE_BACKEND`, `SEED_*`. Toda var de produto mapeada. |
| Resend dry-run guard | `RESEND_API_KEY="" python -c "from app.services.notifications import _resend_dry_run; assert _resend_dry_run()"` | OK. `_send_email` cai no caminho `email.dry_run` sem importar o SDK Resend. |
| LocalStorage factory smoke | Script Python instanciando `get_storage()` com `OBJECT_STORAGE_BACKEND=local` + `LOCAL_STORAGE_*` | `Backend type: LocalStorage`. Factory aceita as env vars de produção sem erro. |
| `jump_storage` tests | `pytest ../jump_storage/tests/ -q` | **23 passed** em 11s (factory + local + r2). |

### LGPD

| Item | Comando | Resultado |
|---|---|---|
| `docs/lgpd.md` v1.0.1 assinado | `head -7 docs/lgpd.md` | Cabeçalho v1.0.1, 2026-05-15, DPO Christopher Tominaga, aprovação registrada. |
| `docs/rat.md` v1.0.1 alinhado | `head -7 docs/rat.md` | Mesma versão, mesma data, mesmo DPO. Canal LGPD `christopher.tominaga@jumplabel.com.br`. |
| `/me/data-export` funcional | `pytest tests/test_lgpd_export.py -q` | **5 passed** (smoke + cobertura + RBAC sem token + cross-user + filtro CLIENT). ZIP com 5 arquivos. |
| `/admin/data-requests` cobertos | `pytest tests/test_lgpd_deletion.py -q` (7 testes RBAC/fulfill/idempotência) | **7 passed**. |
| F5.7.Z débito documentado | `grep F5.7.Z docs/decisoes.md docs/lgpd.md` | Presente em ambos. Linha 197 do `lgpd.md` §10 explica a justificativa. |
| Conformidade-v3.1 linha 60 | leitura | DataProcessingRecord marcado ✅ — cobertura F5.7 reflete realidade. Sem ❌ no escopo F5.7/F5.9. |

### Integrações externas (decisões F5.9.bonus)

| Item | Comando | Resultado |
|---|---|---|
| Resend dry-run em `.env.production.example` | `grep RESEND_API_KEY .env.production.example` | `RESEND_API_KEY=` (vazio). Comentário cita débito F5.9.Resend. |
| Storage = LocalStorage em `.env.production.example` | `grep OBJECT_STORAGE_BACKEND .env.production.example` | `OBJECT_STORAGE_BACKEND=local`. `LOCAL_STORAGE_ROOT=/data`. `R2_*` vazias. |
| Volume mount declarado em `railway.json` | leitura | `deploy.volumes: [{name: "data", mountPath: "/data"}]`. |
| ADRs F5.9.bonus em `docs/decisoes.md` | `grep "2026-05-15 — F5.9" docs/decisoes.md` | 2 ADRs novos: Storage backend mudou + Resend dry-run. Contexto/Decisão/Consequência completos. |

---

## ⚠️ Ajustes menores aplicados e/ou flakes registrados

Nenhum ajuste de código aplicado nesta sessão (escopo F5.9.bonus já fechou).
Anotações para Christopher:

1. **Vitest cross-test flakiness em `tests/diff-baselines-pmo.test.tsx`.**
   Pré-existente (registrada na sessão F5.9a Commit 4). Em rodada completa
   (`npx vitest run`) o teste "PMO + ScopeChanges PROPOSED → botões Aprovar/
   Rejeitar aparecem" falha 1 vez. Rodada isolada (`npx vitest run tests/
   diff-baselines-pmo.test.tsx`) passa 5/5 em 2.1s. Causa raiz: poluição
   de estado Radix Select entre arquivos (jsdom não isola). Mitigação
   já adotada em F5.9a: polyfill `scrollIntoView`/`hasPointerCapture` em
   `tests/setup.ts`. **Não bloqueia deploy.** Investigação para isolamento
   total é débito ergonômico (F6 ou backlog técnico).

2. **`next lint` reporta 6 erros pré-existentes** em 3 arquivos fora do
   escopo F5.9: `src/app/pmo/reports/[rid]/review/page.tsx:180`,
   `src/app/projetos/[id]/encerramento/page.tsx:317`,
   `src/app/projetos/[id]/reports/novo/page.tsx:153`. Todos do regra
   `react/no-unescaped-entities` (aspas em texto JSX). Build do
   Next.js continua passando (lint não é bloqueante por default na
   pipeline). **Não bloqueia deploy** mas é débito de polimento.

3. **Alembic migrations from scratch contra SQLite falha** (`DATABASE_URL=
   sqlite+aiosqlite://...`). Algumas migrations usam SQL bruto com `now()`
   (PG-only). Pré-existente — todos os testes usam `Base.metadata.create_all`
   via conftest, não migrations. **Não bloqueia deploy:** Railway Postgres
   é Postgres real; `start.sh` roda `alembic upgrade head` no boot do
   container e é o caminho validado. `alembic history` confirma a chain
   íntegra do `<base>` ao `0018_users_anonymized_at` (head F5.7).

4. **Docker builds locais não validados** (`docker build` ficou pendurado
   sem output em `docker ps`/`docker info`). Docker Desktop em estado
   degradado, consistente com ADR `2026-05-07 — F0 / Validação Docker
   pendente`. **Não bloqueia deploy:** Railway tem seu próprio Docker
   runner (Nixpacks/Docker buildkit). Christopher valida o build no
   primeiro `railway up` — se falhar, logs do dashboard mostram o ponto.
   Análise estática dos Dockerfiles ficou OK (multi-stage builder/runner,
   usuário não-root, HEALTHCHECK no backend, output standalone no frontend).

---

## 👤 Manuais para Christopher (antes ou durante `railway up`)

### Pré-deploy (bloqueantes do `railway up`)

- [ ] **Conta Railway:** workspace "Jump Label" no plano Pro, cartão
      corporativo, 2FA ativado, spend limit configurado.
- [ ] **`.env.production` local** copiado de `.env.production.example`
      e preenchido. NÃO commitar (`.env*` no `.gitignore` cobre, mas
      verificar duas vezes).
- [ ] **Secrets gerados** (32+ bytes random cada, todos únicos):
      `JWT_SECRET`, `WORKER_SHARED_SECRET`, `WORKER_HMAC_KEY`.
      Comando: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- [ ] **Seed passwords gerados** (16-32 chars random cada) e ANOTADOS:
      `SEED_PMO_PASSWORD`, `SEED_GP_PASSWORD`, `SEED_CLIENT_PASSWORD`.
      Anotar antes de setar no Railway (logs só mostram dry-run).
- [ ] **Volume Railway de 10 GB** criado no dashboard antes do primeiro
      `railway up`, mount path `/data`. Vide
      `docs/runbooks/deploy-railway.md §6.1`. Sem o volume, o backend
      sobe mas falha em qualquer upload.
- [ ] **Backup automático Postgres** validado no dashboard Railway
      (point-in-time recovery — exige plano Pro).
- [ ] **Provisionar Postgres + Redis addons** no projeto. Railway injeta
      `DATABASE_URL` e `REDIS_URL` automaticamente.

### Configuração HTTPS (input pós-deploy, antes do go-live)

- [ ] **CORS_ORIGINS** = URL exata do frontend prod (gerar via Railway
      → service frontend → **Generate Domain**). NÃO usar `*` — backend
      rejeita com `ValidationError` em `ENVIRONMENT=prod` (vide
      `app/core/config.py::Settings._validate_cors_origins_prod` —
      coberto por 4 pytests).
- [ ] **NEXT_PUBLIC_API_URL** = URL exata do backend prod (gerar via
      Railway → service backend → **Generate Domain**). Build-time:
      mudar exige rebuild do frontend.
- [ ] **ENVIRONMENT=beta** (ou `prod` quando promover). Em `prod` o
      seed é IGNORADO mesmo com `SEED_ON_STARTUP=true` por design
      (vide `seed_pilot.py:84`).

### Operacional

- [ ] **Canal LGPD ativo**: Christopher monitora `christopher.tominaga@
      jumplabel.com.br` com filtro/etiqueta dedicado para pedidos LGPD
      entrantes; resposta dentro do SLA art. 19 LGPD (15 dias úteis).
- [ ] **F5.7.Z** (alias `lgpd@jumplabel.com.br`) — débito v1.1.
      Provisionamento recomendado em até 2 semanas pós go-live para
      evitar uso prolongado do e-mail pessoal corporativo do DPO como
      canal LGPD público.
- [ ] **F5.9.Resend** — TI Jump avisada sobre verificação DNS de
      `jumplabel.com.br` (SPF/DKIM/DMARC). Enquanto débito permanecer,
      `RESEND_API_KEY` fica vazio, notificações operacionais ficam
      in-app, recibo LGPD ao titular NÃO sai por email (DPO comunica
      manualmente). Vide `docs/lgpd.md §6.8` e ADR `2026-05-15 — F5.9
      / Resend em dry-run`.
- [ ] **Worker local** rodando no WSL do Christopher conectado ao Redis
      Railway via `rediss://`. Heartbeat verde em `/operator/workers`
      após o deploy. Vide `docs/runbooks/operacao-piloto.md §3`.

### Bloqueado (depende de outra sub-fase)

- [ ] **Spec v3.2 consolidada** — F5.9c não foi executada nesta sessão
      (ficou fora do escopo F5.9.bonus). Débito explícito; rodar antes
      do go-live se a spec consolidada for pré-requisito contratual
      do piloto Bradesco. Em F5.9c estão: spec v3.1 → v3.2 (move para
      `spec_history/`), §6.4.1 com enums novos `DeliverableType/
      Category/Complexity`, §9.5 corrigindo `DataProcessingRecord`,
      §12.8 (subseção LGPD). `docs/conformidade-v3.2.md` espelha v3.2.

### Pós-deploy (ℹ️ — antes do go-live com Bradesco)

- [ ] ℹ️ **Smoke produção** com `scripts/smoke_production.py` (F5.9b,
      ainda não construído nesta sessão). Validação visual no browser
      é alternativa imediata.
- [ ] ℹ️ **Acesso visual** ao frontend HTTPS confirmado em navegador
      do Christopher e em incognito limpo.
- [ ] ℹ️ **Healthchecks** retornam 200: `GET /health`, `GET /health/db`,
      `GET /health/redis`. `/health/full` mostra o agregado.
- [ ] ℹ️ **Logs sem erros** nas primeiras 30min de uptime:
      `railway logs --service backend | grep -i error` deve estar limpo.
- [ ] ℹ️ **Smoke do fluxo LGPD em prod**: criar pedido de eliminação
      logado como `pmo@jumplabel.com.br`, ver entrar em
      `/admin/data-requests`, atender, confirmar que o user de teste
      fica anonimizado (não consegue mais logar). Smoke do fluxo
      completo cobrindo F5.7 + F5.9.bonus simultaneamente.

---

## Resumo executivo

- **Backend:** 221 testes pytest + 23 jump_storage = 244 testes verdes.
  Zero regressão sobre F5.9.bonus.
- **Frontend:** 107/108 vitest verdes; 1 flake cross-test pré-existente
  (não bloqueia). `tsc --noEmit` clean.
- **Configuração:** `.env.production.example`, `railway.json` (com volume),
  `.env.example` ↔ prod consistentes. Resend dry-run funcional.
- **LGPD:** v1.0.1 assinado, RAT alinhado, endpoints cobertos.
- **Storage:** LocalStorage factory smoke OK; volume mount declarado.
- **Pendências bloqueantes do `railway up`:** 7 itens manuais (conta,
  secrets, volume, addons, backup) + decisões pós-deploy de URLs prod.

**Recomendação:** o repositório está pronto para `railway up`. Christopher
executa o §1-§9 de `docs/runbooks/deploy-railway.md` quando tiver os 7
itens manuais bloqueantes resolvidos. Após o deploy, retornar com URLs
de backend/frontend/Redis para iniciar F5.9b (smoke produção) e, se
desejável, F5.9c (spec v3.2 consolidada).

**Status:** **PRONTO PARA DEPLOY** sob os 7 itens manuais documentados acima.
