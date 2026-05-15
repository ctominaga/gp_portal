# Fase 5 — Progresso

**Status atual:** F5.1 a F5.4, F5.6 (a+b) e F5.7 fechadas. F5.5, F5.8 e F5.9 pendentes.

**Última atualização:** 2026-05-14

---

## F5.1 — Schemas P2 ✅ FECHADA

Alinhamento dos 4 modelos (Risk, ActionPlan, Deliverable, PendingItem) à spec v3.1 §4.2 + ao prompt `proposal_reader_v1.md`. Estratégia: drop+recreate onde havia divergência de enum (COUNT=0 já investigado em ETAPA 2A da sub-fase Risk; sem dados em produção).

### Commits

| # | Commit | Modelo | Migration |
|---|---|---|---|
| 1 | `e888415` | **Risk** — probability+impact com level derivado; RiskStatus 4 valores; OPEN_RISK_STATUSES; mitigation_plan | `0010_risk_p_i_level` |
| 2 | `edaec34` | **ActionPlan** — objective + linked_risk_id + linked_deliverable_id (ON DELETE SET NULL); expansão linked_*_description/title em lote | `0011_actionplan_objective_links` |
| 3 | `1284bc5` | **Deliverable** — type+acceptance_criteria+dependencies+status; complexity 3→5 PT-BR; category String→enum; cross-model auto-update CONCLUDED | `0012_deliverable_type_acceptance_deps_status` |
| 4 | `7263526` | **PendingItem** — impact (nullable) + created_at (cumpre open_date semanticamente) | `0013_pendingitem_impact_created` |

### Métricas (evolução durante F5.1)

| Métrica | Início | Risk | ActionPlan | Deliverable | **PendingItem (final)** |
|---|---|---|---|---|---|
| pytest backend | 93 | 105 | 111 | 116 | **119** |
| Cobertura backend | 71.33% | 72.62% | 72.45% | 72.71% | **72.76%** |
| vitest frontend | 69 | 69 | 72 | 73 | **76** |

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~F. Risk: probability/impact + mitigation_plan~~ → endereçado em `e888415`
- ~~G. ActionPlan: objective + vinculações~~ → endereçado em `edaec34`
- ~~H. Deliverable: type + acceptance + dependencies + status~~ → endereçado em `1284bc5`
- ~~J. PendingItem: impact + open_date~~ → endereçado em `7263526`

---

## F5.2 — Versionamento de escopo ✅ FECHADA

Fluxo end-to-end de mudança formal de escopo entre versões de proposta
(v(N) → v(N+1)): GP faz upload v2 → worker importa + cria baseline DRAFT +
ScopeChanges PROPOSED via `diff_baselines` → PMO revisa em `/pmo/scope-changes`
ou `/projetos/[id]/diff` e aprova/rejeita a transição inteira (batch).

### Commits

| # | Commit | Conteúdo |
|---|---|---|
| 1 | `cd8fc45` | Modelo ScopeChange refatorado (+baseline_from_id, +baseline_to_id, +change_type, +approved_by_id) + BaselineStatus.REJECTED + migration `0014_scope_change_refactor` com backfill |
| 2 | `1b85e09` | `POST /baselines/{id}/transition` (PMO, batch approve/reject) + gate em activate_baseline para v2+ (GP → 403) + notify_transition_decision + GETs por projeto e detalhe |
| 3 | `886b74c` | `diff_baselines` cobre MODIFIED (added/removed/modified) + idempotência tripla `(baseline_to_id, change_type, deliverable_code)` + migration `0015_scope_change_deliverable_code` |
| 4 | `c92b076` | Frontend: rota `/pmo/scope-changes`, faixa PMO + modais em `/diff`, badge no portfolio, GET portfólio-wide, `pending_transitions_count`, types TS, vitest |
| 5 | (este commit) | Testes pytest dos endpoints de commit 4 + validação Pydantic do reject + Playwright + dev_notes + conformidade |

### Métricas (evolução durante F5.2)

| Métrica | Início F5.2 | Commit 1 | Commit 2 | Commit 3 | Commit 4 | **Commit 5 (final)** |
|---|---|---|---|---|---|---|
| pytest backend | 119 | 121 | 129 | 138 | 138 | **150** |
| Cobertura backend total | 72.76% | 73% | 72% | 72% | 72% | **72%** |
| vitest frontend | 76 | 76 | 76 | 76 | 84 | **84** |

### Decisões respondidas (Q1-Q5 do início da sub-fase)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1** | Granularidade da aprovação | Por transição (batch) — todos os ScopeChanges com `baseline_to_id=this` mudam juntos. Aprovação 1-a-1 cria estado parcial absurdo. |
| **Q2** | Quando PMO rejeita, o que acontece com o baseline novo? | Adicionar `BaselineStatus.REJECTED` (preserva rastreabilidade). |
| **Q3** | Estender `diff_baselines` para `changed`? | Sim — fecha gap §10.5 literal ("adicionado/removido/**alterado**"). |
| **Q4** | Bloquear GP de `activate_baseline` em v2+? | Sim, 403 com mensagem orientando `POST /baselines/{id}/transition` (role PMO). v1 continua livre para GP. |
| **Q5** | UI PMO — rota dedicada + botões em `/diff` ou só um? | Ambos. `/pmo/scope-changes` lista portfólio-wide; `/diff` tem botões inline para revisão; badge no `/pmo/portfolio` atalha direto. |

### Decisões internas adicionais (durante construção)

