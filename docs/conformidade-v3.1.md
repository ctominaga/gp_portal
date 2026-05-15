# Tabela de Conformidade — Implementação atual × spec v3.1

**Data:** 2026-05-08
**Fonte:** `docs/spec_consolidada_v3.1.md`
**Estado da implementação:** F4 quase aprovado, antes do Mini-ciclo B (relatório).

Cada linha marca conformidade da implementação contra a v3.1. Símbolos:

- ✅ — conforme
- ⚠️ — desvio (parcial ou semântico) que precisa virar AJUSTE
- ❌ — não implementado
- — — fora do escopo do MVP / fora do que foi auditado

---

## Seção 4 — Módulos Funcionais

| Item | v3.1 § | Implementação | Conformidade |
|---|---|---|---|
| Onboarding: cadastro + upload + agente leitor + revisão + ativação | 4.1 | Frontend/backend completos; agente leitor é stub (real em F2.6) | ✅ |
| RAG por dimensão (3 independentes: prazo, escopo, qualidade) | 4.2.1 | `Report.rag_prazo/rag_escopo/rag_qualidade` | ✅ |
| Justificativa obrigatória quando A/R | 4.2.1 | Validação no submit | ✅ |
| Worst-of-3 derivado para `rag_status` agregado | 4.2.1 | `Report.rag_status` derivado | ✅ |
| Progresso entregas: `revised_date` em campo dedicado | 4.2.2 | `DeliveryProgress.revised_date` | ✅ |
| `deviation_flag` derivado revisado vs planejado | 4.2.2 | Flag persistida pelo backend | ✅ |
| Modal de critério de aceite ao marcar 100% + Concluído | 4.2.2 | Modal existe (F3.5 screenshot `f35-6-wizard-criterio-aceite`); confirmação **não persiste** em campo (`acceptance_confirmed` ausente em `DeliveryProgress`) | ⚠️ |
| Riscos: probabilidade × impacto separados, com nível derivado | 4.2.3 | `Risk.severity` único (Severity enum), sem prob/impact discretos | ⚠️ |
| Riscos: campo `mitigation_plan` | 4.2.3 | Ausente no modelo `Risk` | ⚠️ |
| Riscos: status (Identificado/Monitoramento/Mitigado/Materializado) | 4.2.3 | `RiskStatus` (auditar valores — só vi `OPEN`) | ⚠️ |
| Planos de Ação: ação + objetivo + responsável + prazo + status + vinculação | 4.2.4 | `ActionPlan` tem description+owner+due_date+status; **falta** `objective`, `linked_risk_id`, `linked_deliverable_id` | ⚠️ |
| Pendências: descrição, responsável (interno/cliente), datas, status, impacto | 4.2.5 | `PendingItem` tem description, owner_party, due_date, status; **falta** `open_date` distinto e `impact` | ⚠️ |
| Destaques + Próximos passos textuais obrigatórios | 4.2.6/7 | `Report.highlights`, `Report.next_steps` | ✅ |
| Visão Cliente curada com botão Confirmar leitura | 4.3 | Portal `/portal/projetos/[id]` com `confirm-read` | ✅ |
| Linguagem não-técnica gerada por agente (não regex/template) | 4.3 | Não auditei se a tradução é gerada pelo agente ou só repassa texto do GP | — |
| Dashboard PMO com Health Score visível em cards | 4.4 | Página `/pmo/portfolio` com gauges | ✅ |
| Drill-down em qualquer projeto | 4.4 | Existe | ✅ |
| Histórico/linha do tempo de RAG, progresso, riscos, escopo | 4.5 | Reports persistidos e listáveis; gráficos de tendência não auditados | — |

## Seção 9.5 — Modelo de Dados

