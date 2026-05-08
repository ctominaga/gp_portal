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
| `DataProcessingRecord` | id, subject_*, processing_purpose, legal_basis, retention_period | existe (`domain.py:600`); não auditei campos | ✅ presumido |

## Seção 10 — Melhorias do Processo Incorporadas

| Item | v3.1 § | Implementação | Conformidade |
|---|---|---|---|
| **Fluxo de aprovação em 3 estágios** (Aprovar direto / Aprovar com comentário / Devolver para revisão) | 10.1 | Backend: 1 endpoint `POST /reports/{id}/decide` com decision ∈ {approved/rejected/requested_changes}. Frontend PMO (`pmo/reports/[rid]/review`): 2 botões ("Pedir revisão", "Aprovar"). **Falta** terceiro caminho explícito; falta valor `approved_with_comment` no enum; modal não comunica que o comentário é nota interna | ⚠️⚠️ |
| **Modo de Report Assistido por IA** (pré-popula riscos do report anterior, sugestões do agente) | 10.2 | Busca por `prepopulate`, `previous_report` etc. zera. **Não implementado** | ❌ |
| **Health Score com 5 componentes** (RAG médio 0.35 + SPI 0.25 + Risco_inv 0.20 + Resolução 0.10 + Estabilidade 0.10) | 10.3 | `health_score.py` tem **4 componentes** (progress, risks, pendings, schedule) com fórmula divergente. **Faltam**: Status RAG médio (não usa o RAG das dimensões), SPI (usa % done bruto, não real÷planejado), Estabilidade (não computado). Pesos defaults discretos em 4 colunas, não 5 com defaults 35/25/20/10/10 | ⚠️⚠️⚠️ |
| Pesos do Health Score editáveis pelo PMO | 10.3 | Tela `/pmo/portfolio/config` permite editar 4 pesos | ✅ (estrutura existe; precisa adaptar para 5) |
| Faixas de classificação (≥70 verde, 40-69 âmbar, <40 vermelho) | 10.3 | `_band()` em `health_score.py`: 70/40 — **conforme** | ✅ |
| **Retrospectiva ao encerrar projeto** (POST /projects/{id}/close + 4 campos estruturados) | 10.4 | Modelo `ProjectRetrospective` existe mas com schema divergente (lessons_learned + kpis JSON). **Sem endpoint `/close`**. Sem UI de encerramento | ⚠️⚠️ |
| **Versionamento de escopo** (upload v2 → diff vs v1 → ScopeChange por item → aprovação) | 10.5 | `client_portal.py:diff_baselines` cria ScopeChange por added/removed (idempotente). Modelo `ScopeChange` divergente (sem baseline_from_id/to, change_type, approved_by). Fluxo de aprovação PMO desse diff não auditado | ⚠️ |
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

---

## O que muda no plano

- Os AJUSTES 1 e 2 da conversa anterior continuam pertinentes, agora apontando para `spec_consolidada_v3.1.md §10.1` e `§10.3` (não mais a v3 que omitia essas prescrições).
- O AJUSTE 3 (terceiro botão UI + flag) é a implementação concreta do desvio **A**.
- O desvio **B** virou trabalho maior do que `(a)` da pergunta original — não é só voltar para 5 pesos, é mudar 3 dos 5 componentes da fórmula.
- Débito de F5 (C-J) deve ser registrado em backlog explícito, não disperso em comentários.