- **APPROVED é skip:** approve faz transição direta `PROPOSED → IMPLEMENTED`, pulando o estado `APPROVED` do enum (commit 2). Atomicidade da decisão+implementação no MVP. Enum mantém `APPROVED` reservado para futuro caso desacoplado.
- **Description estruturada do MODIFIED** em formato single-line `"Modificado: {code} (field1: old → new, field2: old → new)"` (commit 3). Renderiza bem em telas-lista; UI rica consome `changed_fields` separadamente.
- **UX pós-decisão = navegação para `/pmo/portfolio`** em vez de refresh in-place (commit 4). PMO geralmente processa fila; toast carrega o feedback.
- **`pending_transitions_count` via 1 query agregada** `GROUP BY project_id` em vez de N+1 (commit 4).
- **Comment obrigatório em reject** validado em duas camadas: client-side (commit 4, disabled no botão) e Pydantic server-side (commit 5, via `model_validator`). ADR em `decisoes.md`.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~E. ScopeChange: faltam baseline_from_id/to_id/change_type/approved_by~~ → endereçado em F5.2 commits 1-5
- Linha "Versionamento de escopo" §10.5 da tabela principal: ⚠️ → ✅

### Débitos menores P3 do F5.2

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.2 (P3)":

| ID | Item | Onde |
|---|---|---|
| **F5.2.a** | Convenção SAEnum sem `values_callable` persiste `e.name` UPPERCASE | Aplica a todos os enums; documentado em `dev_notes.md` |
| **F5.2.b** | Testes de migration usam `importlib` (SQLite), não `alembic upgrade` real | `tests/test_migration_0014_*` e `test_migration_0015_*` |
| **F5.2.c** | Remover coluna `impact_baseline_id` legacy | `ScopeChange.impact_baseline_id`; migration de remoção em F6 |
| **F5.2.d** | `pytest-cov` subreporta cobertura de funções async | `portfolio.py` e `scope_changes.py` em 47%/50% apesar de exercício explícito; total 72% OK |

---

## F5.3 — Retrospectiva ao encerrar projeto ✅ FECHADA

Fluxo end-to-end de encerramento com retrospectiva estruturada (spec v3.1 §10.4):
GP preenche 4 campos (`delivered_vs_proposed`, `would_do_differently`, `client_feedback`,
+ lista de `materialized_risks`) → POST /projects/{id}/close → cascade de 8 validações
→ cria `ProjectRetrospective` + marca `Project.status=CLOSED` + `ended_at=today` →
UI redireciona pra `/projetos/[id]` com banner verde + render read-only da retrospectiva.

### Commits

| # | Commit | Conteúdo |
|---|---|---|
| 1 | `fe93d50` | Modelo ProjectRetrospective drop+recreate (4 campos NOT NULL + materialized_risks JSON) + migration 0016 + `.coveragerc` resolvendo F5.2.d |
| 2a | `4de0188` | `fix(backend)`: auth/register normaliza email no SELECT (bug dormente desde F2, descoberto pelo seed de teste F5.3 com case misto) |
| 2b | `93bf7bc` | `POST /projects/{id}/close` (cascade 8 validações Q4) + `GET /projects/{id}/retrospective` + schemas Pydantic + 21 testes pytest |
| 3 | `bf5b97f` | Frontend: rota `/projetos/[id]/encerramento` com form rich + Dialog + render pós-CLOSED em `/projetos/[id]`. Novo `GET /projects/{id}/risks` para pré-marcar materializados (Q1 híbrida). 11 testes vitest |
| 4 | (este commit) | 7 testes pytest do `GET /risks` (débito F5.3.c resolvido) + spec Playwright versionado + conformidade + progresso |

### Métricas (evolução durante F5.3)

| Métrica | Início F5.3 | Commit 1 | Commit 2a+2b | Commit 3 | **Commit 4 (final)** |
|---|---|---|---|---|---|
| pytest backend | 150 | 150 | 171 | 171 | **178** |
| vitest frontend | 84 | 84 | 84 | 95 | **95** |
| Cobertura backend total | (subreport 72%) → **87%** real | **87%** | **88%** | **88%** | **88%** |
| Cobertura `projects.py` | (subreport ~46%) → 67% real | 67% | 90% | 82% | **91%** |

### Decisões respondidas (Q1-Q6 do início da sub-fase)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1** | materialized_risks: automático, manual ou híbrido? | (c) **Híbrido** — backend pré-popula com `Risk.status=MATERIALIZED` do projeto; GP edita livremente (adiciona/remove/comenta). |
| **Q2** | Forma de armazenar materialized_risks | (a) **JSON na coluna** — `list[{risk_id, comment}]`. FK validation em camada Pydantic via JOIN no endpoint, não SQL (JSON não suporta FK constraint nativa). |
| **Q3** | Transição CLOSED irreversível via API? | **Sim** — reabertura é caminho operacional excepcional, não exposto. Documentado no docstring do endpoint. |
| **Q4** | Matriz de bloqueios | Aprovada: ScopeChange PROPOSED, Reports DRAFT/SUBMITTED/PMO_APPROVED/NEEDS_REVISION (desvio intencional, ADR), Baseline DRAFT v2+, Project PAUSED, Project CLOSED (idempotência). Cada mensagem 409 com ação concreta. |
| **Q5** | Quem fecha? | **GP unilateral** (GP-dono). PMO não interfere. |
| **Q6** | UI: modal ou rota? | **Rota dedicada** `/projetos/[id]/encerramento` com form rich + Dialog de confirmação irreversível antes do POST. |

### Decisões internas adicionais

- **`closed_at` não duplicado como coluna** — `ProjectRetrospective.created_at` cumpre semanticamente (registro só existe quando projeto é encerrado). `Project.ended_at` (Date) é o "calendar end date" do cliente.
- **NEEDS_REVISION adicionado à lista bloqueante** — desvio intencional da spec literal (§10.4 lista 3 status). ADR registrado: NEEDS_REVISION é trabalho pendente do GP; permitir encerrar cria órfão semântico.
- **`materialized_risks` no frontend como `Map<risk_id, comment>`** — O(1) lookup, presença=marcado, valor=comment. Conversão para Array só no submit.
- **`GET /retrospective` no detail page só dispara se `status=closed`** — evita 404 ruidoso no console pra projetos ativos.

### Aprendizados marcantes da sub-fase