| Entidade | v3.1 espera | Implementação (`domain.py`) | Conformidade |
|---|---|---|---|
| `User` | id, name, email, password_hash, role, created_at | igual | ✅ |
| `Project` | id, name, code, client_id, gp_id, status, datas, periodicity | semelhante (não auditei campo a campo) | ✅ presumido |
| `Proposal` | id, project_id, version, file_path, raw_text, processed_at | semelhante | ✅ presumido |
| `Baseline` | id, project_id, proposal_id, version, status, confirmed_at/by | semelhante | ✅ presumido |
| `Deliverable` | ext_id, name, description, phase, **type**, planned_date, **acceptance_criteria**, **dependencies**, source_excerpt, **status** | code, title, description, phase, **category+complexity** (em vez de type), due_date (=planned), source_excerpt; **falta** acceptance_criteria, dependencies, status | ⚠️ |
| `Report` | status_schedule/scope/quality, justification_*, highlights, next_steps, submitted_at, approved_at, approved_by | `rag_prazo/escopo/qualidade` (PT-BR), `rag_*_justificativa`, highlights, next_steps, submitted_at, approved_at; aprovador no `ReportApproval` separado | ✅ (semanticamente equivalente; nomes em PT-BR) |
| `DeliveryProgress` | report_id, deliverable_id, completion_pct, revised_date, deviation_flag, **acceptance_confirmed** | report_id, deliverable_id, percent_complete, revised_date, deviation_flag, status, comment; **falta** `acceptance_confirmed` | ⚠️ |
| `Risk` | description, **probability**, **impact**, **level**, status, **mitigation_plan**, owner | description, **severity** (único), owner_id, due_date, status | ⚠️ |
| `ActionPlan` | action, **objective**, owner, due_date, status, **linked_risk_id**, **linked_deliverable_id** | description, owner_id, due_date, status; **falta** objective + vinculações | ⚠️ |
| `PendingItem` | description, **responsible_type**, **open_date**, due_date, status, **impact** | description, owner_party, due_date, status; **falta** impact + open_date distinto | ⚠️ |
| `AIInsight` | id, scope, project/report id, type, message, priority, source_agent, acknowledged_at | scope + payload JSON com tipo/severity/headline/detail; modelagem por payload em vez de colunas | ✅ (modelagem alternativa equivalente) |
| `ScopeChange` | project_id, **baseline_from_id**, **baseline_to_id**, **change_type**, description, **approved_by**, **approved_at** | project_id, description, requested_at, decided_at, status, impact_baseline_id; **falta** baseline_from/to, change_type, approved_by | ⚠️⚠️ |
| `ReportApproval` | decision ∈ {**approved**, **approved_with_comment**, **requested_changes**} | decision ∈ {APPROVED, **REJECTED**, REQUESTED_CHANGES} | ⚠️⚠️ |
| `ProjectRetrospective` | **delivered_vs_proposed**, **materialized_risks**, **would_do_differently**, **client_feedback**, closed_at | lessons_learned (texto único) + kpis (JSON) + created_at; **modelo radicalmente divergente** | ⚠️⚠️ |
| `PortfolioConfig` | singleton com `health_score_weights` JSONB para **5 pesos** | 4 colunas (`weight_progress/risks/pendings/schedule`); modela 4 dimensões | ⚠️⚠️ |
| `AgentRunLog` | run_id PK, task_type, engine_used, route_used, attempts JSONB, duration, worker_id, artifact_path, failover_occurred | igual | ✅ |
| `WorkerHeartbeat` | worker_id PK, last_seen_at, status, sessions_status JSONB, contadores | igual | ✅ |
| `DataProcessingRecord` | id, subject_*, processing_purpose, legal_basis, retention_period | `domain.py` define id, subject_user_id, subject_external_email, request_type, status, requested_at, fulfilled_at, handled_by_id, notes. `processing_purpose` / `legal_basis` / `retention_period` **não estão no modelo SQL** — vivem por atividade em [`docs/rat.md`](rat.md) (Registro de Atividades de Tratamento). Endpoints F5.7 cobrem §12 inteira (GET /me/data-export, POST /me/data-deletion-request, POST /admin/data-requests, fulfill). Texto da spec v3.1 §9.5 (modelo SQL com `legal_basis` por linha) é considerado divergência consciente — vide débito **L** em docs/decisoes.md. | ✅ |

## Seção 10 — Melhorias do Processo Incorporadas

