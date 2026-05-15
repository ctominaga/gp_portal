# Pre-deploy checklist — piloto Bradesco no Railway

**Versão:** F5.9a. **Última revisão:** 2026-05-15.
**Quando rodar:** antes do `railway up` final no piloto Bradesco.

Cada item é binário (✅ ou ❌). Se algum estiver ❌, NÃO fazer deploy —
resolver primeiro. Itens marcados "informativo" (ℹ️) podem ser feitos
após o deploy mas precisam acontecer antes do go-live com o Bradesco.

---

## Código

- [ ] **F5.7 commits no main** (LGPD piloto v1.0 fechado — sha `6086dd3`
      ou descendente). `git log --oneline | grep F5.7` deve mostrar
      todos os 5 commits.
- [ ] **Suíte pytest backend verde** (`pytest -q` no backend retorna
      `221 passed` ou mais, 0 failures, 1 skipped pré-existente).
- [ ] **Suíte vitest frontend verde** (`npx vitest run` retorna
      `108 passed` ou mais, 0 failures).
- [ ] **`tsc --noEmit` no frontend sem erros**.
- [ ] **Migrations sobem em Postgres limpo** (validar local com
      `docker compose up db` + `alembic upgrade head` em DB vazio;
      deve subir do 0001 ao 0018 sem erro).
- [ ] **Linha base do conformidade-v3.x.md** revisada — itens marcados
      ✅ realmente cobertos por testes ou validação manual.

## Secrets do Railway

- [ ] **`.env.production` preparado localmente** copiando de
      `.env.production.example` e preenchendo placeholders.
      **NÃO commitar** — `.gitignore` cobre, mas verificar duas vezes.
- [ ] **`JWT_SECRET`** com 32+ bytes random (`python -c "import secrets;
      print(secrets.token_urlsafe(32))"`) e ÚNICO (não reutilizar de dev).
- [ ] **`WORKER_SHARED_SECRET`** idem, 32+ bytes random.
- [ ] **`WORKER_HMAC_KEY`** idem, 32+ bytes random.
- [ ] **`SEED_PMO_PASSWORD`**, **`SEED_GP_PASSWORD`**, **`SEED_CLIENT_PASSWORD`**
      gerados (16-32 chars random) e ANOTADOS em local seguro.
- [ ] **`JWT_SECRET` ≠ `WORKER_SHARED_SECRET` ≠ `WORKER_HMAC_KEY`** (cada
      um único; vazamento de um não compromete os outros).

## Configuração HTTPS

- [ ] **`CORS_ORIGINS` = URL exata do frontend prod** (não `*` — backend
      rejeita com ValidationError em ENVIRONMENT=prod; vide
      `app/core/config.py::Settings._validate_cors_origins_prod`).
- [ ] **`NEXT_PUBLIC_API_URL` = URL exata do backend prod**. Lembrar:
      é build-time no Next.js, exige rebuild do frontend após mudar.
- [ ] **`ENVIRONMENT=beta`** (ou `prod` quando promover). Em prod, o
      seed é IGNORADO mesmo com `SEED_ON_STARTUP=true` por design.

## Integrações externas

- [ ] **Resend**: domínio `jumplabel.com.br` verificado (SPF/DKIM/DMARC
      publicados). API key gerada com role apropriado.
- [ ] **`RESEND_FROM_EMAIL`** aponta para endereço verificado (recomendado:
      `notificacoes@jumplabel.com.br`).
- [ ] **Cloudflare R2** (se opção A em §6 do runbook deploy-railway):
      bucket `jump-report-proposals` criado, API tokens R/W gerados,
      `R2_*` configurados no Railway. Smoke: upload de arquivo
      pequeno via console R2 + delete.
- [ ] **OU Storage local + Railway volume** (se opção B): volume
      montado em `/data`, `STORAGE_BACKEND=local`.

## Operacional

- [ ] **Canal LGPD operacional ativo**: `christopher.tominaga@jumplabel.com.br`
      (DPO designado recebe diretamente). Christopher confirma que monitora
      a caixa do e-mail no go-live e tem regra de filtro/etiqueta para pedidos
      LGPD entrantes.
- [ ] **F5.7.Z** (alias `lgpd@jumplabel.com.br`) — débito v1.1.
      Provisionamento recomendado em até 2 semanas pós go-live para evitar
      uso prolongado do e-mail pessoal corporativo do DPO como canal LGPD
      público.
- [ ] **Backup automático Postgres** validado. Railway oferece point-in-time
      recovery em planos pagos — confirmar que está ativo.
- [ ] **Worker local** rodando no WSL do Christopher, heartbeat verde
      em `/operator/workers` após o deploy. Vide
      `docs/runbooks/operacao-piloto.md` §3.
- [ ] **Spec v3.2 consolidada** (saída de F5.9c) revisada por Christopher
      com diff vs v3.1 explicitado.

## LGPD piloto (F5.7)

- [ ] **`docs/lgpd.md`** assinado pelo DPO (Christopher Tominaga,
      `christopher.tominaga@jumplabel.com.br`). Cabeçalho com data
      `2026-05-14` (ou mais recente se atualizado em F5.9d/e).
- [ ] **`docs/rat.md`** alinhado com `docs/lgpd.md` (mesma versão
      operacional).
- [ ] **Endpoint `/me/data-export`** funcional em prod — testar com
      o user `pmo@jumplabel.com.br` após deploy.
- [ ] **Endpoint `/admin/data-requests`** acessível para role PMO em prod.

## Pós-deploy (item ℹ️ — fazer depois mas antes do go-live)

- [ ] ℹ️ **Smoke produção** com `scripts/smoke_production.py` (vem em
      F5.9b) retorna exit 0.
- [ ] ℹ️ **Acesso visual** ao frontend HTTPS confirmado em navegador
      do Christopher e em incognito limpo.
- [ ] ℹ️ **Healthchecks** retornam 200:
      `/health`, `/health/db`, `/health/redis`.
- [ ] ℹ️ **Logs** sem erros nas primeiras 30min de uptime
      (`railway logs --service backend | grep -i error`).

---

**Quando todos os itens estiverem ✅:** executar
`docs/runbooks/deploy-railway.md` passo-a-passo.

**Quando algum estiver ❌:** parar. Resolver. Re-executar este checklist.

**Em caso de incidente pós-deploy:** seguir §12 do `deploy-railway.md`
(rollback) e abrir nota em `docs/decisoes.md` com contexto e mitigação.