- **Bug dormente em auth/register descoberto** — SELECT sem `.lower()` + INSERT com `.lower()` causava 500 em vez de 409 em payload com case misto. Bug ativo desde F2; nunca acionado em produção porque clients sempre mandam lowercase. F5.3 commit 2a corrigiu em 3 linhas. Reforça a importância de tests com setup variado.
- **Cobertura real do projeto era 87%, não 72%** — `.coveragerc` com `concurrency=thread,greenlet` revelou que `pytest-cov` subreportava funções `async def`. Métricas históricas (F4, F5.1, F5.2) ficam com a anotação "medidas sem .coveragerc — números reais são maiores". A partir de F5.3, cobertura reportada é real.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~D. Endpoint POST /projects/{id}/close + UI + ProjectRetrospective com 4 campos~~ → endereçado em F5.3 commits 1-4
- Linha "Retrospectiva" §10.4 da tabela principal: ⚠️⚠️ → ✅
- Débito F5.2.d marcado como resolvido (cobertura async)

### Débitos menores P3 do F5.3

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.3 (P3)":

| ID | Item | Status |
|---|---|---|
| **F5.3.a** | Testes para paths defensivos `portfolio.py:97-116` + `scope_changes.py:51,60,98,101,103` | aberto, hardening F5.X/F6 |
| **F5.3.b** | Documentar CWD do pytest pra `.coveragerc` | parcialmente atendido em `dev_notes.md`; Makefile fica como complemento futuro |
| **F5.3.c** | `GET /projects/{id}/risks` sem teste pytest específico | **resolvido em commit 4** (7 testes novos, cobertura 82%→91%) |
| **F5.3.d** | PNGs Playwright F5.3 pendentes | aberto, mesmo problema F5.2 (ambiente local) |

---

## F5.4 — Modo de Report Assistido por IA ✅ FECHADA (parcial — sugestões IA dependem de F2.6)

Pré-população estruturada do novo report (spec v3.1 §10.2): backend cria Report
DRAFT herdando Risks abertos, PendingItems abertos e DeliveryProgress placeholders
para Deliverables com prazo no período. Flag `is_prepopulated` controla badge
visual "Do report anterior" no wizard; backend zera automaticamente ao detectar
edição significativa.

### Commits

| # | Commit | Conteúdo |
|---|---|---|
| 1 | `d90eef5` | Flag `is_prepopulated` em Risk/PendingItem/DeliveryProgress + migration 0017 + service `prepopulate_report` (8 testes cobrindo herança, idempotência, sem baseline ACTIVE, janela 30 dias) |
| 2 | `5e5d258` | Endpoint `POST /projects/{id}/reports/prepopulate` (role GP-dono, tradução de exceções tipadas) + UI radio "Pré-popular" vs "Do zero" em `/reports/novo` com pré-marcação por presença de report anterior |
| 3 | `9dc3a65` | Badge "Do report anterior" no wizard (Risk/PendingItem/DeliveryProgress) + auto-zero da flag no PATCH via snapshot pré-delete + comparação por chave natural |
| 4 | (este commit) | Modal 409 com link "Abrir report existente" + 5 testes adicionais (vitest do modal + 4 testes pytest do auto-zero do commit 3) + Playwright spec versionado + conformidade + progresso |

### Métricas (evolução durante F5.4)

| Métrica | Início F5.4 | Commit 1 | Commit 2 | Commit 3 | **Commit 4 (final)** |
|---|---|---|---|---|---|
| pytest backend | 178 | 186 | 191 | 195 | **195** |
| vitest frontend | 95 | 95 | 99 | 103 | **104** |
| Cobertura backend total | 88% | 88% | 88% | 88% | **88%** |

### Decisões respondidas (Q1-Q5 do início da sub-fase)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1** | Flag `is_prepopulated`: abordagem | (a) **Bool por entidade, zerada ao editar pelo backend** — visual hint do plano F5 + simplicidade. |
| **Q2** | Pré-população server-side ou client-side | (b) **Server-side** — endpoint dedicado `POST /reports/prepopulate`. Robusto a refresh, consistência de sugestões não-determinísticas. |
| **Q3** | Sugestões IA do stub no pre-create | (c) **Pular no MVP** — stub não agrega valor; débito F5.4.X registrado. |
| **Q4** | UX de troca de modo | **Antes do primeiro POST** — radio escolhe; após submit, modo fica fixo. |
| **Q5** | ActionPlan herda? | (b) **Não** — vínculo a Risks/Deliverables herdados; GP recria se faz sentido. Botão "Criar plano vinculado" no wizard fica como débito F5.4.Y. |

### Decisões internas adicionais

- **Status de Report "herdável"** = `(SUBMITTED, PMO_APPROVED, CLIENT_RELEASED, ARCHIVED)`. DRAFT e NEEDS_REVISION descartados como fonte porque ainda estão sendo trabalhados.
- **Filtro Risks segue `OPEN_RISK_STATUSES`** (constante F5.1: IDENTIFIED + MONITORING). Não inventou filtro novo.
- **Janela DeliveryProgress = `[period_start - 30d, period_end]`** — captura entregas atrasadas recentes (trabalho real do período) sem arrastar deliverables antigos esquecidos.
- **Match-by-description para preservar flag no PATCH** — trade-off conhecido (débito F5.4.W); refactor para upsert por ID fica para hardening futuro.
- **Modal 409 com extração de UUID da mensagem** — backend retorna `"/reports/{uuid}"` na mensagem do conflict; regex client-side abre Dialog com link clicável "Abrir report existente" em vez de toast cru.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- ~~C. Modo de Report Assistido por IA~~ → endereçado em F5.4 commits 1-4 (parcial — sugestões IA pendentes em F5.4.X)
- Linha "Modo de Report Assistido por IA" §10.2 da tabela principal: ❌ → ✅ (parcial)

### Débitos menores P3 do F5.4

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.4 (P3)":