| Item | v3.1 § | Implementação | Conformidade |
|---|---|---|---|
| **Fluxo de aprovação em 3 estágios** (Aprovar direto / Aprovar com comentário / Devolver para revisão) | 10.1 | Backend: 1 endpoint `POST /reports/{id}/decide` com decision ∈ {approved/rejected/requested_changes}. Frontend PMO (`pmo/reports/[rid]/review`): 2 botões ("Pedir revisão", "Aprovar"). **Falta** terceiro caminho explícito; falta valor `approved_with_comment` no enum; modal não comunica que o comentário é nota interna | ⚠️⚠️ |
| **Modo de Report Assistido por IA** (pré-popula riscos do report anterior, sugestões do agente) | 10.2 | Endereçado em **F5.4** (commits `d90eef5` modelo+service, `5e5d258` endpoint+UI radio, `9dc3a65` badge+auto-zero, `+commit 4` testes+docs). Cumpre 80% da spec §10.2 — herança de Risks/Pendings/DeliveryProgress placeholders funciona. **Sugestões textuais da IA (§10.2 ponto 3) ficam para F5.5/F2.6** quando agente real chegar (débito F5.4.X). | ✅ (parcial) |
| **Health Score com 5 componentes** (RAG médio 0.35 + SPI 0.25 + Risco_inv 0.20 + Resolução 0.10 + Estabilidade 0.10) | 10.3 | `health_score.py` tem **4 componentes** (progress, risks, pendings, schedule) com fórmula divergente. **Faltam**: Status RAG médio (não usa o RAG das dimensões), SPI (usa % done bruto, não real÷planejado), Estabilidade (não computado). Pesos defaults discretos em 4 colunas, não 5 com defaults 35/25/20/10/10 | ⚠️⚠️⚠️ |
| Pesos do Health Score editáveis pelo PMO | 10.3 | Tela `/pmo/portfolio/config` permite editar 4 pesos | ✅ (estrutura existe; precisa adaptar para 5) |
| Faixas de classificação (≥70 verde, 40-69 âmbar, <40 vermelho) | 10.3 | `_band()` em `health_score.py`: 70/40 — **conforme** | ✅ |
| **Retrospectiva ao encerrar projeto** (POST /projects/{id}/close + 4 campos estruturados) | 10.4 | Endereçado em **F5.3** (commits `fe93d50` modelo+migration+`.coveragerc`, `4de0188` bug-fix auth, `93bf7bc` endpoint+cascata Q4, `bf5b97f` frontend+GET /risks, `+commit 4` testes+docs). Modelo refatorado para 4 campos NOT NULL + materialized_risks JSON. POST /close com cascade 8 validações. UI `/projetos/[id]/encerramento` + render read-only pós-CLOSED. | ✅ |
| **Versionamento de escopo** (upload v2 → diff vs v1 → ScopeChange por item → aprovação) | 10.5 | Endereçado em **F5.2** (commits `cd8fc45` `1b85e09` `886b74c` `c92b076` + commit 5). Modelo ScopeChange refatorado (+`baseline_from_id`, `baseline_to_id`, `change_type`, `approved_by_id`, `deliverable_code`). `diff_baselines` cobre os 3 change_types (added/removed/modified). `POST /baselines/{id}/transition` (PMO, batch). Gate em activate_baseline para v2+. UI: `/pmo/scope-changes`, botões PMO em `/diff`, badge no portfólio. | ✅ |
| Integrações (Jira, Slack, etc.) | 10.6 | Fora do MVP por design | — |

---

## Lista priorizada dos desvios → AJUSTES

Ranking por impacto no contrato com o usuário e na fidelidade à fonte única.

### Prioridade 1 — bloqueiam Mini-ciclo B (relatório do F4)

| # | Desvio | § v3.1 | Impacto |
|---|---|---|---|
| **A** | Aprovação só tem 2 caminhos UI (falta "Aprovar com comentário"). Enum tem REJECTED no lugar de APPROVED_WITH_COMMENT | 10.1 | Contrato com PMO violado; o que é "nota interna ao GP" hoje só existe implicitamente |
| **B** | Health Score com fórmula divergente em 3 dos 5 componentes (sem RAG médio, sem SPI real÷planejado, sem Estabilidade); 4 pesos em vez de 5 | 10.3 | Métrica central do PMO calcula coisa diferente da spec; `PortfolioConfig` precisa migrar; defaults precisam ancorar em 35/25/20/10/10 |