| ID | Item | Status |
|---|---|---|
| **F5.4.W** | Match-by-description para preservar `is_prepopulated` em PATCH | aberto; refactor para upsert por ID em hardening futuro |
| **F5.4.X** | Sugestões textuais da IA pendentes | aberto, depende de F5.5/F2.6 |
| **F5.4.Y** | Botão "Criar plano vinculado" ao lado de Risk herdado | aberto, UX enhancement de baixa prioridade |
| **F5.4.Z** | Limitação Vitest em Tabs do Radix (mesmo F5.1.c) | aberto, hardening de testes |
| **F5.4 PNGs** | Playwright PNGs F5.4 pendentes | aberto, mesmo ambiente F5.2/F5.3 |

---

## F5.6a — Setup limpo do WSL + worker básico ✅ FECHADA (parcial — smoke F2.8 em F5.6b)

Constrói o processo `jump-worker` real (consumidor da fila Redis `jobs.agent`)
e atualiza o setup do ambiente WSL para suportar `claude`/`codex` nativos no
Linux. Endereça **parcialmente** o débito K: F2.6 (worker real) cumprido com
pipeline `BRPOP → AgentRunner → callback HMAC + heartbeat`; F2.8 (smoke real
contra `bradesco_sas_databricks.expected.json`) fica para F5.6b.

### Commits

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `0cb9ff9` | docs | Runbook `setup-worker-wsl.md` (12 passos idempotentes + 6 troubleshootings) + ADR worker real (decisões B-α/β/γ agrupadas) |
| 2 | `365e0d7` | chore | `setup-windows.ps1` reescrito idempotente (systemd, Node 20 LTS via NodeSource, PATH `~/.npm-global` precede mount Windows, relatório colorido final por componente) + seção "Como rodar o worker em dev" em `dev_notes.md` |
| 3 | `797785f` | feat(worker) | `worker/worker/{config,hmac_signer,http_client,heartbeat,prompt_builder,main}.py` — pipeline completo Redis→Runner→callback com retry tenacity + dead-letter |
| 4 | `14ed546` | test+docs | 27 testes pytest (worker 82% cobertura) + `.env.example` + `.coveragerc` + atualização `conformidade-v3.1.md` |
| 5 | `5697b7d` | chore | F5.6a.X: NodeSource sem `bash -` root (gpg+tee+apt-get) + `curl -I` preventivo no codex installer |
| 6 | `4c22e53` | fix | **F2.8 destravado:** remove `--bare` de `claude_headless.py` e `wsl_tmux.py` (incompatível com OAuth no v2.1.x — diagnóstico do ADR 2026-05-11) |
| 7 | `adf41b7` | chore | `setup-windows.ps1` escreve PATH em `~/.profile` além de `~/.bashrc` (`bash -lc` não lê bashrc) + dev_notes diagnóstico `--bare` + conformidade atualizada |

### Métricas

| Métrica | Início F5.6a | **Final F5.6a** |
|---|---|---|
| pytest backend | 195 | **195** (sem alteração — F5.6a é puro worker/docs/script) |
| pytest worker | 0 | **27** (novo pacote) |
| vitest frontend | 104 | **104** (sem alteração) |
| Cobertura worker total | n/a | **82%** (gate ≥70% folgado) |
| Cobertura backend total | 88% | 88% |

### Decisões respondidas (B-α/β/γ)

| # | Pergunta | Resposta |
|---|---|---|
| **B-α** | Status `RUNNING` intermediário no callback? | **(a) Não muda nada.** Heartbeat já dá observability suficiente. Reabrir quando alguém pedir granularidade do estado entre QUEUED e DONE. |
| **B-β** | Construção do prompt em F5.6a — stub ou real? | **(a) Stub mínimo.** Templates curtos hardcoded por `task_type` (`proposal_extraction` / `report_analysis` / `portfolio_pattern`). Prompt versionado real entra em F5.6b junto com o smoke. |
| **B-γ** | Download de `input_files` do R2 em F5.6a? | **(a) Pula.** F5.6a roda jobs sintéticos para validar transporte. Download via boto3 (lib já em deps) é trabalho de F5.6b. |

### Decisões internas adicionais

- **`worker_stub.py` preservado, não substituído.** Inventário inicial revelou que o stub é asyncio in-process (sem Redis), controlado por `STUB_WORKER_ENABLED` — fallback de dev. O worker real é processo separado em `worker/worker/main.py`. Briefing original previa substituição; ADR registra o desvio.
- **Worker NÃO usa `concurrency=greenlet` no `.coveragerc`** (diferente do backend). Worker é puro asyncio sem ORM async (sqlalchemy[asyncio]/asyncpg/aiosqlite). Adicionar greenlet sem a lib estar nas deps quebra com `ConfigError: Couldn't trace with concurrency=greenlet, the module isn't installed`. Documentado na nota do `worker/.coveragerc`.
- **HMAC client-side em `worker/hmac_signer.py` espelhado de `backend/app/core/worker_auth.py`** sem importar do backend (worker é pacote independente). Teste `test_signature_replicates_backend_verify_signature` garante que os dois cálculos produzem o mesmo hex — falhar lá significa HMAC quebra em prod.
- **`tmux NUNCA mata sessão existente`** no `setup-windows.ps1` novo. Versão antiga fazia `tmux kill-session` antes de recriar, descartando login válido entre rodadas. Novo script usa `tmux has-session` antes; sessões persistentes preservam credenciais.
- **Validação `[System.Management.Automation.Language.Parser]::ParseFile` antes do commit do `.ps1`** pegou bug do em-dash `—` em string PowerShell em ambiente Windows-PT (CP1252 vs UTF-8). Substituído por `-`. Lição vai pra `dev_notes.md` em ciclo futuro.
- **Plano B do Codex como operacionalmente aceitável.** Se URL `https://codex.openai.com/install.sh` mudar, runbook documenta 3 alternativas + opção de rodar **só com Claude** (CodexProvider reporta `BROKER_UNAVAILABLE` cedo, AgentRunner cai pra primary apenas).

### Aprendizados marcantes da sub-fase

- **Inventário ativo antes de codar evita refactor enorme.** Briefing pedia "substituir `worker_stub` por `worker_real`". Inventário revelou que (1) o stub é asyncio in-process — não substituível; (2) `jump_agent_runner` já tinha 80% pronto desde F1 (AgentRunner com fallback, providers, brokers, routes, validator, observer); (3) `worker/worker/main.py` é o que faltava; (4) endpoint `POST /internal/agent-results/{run_id}` com HMAC + `WorkerHeartbeat` model já existiam no backend desde F2. F5.6a virou enxuto porque não houve reimplementação de máquina pronta.
- **Cobertura `concurrency=greenlet` é armadilha sutil ao espelhar configs.** Backend depende de greenlet por sqlalchemy[asyncio]→asyncpg; worker não tem ORM. Espelhar `.coveragerc` direto causou `ConfigError` em runtime. Vale validar `concurrency=...` contra deps reais antes de copiar config.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- **K. F2.8 — smoke real do agente leitor** → marcado como **parcial** (F5.6a entregou worker real; F5.6b fecha smoke).

### Débitos menores P3 do F5.6a

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.6a (P3)":

| ID | Item | Status |
|---|---|---|
| **F5.6a.X** | `curl -I` preventivo na URL do codex installer antes do `curl | sh` | aberto, refactor em F5.6b ou F6 |
| **F5.6a.Y** | Onde o `jump-worker` roda (Windows host vs WSL Linux) — decisão arquitetural | aberto, F5.6b força a escolha pelo smoke |

---

## F5.6b — Smoke real do agente leitor contra Bradesco ✅ FECHADA

Roda o smoke F2.8 end-to-end (debito K do `conformidade-v3.1.md`): carrega
prompt versionado `proposal_reader_v1.md`, alimenta texto pre-extraido da
proposta Bradesco para o `AgentRunner`, compara o JSON resultante contra
`bradesco_sas_databricks.expected.json`, decide pass/shadow/fail por recall
ponderado (criticidade-aware).

### Commits

| # | Hash | Tipo | Conteúdo |
|---|---|---|---|
| 1 | `177e5ee` | chore | `setup-windows.ps1` etapas 3.11–3.14: `uv` via `pip --user` (sem `curl|sh`), Python 3.12 em userspace, venv worker em `~/.jump-runner/.venv-worker`, `uv pip install -e jump_agent_runner worker`. **Resolve F5.6a.Y: jump-worker roda dentro do WSL Linux** (claude no PATH nativo, sem mount). |
| 2 | `84f5e72` | feat | `scripts/f28_smoke_bradesco.py` — invoca `AgentRunner(ClaudeProvider, CodexProvider)` direto contra a proposta Bradesco com o prompt v1. Workspace, schema_hint, metadata logada para o comparador. |
| 3 | `92ffb61` | feat | `scripts/f28_compare_bradesco.py` (Jaccard + recall simples + recall ponderado) + `scripts/f28_show_bradesco_output.py` (debug helper) + `docs/f28-bradesco-baseline-quality.md` (relatório completo + decisão operacional aprovada). |
| 4 | `(este)` | docs | ADR fechamento débito K + atualização `conformidade-v3.1.md` (K marcado ✅) + atualização `fase-5-progresso.md`. |

### Resultado do smoke

Run `f28-bradesco-1778780537` (2026-05-14, 159.2s, Claude headless, 1 tentativa,
sem fallback):

| Chave | Recall | Match | Notas |
|---|---|---|---|
| `project` | 90.9% | 10/11 | Perde só `estimated_capacity_per_sprint_hours` (calculável trivialmente) |
| `phases` | 100.0% | 4/4 | sprint-1/2/3 + phaseout |
| `deliverables` | 100.0% | 21/21 | Core do baseline em PERFEITO |
| `key_premises` | 0% strict | 0/4 (+16 extras) | Artefato do Jaccard de palavras para sinônimos; substância coberta nos extras |
| `out_of_scope` | 33.3% | 1/3 (+17 extras) | 1 match literal; 2 itens do expected não capturados (risco controlado) |

**Recall simples:** 64.8% → SHADOW.
**Recall ponderado (criticidade-aware, deliverables peso 2):** 81.5% → **PASS**.

### Decisões respondidas (Q1/Q2/Q3 do briefing)

| # | Pergunta | Resposta |
|---|---|---|
| **Q1 (F5.6a.Y)** | Onde o `jump-worker` roda — Windows host vs WSL Linux? | **(a) WSL Linux.** Python venv via `uv` em `~/.jump-runner/.venv-worker`. Claude resolvido pelo subprocess Python aponta para nativo `~/.npm-global/bin/claude`, sem mount cross-OS. |
| **Q2** | Extrair PDF do R2 no fly ou usar `.txt` pré-extraído? | **(b) `.txt` pré-extraído** (`backend/tests/fixtures/proposals/bradesco_sas_databricks.txt`). Isola "agente leitor" de "extração de PDF". Download R2 + pypdf no fly fica para F5.6c/F5.9 se necessário. |
| **Q3** | Modo de comparação — strict, normalizado, ou soft? | **Híbrido evoluído:** normalize + substring + Jaccard ≥ 0.45. Quando a métrica simples ficou em SHADOW mas inspeção visual mostrou que era artefato do Jaccard para sinônimos, adicionei **métrica ponderada por criticidade** como segundo veredito. Reportar ambos é mais honesto que escolher um. |

### Decisão operacional final

**Aprovada por Christopher Tominaga em 2026-05-14:**