Esses são os AJUSTES 2 e 3 que você sinalizou no início desta conversa, agora ancorados em fonte única.

### Prioridade 2 — débito de F5 (não bloqueiam fechar F4)

| # | Desvio | § v3.1 |
|---|---|---|
| **C** | Modo de Report Assistido por IA não implementado | 10.2 |
| **D** | Endpoint `POST /projects/{id}/close` + UI de encerramento + ProjectRetrospective com 4 campos estruturados ausentes | 10.4 |
| **E** | `ScopeChange` precisa de `baseline_from_id`, `baseline_to_id`, `change_type`, `approved_by` para o fluxo de versionamento ficar completo | 10.5 / 9.5 |
| **F** | `Risk` precisa de probability/impact separados + level derivado + mitigation_plan | 4.2.3 / 9.5 |
| **G** | `ActionPlan` precisa de `objective` + `linked_risk_id` + `linked_deliverable_id` | 4.2.4 / 9.5 |
| **H** | `Deliverable` precisa de `acceptance_criteria`, `dependencies`, `status` (e tipo Documento/Software/Serviço/Treinamento, ou racional para `category+complexity` no lugar) | 9.5 |
| **I** | `DeliveryProgress.acceptance_confirmed` precisa persistir o resultado do modal de critério de aceite | 4.2.2 / 9.5 |
| **J** | `PendingItem` precisa de `impact` e `open_date` distinto de `created_at` | 4.2.5 / 9.5 |

### Prioridade 3 — auditoria pendente (preciso ler mais código antes de classificar)

- Linguagem não-técnica do Portal do Cliente: hoje é gerada pelo agente ou só repassa texto do GP? (§4.3)
- Histórico/linha do tempo: existem gráficos de tendência ou só lista de reports? (§4.5)
- Gráficos do dashboard PMO: padrões cruzados entre projetos? (§4.4)
- Status do `Risk` cobre os 4 valores da spec (Identificado/Monitoramento/Mitigado/Materializado)? Vi só `OPEN` no modelo
- Fluxo de aprovação do PMO sobre `ScopeChange` (não só criação automática) (§10.5)
- **Hardening de testes — mock pode mentir matematicamente:** o mock do Playwright F4-1 (`screenshots-f4.spec.ts`) tinha `score` inconsistente com a soma ponderada dos `components`, e nenhum teste pegou — só pegou na auditoria manual. Padrão vai aparecer em outros mocks (portfolio, delivery progress, etc.). Vale uma sessão dedicada de "consistency assertion" — pre-flight que valida invariantes do dado mock antes de gerar PNG.

## Validação prática do agente leitor (F2.8) — adiada para F5

| Item | Estado | Onde |
|---|---|---|
| Smoke real do agente leitor contra `bradesco_sas_databricks.expected.json` | ⏸️ **adiado para F5** | Bloqueado por `claude` headless errático no setup atual (Windows binary via mount WSL). Ver ADR `2026-05-11 — F2.8 adiado...` em `decisoes.md`. |
| Prompt versionado `proposal_reader_v1.md` | 📥 a receber | Preparação útil independente. Vai para `jump-report/docs/prompts/` quando recebido. |
| Schema Pydantic `ProposalExtraction` | ✅ feito | `backend/app/schemas/proposal_extraction.py`. **Nota:** enums (`type`/`category`/`complexity`) divergem da v3.1 §6.4.1 **intencionalmente** — fonte é o prompt `proposal_reader_v1.md`. v3.1 §6.4.1 será atualizada na próxima edição da spec (**v3.2** — débito L). Acid test contra `bradesco_sas_databricks.expected.json` passa. |
| Modo shadow no piloto Bradesco (§1.5) | ✅ já especificado | Extração apresentada como sugestão; baseline só ativado após revisão manual do GP. Mitiga risco de extração não-validada empiricamente. |

## Débitos F5 (atualizados pós-AJUSTE B)

Inclui débitos P2 da auditoria + F2.8 adiado:

- ~~C. Modo de Report Assistido por IA (§10.2)~~ → endereçado em **F5.4** (commits `d90eef5` `5e5d258` `9dc3a65` + commit 4 de encerramento). Cumpre 80% da spec §10.2: herança de Risks/Pendings/DeliveryProgress placeholders, flag `is_prepopulated` com auto-zero ao editar, UI rich com radio modo + badge + modal 409. Sugestões textuais da IA (§10.2 ponto 3) ficam para F5.5/F2.6 — débito F5.4.X. 5 débitos P3 listados abaixo.
- ~~D. Endpoint `POST /projects/{id}/close` + UI + `ProjectRetrospective` com 4 campos estruturados (§10.4)~~ → endereçado em **F5.3** (commits `fe93d50` `4de0188` `93bf7bc` `bf5b97f` + commit 4 de encerramento). Fluxo completo: modelo refatorado, endpoint com cascade de 8 validações Q4, frontend rich com form + Dialog + render read-only, novo `GET /projects/{id}/risks` pra pré-marcar materializados (Q1 híbrida). 3 débitos P3 listados abaixo.
- ~~E. `ScopeChange`: faltam `baseline_from_id`, `baseline_to_id`, `change_type`, `approved_by` (§10.5/9.5)~~ → endereçado em **F5.2** (commits `cd8fc45` modelo+migration, `1b85e09` endpoint+gate, `886b74c` diff MODIFIED + idempotência tripla, `c92b076` frontend, +commit 5 testes+docs). Fluxo end-to-end PMO aprova/rejeita transição completo. 4 débitos P3 listados abaixo.
- ~~F. `Risk`: falta probability/impact separados + `mitigation_plan` (§4.2.3/9.5)~~ → endereçado em **F5.1 ETAPA 2B** (commit `e888415`). RiskStatus reescrito (IDENTIFIED/MONITORING/MITIGATED/MATERIALIZED). 3 débitos menores P3 listados abaixo.
- ~~G. `ActionPlan`: falta `objective`, `linked_risk_id`, `linked_deliverable_id` (§4.2.4/9.5)~~ → endereçado em **F5.1 ActionPlan** (commit `edaec34`). Expansão `linked_*_description/title` em lote no GET.
- ~~H. `Deliverable`: falta `acceptance_criteria`, `dependencies`, `status` (§9.5)~~ → endereçado em **F5.1 Deliverable** (commit `1284bc5`). +4 campos (`type`, `acceptance_criteria`, `dependencies`, `status`), +2 enums realinhados (`complexity` 3→5 PT-BR, `category` String→enum), cross-model auto-update `Deliverable.status=CONCLUDED` quando DeliveryProgress satisfaz as 3 condições.
- ~~I. `DeliveryProgress.acceptance_confirmed` não persiste resultado do modal~~ → endereçado em AJUSTE I no F4.
- ~~J. `PendingItem`: falta `impact` e `open_date` distinto (§4.2.5/9.5)~~ → endereçado em **F5.1 PendingItem** (commit a seguir). `impact` adicionado (Text nullable); `created_at` cumpre `open_date` semanticamente (não duplicamos com campo dedicado).
- ~~**K. F2.8 — smoke real do agente leitor**~~ → **FECHADO em F5.6b (2026-05-14)**. F5.6a entregou worker real + diagnosticou bug `--bare`. F5.6b rodou smoke real contra `bradesco_sas_databricks.expected.json` com prompt versionado `proposal_reader_v1.md` (159s, Claude headless, 1 tentativa, sem fallback). Resultado: **recall ponderado 81.5% → PASS técnico**. Core do baseline em 100% (`phases` 4/4, `deliverables` 21/21); `project` 90.9% (10/11). Discrepâncias em `key_premises`/`out_of_scope` (recall simples 0% e 33%) são artefato do Jaccard de palavras para sinônimos, não defeito do agente — 16 e 17 extras semanticamente válidos. Decisão operacional aprovada por Christopher: **PASS técnico + SHADOW na 1ª semana do piloto** + upgrade condicional para automático após primeira proposta real validada pelo GP. F5.6a.Y (decisão arquitetural sobre onde o `jump-worker` roda) **resolvida: Python venv no WSL Linux via uv (`~/.jump-runner/.venv-worker/`)**. Relatório completo em `docs/f28-bradesco-baseline-quality.md`. Ver ADRs `2026-05-13 — F5.6a / Worker real`, `2026-05-14 — F5.6a / --bare bug`, `2026-05-14 — F5.6b / F2.8 fechado`.
- **L. Atualizar v3.1 §6.4.1 e gerar v3.2 consolidada** (novo): a spec funcional v3.1 §6.4.1 lista enums de `DeliverableType` (Documento/Software/Serviço/Treinamento) e omite `category`/`complexity` que o prompt `proposal_reader_v1.md` realmente usa. Implementação seguiu o prompt (fonte). Próxima edição da spec consolida vocabulário do prompt + adiciona seção sobre `confidence_score`/`confidence_notes`. Mantém a regra de "toda nova versão começa com diff explícito do que foi alterado" (ADR 2026-05-08 — Governança).