- **PASS técnico** (recall ponderado 81.5%). Agente leitor v1 entra em produção no piloto Bradesco.
- **SHADOW na semana 1**. Spec v3.1 §1.5 já prevê. GP audita primeiro baseline real.
- **Upgrade condicional para AUTOMÁTICO na semana 2+**. Critério binário: se GP editar pouco/nada em premises/oos do primeiro baseline, agente promove. Se editar muito, fica em shadow e abre ciclo de iteração para `proposal_reader_v1.1.md`.

### Decisões internas adicionais

- **Comparador com duas métricas vale o esforço.** Jaccard de palavras é fraco para sinônimos PT-BR — "código SAS legado" vs "scripts SAS originais" tem Jaccard 0.08 mas é a mesma premissa. Reportar só métrica simples seria injusto com o agente e levaria a iteração de prompt desnecessária. Reportar só ponderado esconde a fragilidade da heurística. Reportar AS DUAS dá ao operador o sinal correto.
- **F5.6a.Y resolvida da forma menos invasiva.** Alternativa (b) — wrapper em `ClaudeHeadlessRoute._claude_path` que invoca `wsl.exe -- claude ...` — exigiria refactor do `jump_agent_runner` e injeção de configuração específica para Windows host. Manter Python dentro do WSL é mais simples, mais aderente à spec original do `02_jump_agent_runner_spec.md §6.1`, e usa o mesmo `~/.npm-global/bin/claude` que já validamos.
- **`uv` via `pip install --user`, não `curl|sh`** — mesma decisão arquitetural do F5.6a.X (NodeSource sem `bash -` root). Guard interno do Claude Code bloqueia `curl|sh` durante F5.6b — confirmação independente da consistência da regra.

### Aprendizados marcantes da sub-fase

- **O bug F2.8 do ADR 2026-05-11 era múltiplo, não único.** A causa raiz (descoberta em F5.6a) era `--bare` desabilitando OAuth. Mas mesmo após o fix, sem o venv Python no Linux (resolução F5.6a.Y), o `subprocess` rodando do Windows host resolveria claude para o mount e voltaria o bug. **Os dois precisavam ser corrigidos simultaneamente** — fix no `claude_headless.py` (F5.6a commit `4c22e53`) + Python rodando no Linux (F5.6b commit `177e5ee`). Cada um isoladamente não bastava.
- **Métricas heurísticas precisam de leitura qualitativa.** Quando o número diz uma coisa e a inspeção visual diz outra, a heurística está errada — não a realidade. F5.6b absorveu isso: dois números, decisão explícita do humano. Padrão a copiar em outras avaliações de IA-output futuras.

### Conformidade — itens marcados em `docs/conformidade-v3.1.md`

- **K. F2.8 — smoke real do agente leitor** → **FECHADO**. Era débito desde ADR 2026-05-11. F5.6a entregou o worker e diagnosticou bug `--bare`; F5.6b rodou o smoke real e validou o agente em produção (com SHADOW de salvaguarda na semana 1).

### Próximas sub-fases

Com F5.6 (a+b) fechada, o caminho crítico para o **lançamento do piloto Bradesco** está claro:

- **F5.7 — LGPD**: depende de Christopher como DPO produzir/aprovar `docs/lgpd.md`. Pré-deploy obrigatório.
- **F5.5 — Inteligência cruzada**: independente do piloto; pode rodar em paralelo.
- **F5.8 — Export PDF/PPTX**: independente; pode ficar para depois do piloto começar (não bloqueia).
- **F5.9 — Deploy Railway + v3.2 consolidada**: depende de F5.7 (LGPD assinado). F5.6b (smoke validado) já cumprido.

---

## F5.7 — LGPD ✅ FECHADA

Aberta em `docs/decisoes.md` ADR `2026-05-14 — F5.7 / Abertura` e fechada em `2026-05-15 — F5.7 / Fechada`. Pré-requisito formal de F5.9 (deploy Railway com piloto Bradesco) atendido.

**Modo confirmado pós-execução:** híbrido. Agente produziu `docs/lgpd.md` v1.0 e `docs/rat.md` v1.0; DPO Christopher Tominaga revisou e assinou como signatário designado. Anderson Argentoni atua como receptor operacional do canal externo (`anderson.argentoni@jumplabel.com.br`) — alias `lgpd@jumplabel.com.br` é débito F5.7.Z. Revisão jurídica externa permanece como débito v1.1.

**5 commits sequenciais aprovados commit-a-commit pelo humano:**

| # | SHA | Tipo | Resumo |
|---|---|---|---|
| 1 | `640bd28` | docs | `docs/lgpd.md` v1.0 + `docs/rat.md` v1.0 + ADR abertura + apêndice nesta página (status EM ANDAMENTO). 4 arquivos, +451/-9. |
| 2 | `b5f1fd0` | feat(backend) | Migration `0018_users_anonymized_at` (`TIMESTAMPTZ NULL` + índice parcial) + `services/data_export_service.py` (ZIP em memória com 5 arquivos) + schemas `data_export.py` + `GET /me/data-export` + 5 pytests (smoke, cobertura, RBAC sem token, RBAC cross-user, filtro CLIENT). 7 arquivos, +1390. |
| 3 | `1e47cbc` | feat(backend) | `POST /me/data-deletion-request` (notifica DPO + recibo neutro ao titular via Resend dry-run) + `admin_data_requests.py` (POST manual / GET paginado / POST fulfill com anonimização idempotente, role PMO) + schemas `data_request.py` + login guard 401 idêntico ao de senha errada em `auth.py` + 7 pytests. 6 arquivos, +658/-7. |
| 4 | `f54c020` | feat(frontend) | Página `src/app/admin/data-requests/page.tsx` (App Router, segue padrão de `pmo/scope-changes`) + `apiAdminDataRequests.{list,createManual,fulfill}` em `lib/api.ts` + tipos LGPD em `lib/types.ts` + link "LGPD" no `AppShell` (somente PMO; OPERATOR cai no 403 do backend) + polyfill `scrollIntoView/hasPointerCapture` em `tests/setup.ts` (libera testes de Radix Select) + 4 vitests. 6 arquivos, +721/-1. |
| 5 | `(este)` | test+docs | `test_lgpd_e2e.py` (titular → pedido → DPO recebe e-mail dry-run → PMO fulfill → titular tenta login → 401 idêntico ao de senha errada) + correção de `conformidade-v3.1.md:60` (linha "presumido" reescrita auditando os 9 campos reais do `DataProcessingRecord` + remissão para `docs/rat.md` como local dos campos `processing_purpose`/`legal_basis`/`retention_period`) + ADR de fechamento em `decisoes.md` + apêndice nesta página. |

**Métricas:**

| Métrica | Início F5.7 | **Final F5.7** |
|---|---|---|
| pytest backend | 195 | **208** (+5 export + 6 deletion + 1 sanity-check module + 1 E2E = +13; 1 skipped pré-existente) |
| vitest frontend | 104 | **108** (+4 admin/data-requests) |
| Linhas de código (delta cru) | — | +3220 / -17 (4 commits de feat/test + 1 commit de docs) |
| Endpoints novos no backend | 0 | **5** (`GET /me/data-export`, `POST /me/data-deletion-request`, `POST /admin/data-requests`, `GET /admin/data-requests`, `POST /admin/data-requests/{id}/fulfill`) |
| Migrations novas | — | **1** (`0018_users_anonymized_at`) |
| Rotas novas no frontend | — | **1** (`/admin/data-requests`) |
| Cobertura backend (pytest) | sem regressão | sem regressão; `data_export_service` e `admin_data_requests` exercitados pelos 13 testes LGPD |
| tsc + lint frontend | — | tsc sem erros; lint só com warnings pré-existentes em arquivos fora de F5.7 |

**Decisões resolvidas no fechamento (não eram do ADR de abertura):**

| Decisão | Resolução |
|---|---|
| Ordem de gravação do log de auditoria no `GET /me/data-export` | Build do ZIP **antes** de gravar `DataProcessingRecord(EXPORT, FULFILLED)`. Snapshot reflete estado pré-requisição; log do ato aparece em exports subsequentes. Alternativa rejeitada (log primeiro) deixaria FULFILLED órfão em falha de build. |
| Onde registrar o `me_router`/`admin_data_requests_router` | Em `app/main.py` via `app.include_router(...)`, seguindo a convenção real do repo. Briefing inicial sugeria `__init__.py`, que está vazio na prática. |
| Aria do filtro Select no vitest | jsdom não implementa `Element.scrollIntoView`/`hasPointerCapture` — polyfill no-op em `tests/setup.ts` libera Radix Select sem afetar produção. |

**Débitos finais (carregados do ADR de abertura, sem mudança):**

- **F5.7.X (v1.1)** — Anonimização de texto livre em descrições de `Risk`/`PendingItem`/`ActionPlan` e seções narrativas de `Report`. v1.0 retém com justificativa em [`docs/lgpd.md`](lgpd.md) §6.4/§10 (LGPD art. 16 II).
- **F5.7.Y (v1.1)** — Formulário web público para abertura de pedido por titular externo. v1.0 cobre via `POST /admin/data-requests` (DPO transcreve manualmente).
- **F5.7.Z (v1.1)** — Provisionamento do alias `lgpd@jumplabel.com.br` e migração do canal documentado em `docs/lgpd.md` e `docs/rat.md`. v1.0 opera com `anderson.argentoni@jumplabel.com.br`.
- **L (v3.2 da spec)** — Spec consolidada lista `processing_purpose`/`legal_basis`/`retention_period` no `DataProcessingRecord`. Esses campos vivem por atividade em `docs/rat.md`, não no modelo SQL. `conformidade-v3.1.md:60` já reflete; ajuste na spec entra no próximo ciclo.

**Checkpoints humanos:** #1 (inventário + plano) concluído em 2026-05-14. #2 (DPO lê `docs/lgpd.md` e `docs/rat.md` inteiros) concluído em 2026-05-15. #3 (rodar `GET /me/data-export` local antes do Commit 5) **não exercido** — aprovação direta para sequenciamento dos commits restantes após Commit 3.

**Lições operacionais:**

- **Pré-existência do `DataProcessingRecord` no domínio salvou complexidade**: modelo já estava em `domain.py:973-996` desde F2 (entrou na primeira modelagem completa do schema), com `DPRequestType`/`DPRequestStatus`. F5.7 só consumiu essas entidades — não houve migration de modelagem, só `users.anonymized_at`.
- **Cascata de FKs do `User` força anonimização (não hard-delete)**: `Project.gp_user_id`, `Proposal.uploaded_by_id`, `Report.created_by_id`, `ReportApproval.approver_id` são NOT NULL. Q1 do ADR de abertura ratificou anonimização; isso preserva integridade referencial sem violar art. 16 II (exercício regular de direitos).
- **Resend dry-run é o caminho operacional do piloto**: `_send_email` em [`notifications.py`](../backend/app/services/notifications.py) já detecta `RESEND_API_KEY` ausente e cai em modo log — F5.7 reaproveitou sem nenhum acoplamento novo. Quando o domínio `jump.tec.br` for verificado (débito F0), notificações reais saem automaticamente sem mudança de código.
- **Frontend só precisou de 1 polyfill jsdom**: pre-existência de Radix Select + Dialog + Input + Textarea no design system removeu necessidade de componentes novos. A maior decisão de UX foi o modal de confirmação com alerta de irreversibilidade — espelha o pattern do encerramento de projeto (F5.3).

---

## F5.5, F5.8, F5.9 — Pendentes

Conforme plano em `docs/fase-5-plano.md`. F5.6 (a+b) e F5.7 (em andamento) destravam o caminho crítico:

| # | Sub-fase | Estimativa | Bloqueia / é bloqueada por |
|---|---|---|---|
| F5.5 | Agente de Inteligência Cruzada (heurística inicial + flag) | ~30k | depende de F5.3 (✅); worker real (F5.6a ✅) já suficiente |
| F5.8 | Exportação PDF/PPTX | ~50k (teto) | livre |
| F5.9 | Deploy Railway + v3.2 consolidada | ~40k | depende de F5.6b (✅) + F5.7 (✅ LGPD piloto v1.0 fechado) |

---

## Decisões respondidas (4 de 8 do plano F5)

| # | Pergunta | Resposta |
|---|---|---|
| **#1** | F5.5 antes ou depois do piloto rodar? | **Construir infra agora, ativar UI quando 5+ projetos encerrados.** Implementação: flag `portfolio_intelligence_enabled` em `PortfolioConfig` (default false). Backend produz insights independente da flag (alimenta histórico). UI mostra card aguardando volume mínimo + contagem; quando flag=true, exibe insights reais. Gatilho via `PATCH /portfolio/config`. |
| **#2** | F5.6 WSL setup — Christopher instala ou runbook? | **Runbook.** Quando F5.6 chegar, eu produzo `docs/runbooks/setup-worker-wsl.md` detalhado (pré-requisitos máquina, WSL2 Ubuntu, instalação `claude`/`codex` no Linux puro, login interativo passo a passo, tmux com persistência, smoke test após cada passo). Christopher executa manualmente. |
| **#3** | F5.7 LGPD — texto jurídico revisado por advogado externo? | **(a) v1.0 piloto Bradesco com DPO Christopher Tominaga como signatário; revisão jurídica externa fica como pré-requisito formal de v1.1.** Cabeçalho da v1.0 explicita o status. Razão: piloto Bradesco já tem contrato comercial assinado; LGPD do produto é polimento sobre operação contratada, não criação. Atrasar por advogado externo adiaria F5.9 sem ganho proporcional. Detalhamento no ADR `2026-05-14 — F5.7 / Abertura`. |
| **#7** | F5.1 — F.Risk: drop+recreate ou backfill heurístico? | **Drop+recreate.** Investigação confirmou COUNT(*) FROM risks = 0 (mesma máquina, mesmo banco in-memory, ambiente pré-piloto). Estratégia replicada para Deliverable enums (D1+D2) também sem cerimônia. |

---

## Decisões pendentes (4 de 8) — pedir antes de cada sub-fase relacionada

| # | Pergunta | Quando vou perguntar |
|---|---|---|
| **#4** | F5.8 — PDF e PPTX ambos, ou só PDF inicialmente? PPTX exige mais código (`python-pptx` mais arestas que `reportlab`). PDF cobre 80% dos casos. | Antes de iniciar F5.8 |
| **#5** | F5.9 — deploy beta no Railway com dados seed ou esperar piloto real autorizar? Bradesco tem requisitos próprios (LGPD assinado, contratos de tratamento). | Antes de iniciar F5.9 |
| **#6** | F5.X (P3 hardening) — dentro de F5 ou postergar para F6? A spec v3.1 §10 (Plano em fases) coloca esses itens em F6. | Quando decidir entre fechar F5 ou ampliar |
| **#8** | F5.6 — engine primário do worker real continua Claude ou aposta em Codex inicialmente? Smoke F2.8 vai decidir, mas pode haver preferência de operação. | Antes de iniciar F5.6 |

---

## Débitos acumulados — links para contexto

### Débito K — F2.8 smoke real do agente leitor adiado

**Onde:** `docs/decisoes.md` (ADR 2026-05-11 — "F2.8 adiado para F5") + tabela em `docs/conformidade-v3.1.md`
**Motivo:** `claude` CLI v2.1.138 instalado no Windows e acessado via mount WSL errático em modo headless após login interativo
**Plano:** absorvido em F5.6 (WSL clean + F2.6 + F2.8 num pacote por compartilhar pré-requisito)

### Débito L — v3.1 §6.4.1 desatualizada

**Onde:** `docs/decisoes.md` (Adendo do ADR 2026-05-11) + `docs/conformidade-v3.1.md` (linha do schema ProposalExtraction)
**Motivo:** enums do schema/prompt v1 divergiram do que a spec §6.4.1 listava. Prompt vence (fonte), spec será atualizada
**Plano:** gerar v3.2 consolidada em F5.9 com diff explícito do que mudou (regra de governança ADR 2026-05-08)

### Débitos menores P3 do F5.1

Todos em `docs/conformidade-v3.1.md` seção "Débitos menores de F5.1 (P3)":

| ID | Item | Onde aparece |
|---|---|---|
| **F5.1.a** | `open_critical` em Python (não SQL) por causa de property `Risk.level` | `app/api/v1/portfolio.py` linhas ~94-101 |
| **F5.1.b** | `Severity` (frontend) + `RiskLevel` (backend) coexistem com mesmos 4 valores | `frontend/src/lib/types.ts` linha 103 + `backend/app/models/domain.py` classe RiskLevel |
| **F5.1.c** | Vitest não renderiza shadcn `<TabsContent>` em jsdom isolado | Tentativa removida em `e888415`; compensado por shape tests puros |

---

## Estado do repo (HEAD)

```
7263526 feat(backend,frontend): F5.1 PendingItem com impact+open_date v3.1 §4.2.5
1284bc5 feat(backend,frontend): F5.1 Deliverable com type+acceptance+dependencies+status v3.1 §4.2.2
edaec34 feat(backend,frontend): F5.1 ActionPlan com objective+vinculacoes v3.1 §4.2.4
e888415 feat(backend,frontend): F5.1 Risk com probability+impact+level+status v3.1 §4.2.3
f9c3fce docs: plano de F5 com 9 sub-fases e ~390k tokens estimados
bc32d04 fix(backend): alinhar SOURCE_EXCERPT_MAX ao prompt v1 R4
9824b96 docs: fase-4-relatorio.md final
[...]
```

---

*Documento atualizado ao fim de cada sub-fase de F5 fechada. Próximo update: ao fim de F5.5.*