### Débitos menores de F5.1 (P3 — escolhidos conscientemente)

- **F5.1.a — `open_critical` calculado em Python, não SQL.** `Risk.level` é property derivada (não coluna), então `app/api/v1/portfolio.py:open_critical` faz `sum(1 for r in rows if r.level == RiskLevel.CRITICAL)`. Aceitável para o piloto Bradesco (~5-10 riscos por report). Vai aparecer com 50+ projetos. **Alternativa:** GENERATED COLUMN `level` no Postgres com índice — torna filtro SQL e mantém matriz como fonte da verdade via trigger/view.
- **F5.1.b — `Severity` (frontend) vs `RiskLevel` (backend) coexistem.** Mesmos 4 valores `low/medium/high/critical`, dois nomes em camadas diferentes. Frontend mantém `Severity` exclusivamente para `AIInsight.payload.severity` (campo livre dentro de JSON, sem relação com Risk). Unificar nomenclatura em ciclo posterior.
- **F5.1.c — Vitest não renderiza shadcn `<TabsContent>` em jsdom isolado.** Tentativa de criar `tests/report-edit-risks.test.tsx` em F5.1 falhou: clique no `<TabsTrigger>` não troca o painel ativo. Cobertura visual via Playwright compensou. **Alternativa:** `userEvent` async + `findByRole`, ou mock de `@radix-ui/react-tabs`. Item de hardening de testes — vale uma sessão dedicada quando outros formulários do wizard precisarem de teste isolado.

### Débitos menores de F5.2 (P3 — escolhidos conscientemente)

- **F5.2.a — Convenção SAEnum sem `values_callable` persiste `e.name` (UPPERCASE).** Descoberta empírica em F5.2 commit 1 quando o backfill da migration 0014 inseriu `change_type='added'` (lowercase) e ORM falhou ao ler. Aplica-se a TODOS os enums do projeto (`BaselineStatus`, `ScopeChangeStatus`, `ScopeChangeType`, `RiskStatus`, `DeliverableStatus`, etc.). Documentado em `docs/dev_notes.md` "Convenções de enum no projeto" + ADR em `decisoes.md`. Toda migration futura que mexer com SQL literal em coluna de enum deve usar NAMES uppercase. Item de governança, não bug. **Alternativa:** introduzir `values_callable=lambda x: [e.value for e in x]` em todos os SAEnum — quebraria os dados existentes; não vale.
- **F5.2.b — Testes de migration usam `importlib`, não `alembic upgrade` real.** `backend/tests/test_migration_0014_*` e `test_migration_0015_*` carregam o módulo da migration via `importlib.util.spec_from_file_location` e chamam `run_backfill(conn)` direto. Razão: `conftest.py` usa `Base.metadata.create_all` (SQLite in-memory), não roda Alembic. Garante que o **SQL do backfill** está correto, mas **não** garante que `upgrade()` (add_column, etc.) funciona — isso só é exercido na CI/produção contra Postgres real. **Hardening em F5.X ou F6:** fixture Alembic em SQLite ou Postgres ephemeral em CI.
- **F5.2.c — Remover coluna `impact_baseline_id` de `ScopeChange`.** Campo legacy do F4.3; substituído por `baseline_to_id` em F5.2 commit 1. Backfill da 0014 já copiou os valores; código novo não escreve nele. Marcado como `DEPRECATED` no modelo. **Plano:** migration de remoção em ciclo posterior (F6 ou hardening), após confirmar zero leitura em código novo. Custo de manter: 1 coluna nullable a mais (~bytes desprezíveis); benefício de remover: schema mais limpo. Não bloqueia ninguém.
- ~~**F5.2.d — `pytest-cov` subreporta cobertura de funções async.**~~ → **resolvido em F5.3 commit 1.** Criado `backend/.coveragerc` com `concurrency = thread,greenlet`. Números reais pós-config (rodando pytest do CWD `backend/`): `portfolio.py` 47% → **77%**, `scope_changes.py` 50% → **86%**. Total dos 2: 48% → 80%. Cobertura comportamental sempre existiu (testes verdes); o número raw estava subreportado por falta de instrumentação do trace dentro de event loop asyncio.

### Débitos menores de F5.3 (P3 — escolhidos conscientemente)

- **F5.3.a — Testes para paths defensivos.** `portfolio.py:97-116` (projeto sem `last_report_id` no `portfolio_overview`) e `scope_changes.py:51,60,98,101,103` (handlers 404/403 raros nos GETs do scope-changes) permanecem sem cobertura explícita após o `.coveragerc` do commit 1 do F5.3. Cobertura comportamental existe via paths normais; gaps são branches de exceção. **Hardening em F5.X ou F6:** testes específicos cobrindo cada handler defensivo. Não bloqueia ninguém.
- **F5.3.b — Documentar CWD do pytest para `.coveragerc`.** Comando `pytest --cov` precisa rodar de `backend/` (não do path absoluto) para o `.coveragerc` ser lido. Documentado em `docs/dev_notes.md` seção "Testes que tocam o banco usam SQLite". Possível complemento: criar `backend/Makefile` com alvo `test-cov` que executa `cd backend && pytest --cov` automaticamente. **Hardening em F6:** Makefile com targets comuns.
- ~~**F5.3.c — `GET /projects/{id}/risks` sem teste pytest específico**~~ → **resolvido em F5.3 commit 4.** 7 testes novos cobrindo happy path multi-status, filtros (identified/materialized), invalid status (422), projeto inexistente (404), role matrix (GP-dono/GP-outro/PMO/CLIENT-dono/CLIENT-outsider), ordering por `created_at DESC`. Cobertura `projects.py`: 82% → **91%** (≥90% ✅).
- **F5.3.d — Playwright PNGs do F5.3 pendentes.** Specs `screenshots-f53.spec.ts` versionados e prontos (2 cenários: form de encerramento + projeto CLOSED com retrospectiva). Geração falha localmente com `net::ERR_ABORTED` no Next dev server — mesmo problema do F5.2 (firewall/AV Windows local, não específico desses specs). Regeneração quando ambiente clean — 1-2 minutos. Mesmo débito P3 do F5.2 (não bloqueia release).

### Débitos menores de F5.4 (P3 — escolhidos conscientemente)

- **F5.4.W — Match-by-description para preservar `is_prepopulated` em PATCH /reports.** Contexto: `PATCH /reports/{id}` faz `delete+insert` nas listas filhas; preservação de `is_prepopulated` entre ciclos depende de matching item antigo com item novo. Implementação atual usa `description` como chave natural para Risk e PendingItem (DeliveryProgress usa `deliverable_id`, UNIQUE no banco — sem problema). **Consequência:** editar `description` de Risk/PendingItem pré-populado sem mudar outros campos resulta em `is_prepopulated=False` (match falha, item virtualmente recriado). **Avaliação:** aceitável no MVP — editar description sem outras mudanças é raro, e perder a flag nesse caso é semanticamente defensável (GP editou algo, então não é mais "puramente do anterior"). **Refactor:** upsert por ID em PATCH /reports em ciclo de hardening futuro. Custo médio: muda padrão de delete+insert em ~6 endpoints.
- **F5.4.X — Sugestões textuais da IA pendentes.** Spec v3.1 §10.2 ponto 3: "Sugestões geradas pelo agente como placeholders ('Na semana passada o risco X estava em monitoramento. Ainda está ativo?')". Decisão F5.4 (Q3 = c): pular no MVP. Stub atual (`report_analyzer_stub`) gera heurísticas pós-submit; prompts conversacionais pre-criação exigem agente real (LLM). **Depende de F5.5 (Agente de Inteligência Cruzada)** ou **F2.6 (worker real)**, ambos pendentes.
- **F5.4.Y — Botão "Criar plano de ação vinculado" ao lado de Risk herdado.** Nuance do briefing Q5 (ActionPlan não herda mas UI pode facilitar criação manual). Não implementado no Commit 3 — escopo creep. Enhancement de UX, baixa prioridade. Fica em F5.X ou hardening futuro.
- **F5.4.Z — Limitação Vitest em Tabs do Radix.** Mesmo débito F5.1.c: `<TabsContent>` inativos não renderizam em jsdom. Cobertura visual do badge "Do report anterior" em Risk/PendingItem (que ficam em tabs não-default) feita apenas via shape test no commit 3 + Playwright spec no commit 4 (PNG pendente — vide débito abaixo). Sem fix conhecido — `userEvent` async ou mock de `@radix-ui/react-tabs` em sessão de hardening dedicada.
- **F5.4 PNGs Playwright pendentes.** Specs `screenshots-f54.spec.ts` versionados (3 cenários: form com radio, wizard com badge, modal 409 com link). Geração falha localmente com `net::ERR_ABORTED` — mesmo ambiente F5.2/F5.3 (firewall/AV Windows). Regeneração em ambiente clean = 1-2 minutos.

### Débitos menores de F5.6a (P3 — escolhidos conscientemente)

- **F5.6a.X — Verificação preventiva da URL do codex installer no `setup-windows.ps1`.** Hoje o script faz `curl -fsSL https://codex.openai.com/install.sh | sh` direto. Se a OpenAI mover o endpoint (precedente: alguns instaladores de CLIs já mudaram URL), Chris só descobre depois de ~5-10 min de execução chegar no passo 3.7. **Sugestão:** antes do `curl ... | sh`, fazer `curl -I -fsS https://codex.openai.com/install.sh` (HEAD request) para confirmar 200 — aborta com mensagem clara apontando "Plano B 1/2/3" do runbook se 404. Custo: 5 linhas. Não bloqueia ninguém porque o script já é idempotente e o runbook documenta as 3 alternativas, mas economiza 10 min de loop falho. **Refactor:** F5.6b ou hardening F6.

### Débitos menores de F5.6 (P3 — escolhidos conscientemente, fecharão em F5.6b)

- **F5.6a.Y — Onde o `jump-worker` roda (decisão de arquitetura adiada para F5.6b).** `ClaudeHeadlessRoute` usa `resolve_executable("claude")` do PATH do processo Python. Hoje, se o jump-worker rodar no Windows host (caminho previsto pelo `start-worker.ps1`), ele resolve para o claude do mount Windows — bug do ADR 2026-05-11 ressurge. Opções candidatas: (a) rodar o próprio jump-worker dentro do WSL Linux com claude nativo no PATH (Python via venv Linux); (b) introduzir wrapper executável em `ClaudeHeadlessRoute` que invoca `wsl.exe -d Ubuntu-22.04 -- claude ...` quando o host é Windows. Ambas têm trade-offs. Testes F5.6a mockam `AgentRunner` integralmente — decisão não bloqueia F5.6a; smoke F5.6b força a escolha.

---

## O que muda no plano

- Os AJUSTES 1 e 2 da conversa anterior continuam pertinentes, agora apontando para `spec_consolidada_v3.1.md §10.1` e `§10.3` (não mais a v3 que omitia essas prescrições).
- O AJUSTE 3 (terceiro botão UI + flag) é a implementação concreta do desvio **A**.
- O desvio **B** virou trabalho maior do que `(a)` da pergunta original — não é só voltar para 5 pesos, é mudar 3 dos 5 componentes da fórmula.
- Débito de F5 (C-J) deve ser registrado em backlog explícito, não disperso em comentários.
