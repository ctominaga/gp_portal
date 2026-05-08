# Especificação Funcional Consolidada — Sistema de Report e Gestão Estratégica de Projetos

**Versão:** 3.1 — Consolidação das prescrições funcionais (v2.0/v2.1) com arquitetura híbrida (v3.0)
**Data:** Maio 2026
**Status:** Aprovado para construção. Substitui v2.0, v2.1 e v3.0.
**Produto:** Interno da Jump Label
**Piloto:** Bradesco — Migração SAS → Databricks (em andamento)

---

## Nota sobre histórico de versões

Esta versão consolida três documentos anteriores em uma fonte única de verdade:

- **v2.0** (Maio 2026) — primeira spec aprovada, com prescrições funcionais detalhadas
- **v2.1** (Maio 2026) — ajustes de provider de LLM (Gemini removido) e custos. Era um delta da v2.0.
- **v3.0** (Maio 2026) — substituição da camada de API LLM por `jump-agent-runner` invocando Claude Code e Codex CLI; arquitetura híbrida Railway + máquina Windows local.

A v3.0 foi escrita como delta da v2.1, omitindo prescrições funcionais que permaneciam válidas. Isso gerou ambiguidade quando a implementação prosseguiu sem acesso à v2.1. Esta v3.1 elimina a ambiguidade ao incorporar **todas** as prescrições funcionais explicitamente, marcando origem quando relevante.

**Lições registradas (vão para `docs/decisoes.md`):**
- Toda nova versão de spec deve ser autossuficiente, não delta
- Toda nova versão deve começar com diff explícito do que foi alterado/removido em relação à anterior
- Versões anteriores são preservadas em `docs/spec_history/` como referência histórica

---

## Sumário

1. Visão Geral e Caso de Negócio
2. Arquitetura Geral (Híbrida)
3. Perfis de Acesso
4. Módulos Funcionais
5. Fluxo Principal do Sistema
6. Camada de Inteligência via `jump-agent-runner`
7. Indicadores e Estrutura do Report
8. Visões por Perfil
9. Arquitetura Técnica Detalhada
10. Melhorias do Processo Incorporadas (fluxo aprovação, Health Score, retrospectiva, versionamento, modo assistido)
11. Implicações Operacionais e Mitigações
12. LGPD e Governança de Dados
13. Plano de Implementação em Fases
14. Métricas e Riscos

---

## 1. Visão Geral e Caso de Negócio

### 1.1. Objetivo

Centralizar e padronizar o acompanhamento de projetos de consultoria da Jump Label através de uma plataforma executiva orientada por dados. O Gerente de Projetos (GP) alimenta as informações-chave de forma estruturada, e o sistema as transforma em visões estratégicas para cada perfil de usuário.

### 1.2. Pilares de inteligência

- **Ancoragem na Proposta.** Um agente lê as propostas comerciais e transforma seu conteúdo em baseline de escopo, prazo e entregas.
- **Inteligência Cruzada entre Projetos.** O sistema acumula dados históricos e cruza informações de múltiplos projetos.

### 1.3. Caso de negócio

| Premissa | Valor |
|---|---|
| Tempo economizado por GP por mês | 8 horas |
| Tempo economizado por projeto | 8 horas |
| Volume estimado em 12 meses | 30 projetos × 3 meses |
| Total de horas economizadas | 960 horas |
| Valor-hora de referência | R$ 100,00 |
| **Economia direta projetada** | **R$ 96.000,00 / ano** |

**Métrica adicional não-financeira:** escopo recuperado por projeto via detecção automática de desvio. Em projetos de grande porte (Bradesco), um único entregável recuperado pode representar valor superior à economia anual de tempo. Reportada separadamente.

**Custo dos modelos:** zero por chamada (assinaturas Claude e ChatGPT já contratadas pela Jump). Custo fixo das assinaturas é tratado como custo do produto e documentado separadamente.

### 1.4. Problema que o sistema resolve

| Dor atual | Como o sistema resolve |
|---|---|
| Relatórios manuais e sem padrão | Template estruturado com preenchimento guiado |
| Desvio de escopo não percebido | Baseline extraído automaticamente da proposta |
| PMO sem visão consolidada | Dashboard centralizado de todos os projetos |
| Cliente sem visibilidade clara | Portal executivo com linguagem não técnica |
| Nenhum aprendizado com projetos passados | Agente de IA que cruza dados históricos |
| Riscos identificados tarde demais | Alertas proativos baseados em padrões |

### 1.5. Piloto

Primeiro projeto cadastrado: **Bradesco — Migração SAS → Databricks**, em andamento. Operará em modo *shadow* na fase do agente leitor: extração automática é apresentada como sugestão; baseline só é ativado após revisão manual do GP.

---

## 2. Arquitetura Geral (Híbrida)

A solução opera em dois ambientes interligados:

```
┌─────────────────────────────────────┐         ┌──────────────────────────────────────┐
│      RAILWAY (cloud, 24/7)          │         │     MÁQUINA WINDOWS (Jump)           │
│                                     │         │                                      │
│  - Frontend Next.js                 │         │  jump-agent-runner                   │
│  - Backend FastAPI                  │  ◄──►   │  - Worker que puxa jobs da fila      │
│  - PostgreSQL                       │  jobs   │  - WSL2 + tmux + sessões persistent. │
│  - Redis (broker da fila)           │  via    │  - claude (-p) / claude broker       │
│  - Acesso de GPs, PMO, Cliente      │  Redis  │  - codex (exec) / codex broker       │
│                                     │         │  - Browser para login interativo     │
└─────────────────────────────────────┘         └──────────────────────────────────────┘
        Internet pública                              Atrás de NAT/firewall corporativo
```

**Por que essa divisão:**
- **Railway** carrega cargas que precisam de disponibilidade 24/7 e acesso via internet (UI dos usuários).
- **Máquina Windows local** carrega cargas de IA, aproveitando assinaturas Claude/ChatGPT já contratadas pela Jump.

**Comunicação:** worker **puxa** jobs de fila Redis no Railway; resultado é publicado via HTTP autenticado por token + HMAC.

---

## 3. Perfis de Acesso

| Perfil | Localização | Permissões principais |
|---|---|---|
| **Gerente de Projetos (GP)** | Acessa via Railway | Cria/configura projetos, faz upload de propostas, registra reports |
| **Gerente do PMO** | Acessa via Railway | Visão consolidada do portfólio, aprova reports antes do cliente, configura templates |
| **Cliente** | Acessa via Railway | Vê apenas seu próprio projeto, com conteúdo curado e aprovado |
| **Operador da máquina worker** | Acessa máquina Windows | Mantém sessões logadas, monitora workers, atende pedidos de re-login |

---

## 4. Módulos Funcionais

### 4.1. Módulo de Onboarding do Projeto

Ponto de entrada de todo novo projeto. Captura informações fundacionais e aciona o agente leitor de propostas.

**Fluxo de cadastro:**
1. GP preenche dados básicos: nome, cliente, GP responsável, data de início, data prevista de término
2. GP faz upload da proposta comercial (PDF, DOCX ou texto)
3. Agente Leitor processa a proposta e extrai o baseline
4. GP revisa e valida o baseline extraído
5. Projeto é ativado e começa o ciclo de reports

**Dados de configuração do projeto:**
- Identificação: nome, código, cliente, contrato
- Equipe: GP responsável, recursos alocados
- Datas: início, término previsto, marcos principais
- Baseline do escopo (extraído da proposta + revisão do GP)
- Orçamento previsto (se disponível na proposta)
- Periodicidade dos reports (semanal / quinzenal / mensal)

### 4.2. Módulo de Report Periódico

Núcleo operacional. É onde o GP registra o que está acontecendo no projeto com a periodicidade configurada.

#### 4.2.1. Status Geral (RAG)

Avaliação sintética da saúde do projeto no período em **três dimensões independentes**:

| Dimensão | Descrição |
|---|---|
| Prazo | O projeto está dentro do cronograma previsto? |
| Escopo | As entregas estão alinhadas ao que foi proposto? |
| Qualidade | O nível de qualidade das entregas está adequado? |

Cada dimensão recebe cor (Verde/Amarelo/Vermelho) com **justificativa obrigatória** quando Amarelo ou Vermelho. O sistema deriva automaticamente o status agregado do report como **worst-of-3** (a pior das três dimensões).

#### 4.2.2. Progresso das Entregas

Lista de entregas previstas no baseline (extraído da proposta), com:
- Atualização do percentual de conclusão
- Data revisada de entrega quando aplicável (campo dedicado, não texto livre)
- Sistema marca `deviation_flag=true` quando data revisada ≠ planejada
- Quando GP marca status "Concluído" + 100%, sistema exige confirmação de critério de aceite via modal

#### 4.2.3. Riscos

| Campo | Descrição |
|---|---|
| Descrição do risco | O que pode acontecer |
| Probabilidade | Alta / Média / Baixa |
| Impacto | Alto / Médio / Baixo |
| Nível geral | Calculado automaticamente (prob × impacto) |
| Status | Identificado / Em monitoramento / Mitigado / Materializado |
| Plano de mitigação | O que será feito para evitar ou reduzir |
| Responsável | Quem cuida desse risco |

#### 4.2.4. Planos de Ação

| Campo | Descrição |
|---|---|
| Ação | O que será feito |
| Objetivo | Por que essa ação foi criada |
| Responsável | Quem executa |
| Prazo | Quando deve ser concluída |
| Status | A fazer / Em andamento / Concluída / Cancelada |
| Vinculação | Risco ou entrega relacionada (opcional) |

#### 4.2.5. Atividades Pendentes

| Campo | Descrição |
|---|---|
| Descrição | O que está pendente |
| Responsável | Interno ou cliente |
| Data de abertura | Quando foi registrado |
| Data limite | Quando precisa ser resolvido |
| Status | Aberto / Resolvido |
| Impacto no projeto | Se não resolvido, o que afeta |

#### 4.2.6. Destaques do Período

Campo livre (mas guiado por prompts) para o GP registrar conquistas, decisões, aprendizados, contexto adicional.

#### 4.2.7. Próximos Passos

Lista das principais entregas e marcos previstos para o próximo período.

### 4.3. Módulo de Visão Executiva (Cliente)

Visão curada e de linguagem acessível **gerada automaticamente a partir do report do GP, com aprovação do PMO antes de ser liberada**. A linguagem não-técnica é responsabilidade do agente de análise (não regex/template).

**Conteúdo:**
- Semáforo de saúde do projeto (prazo, escopo, qualidade)
- Progresso visual das entregas (barra de progresso por entrega)
- Riscos relevantes em linguagem não técnica
- Planos de ação em andamento
- Pendências que envolvem o cliente
- Próximos marcos e datas
- Linha do tempo simplificada
- Botão "Confirmar leitura" do report

### 4.4. Módulo de Dashboard do PMO

**Painel de portfólio:**
- Lista de todos os projetos com status RAG atualizado
- Health Score visível em cada card (gauge proeminente, não número pequeno)
- Alertas de projetos em vermelho ou com riscos críticos
- Métricas agregadas: projetos no prazo, com risco alto, com pendências críticas
- Comparativo entre projetos: padrões de desvio, tipos de risco mais comuns

**Drill-down por projeto:**
- Acesso ao report completo de qualquer projeto
- Histórico completo de todos os reports
- Análise de tendência gerada pelo agente de IA

### 4.5. Módulo de Histórico e Linha do Tempo

Todo report é armazenado e versionado.

**Funcionalidades:**
- Histórico navegável de todos os reports
- Gráfico de evolução do status RAG ao longo do tempo
- Gráfico de evolução do progresso das entregas
- Evolução do número de riscos abertos e mitigados
- Registro de mudanças no escopo (desvios documentados)

---

## 5. Fluxo Principal do Sistema

```
┌──────────────────────────────────────────────────────────────────┐
│                       USUÁRIO (GP, PMO, Cliente)                 │
│                  acessa frontend hospedado em Railway             │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  FRONTEND Next.js (Railway)                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │ REST + SSE
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  BACKEND FastAPI (Railway)                       │
│                                                                  │
│  Operações síncronas (CRUD, login, dashboards) → resposta direta │
│  Operações de IA (extração, análise) → enfileiram em Redis       │
│                                                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
                      ┌────────────────┐
                      │   Redis Queue  │   (Railway gerencia)
                      │  (jobs.agent)  │
                      └────────┬───────┘
                               │ worker pulls
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              MÁQUINA WORKER WINDOWS (Jump, on-prem)              │
│                                                                  │
│  jump-agent-runner-worker invoca AgentRunner que executa         │
│  Claude/Codex via WSL+tmux, recebe artefato JSON canônico,       │
│  publica resultado via HTTP autenticado no backend               │
└──────────────────────────────┬───────────────────────────────────┘
                               │ resultado
                               ▼
                  Backend persiste e notifica
                  o usuário (SSE + email)
```

### 5.1. Fluxo Detalhado do Report

```
GP recebe notificação de report
       │
       ▼
Acessa a plataforma e abre novo report
       │
       ▼
Preenche Status Geral (RAG por dimensão: prazo, escopo, qualidade)
       │
       ▼
Atualiza progresso das entregas
       └─ Se desvio de prazo ou escopo → sistema registra e alerta
       │
       ▼
Atualiza riscos / planos de ação / atividades pendentes
       │
       ▼
Registra destaques e próximos passos
       │
       ▼
Submete report
       │
       ├─────────────────────────────────────────────────┐
       ▼                                                 ▼
Agente de IA analisa o report          Report entra em fila
e gera insights e alertas              para revisão do PMO
       │                                                 │
       ▼                                                 ▼
GP recebe sugestões                     PMO toma uma das 3
e alertas proativos                     decisões (seção 10.1)
```

---

## 6. Camada de Inteligência via `jump-agent-runner`

Especificação técnica completa em `docs/02_jump_agent_runner_spec.md`.

### 6.1. Resumo da arquitetura

```
Backend FastAPI ──[job na fila Redis]──► Worker Windows
                                                │
                                                ▼
                                         AgentRunner
                                                │
                              ┌─────────────────┴─────────────────┐
                              ▼                                   ▼
                       ClaudeProvider                      CodexProvider
                       (engine primário                    (engine fallback)
                       quando configurado)                 headless → broker
                       headless → broker                   
                              │                                   │
                              └─────────────┬─────────────────────┘
                                            ▼
                                     ArtifactValidator
                                  (JSON em output_path
                                   é a única fonte da verdade)
```

### 6.2. Política de fallback

- **Primeiro:** rota headless do engine primário
- **Se falhar** por login, quota, modo interativo, timeout sem artefato ou erro: rota broker do mesmo engine
- **Se broker falhar** sem produzir sentinel/artefato: engine secundário (mesma sequência)
- **API Key nunca é sugerida em nenhum nível** — não é parte da política

### 6.3. Tarefas dos agentes

| Agente | Engine primário | Fallback | Justificativa |
|---|---|---|---|
| **Leitor de Propostas** | Claude | Codex | Tende a produzir JSON estruturado mais consistente |
| **Análise e Alertas** | Claude | Codex | Tarefa de análise e síntese |
| **Inteligência Cruzada** | Claude | Codex | Idem |

Atribuições são configuráveis via `agent_runner_config.toml`.

### 6.4. Os três agentes do produto

#### 6.4.1. Agente Leitor de Propostas

**Objetivo:** ler proposta comercial e extrair entregáveis estruturados que viram baseline do projeto.

**Output estruturado por entregável:**

| Campo | Descrição |
|---|---|
| ID | Identificador único (ex: ENT-001 ou d-001) |
| Nome | Nome curto |
| Descrição | O que está sendo entregue, conforme proposta |
| Fase | Em qual fase do projeto pertence |
| Tipo | Documento / Software / Serviço / Treinamento |
| Data prevista | Prazo extraído da proposta |
| Critério de aceite | Como saber que está concluído |
| Dependências | Outros entregáveis que precisam ser concluídos antes |
| Origem na proposta | Trecho exato extraído (`source_excerpt`) |
| Status inicial | Sempre começa como "Não iniciado" |

**Tela de revisão pelo GP:**
- `source_excerpt` mostrado **expandido por padrão** ao lado de cada entregável
- Sub-cabeçalho de auditoria: "Extraído de {proposta} em {data} via {engine}/{rota} · confiança {score}%"
- Quando confiança < 70%, sistema exibe aviso visual proeminente
- Botão "Ativar baseline" exige confirmação modal explicando que ativação é ponto sem volta

#### 6.4.2. Agente de Análise e Alertas

**Objetivo:** analisar cada report submetido e gerar insights proativos.

**Inputs:** report atual + 3 reports anteriores do mesmo projeto + baseline ativo.

**Output:** lista de insights classificados por prioridade (high/medium/low).

**Exemplos:**
- "O prazo das entregas tem sido revisado nos últimos 3 reports consecutivos."
- "Há 2 pendências abertas há mais de 30 dias envolvendo o cliente."
- "O risco X aumentou de probabilidade Baixa para Alta."

#### 6.4.3. Agente de Inteligência Cruzada (Portfólio)

**Objetivo:** aprender com o histórico de todos os projetos e antecipar padrões.

**Disparo:** task agendada (diária via Celery Beat) que processa projetos com mais de 3 reports.

**Saída:** observações de portfólio com flag de maturidade. Com base de dados pequena (< 10 projetos encerrados), apresentadas como "Padrões observados — sujeitos a confirmação", **não como predições**. Conforme o volume cresce, transição para correlações com confiança estatística.

### 6.5. AgentRunLog (substitui LLMCallLog)

Toda execução é registrada em `AgentRunLog`:

| Campo | Descrição |
|---|---|
| `run_id` | ID único, usado também como sentinel `AGENT_DONE:<run_id>` |
| `task_type` | `proposal_extraction`, `report_analysis`, `portfolio_pattern`, etc |
| `engine_used` | `claude` ou `codex` |
| `route_used` | `headless` ou `broker` |
| `attempts` | JSONB com tentativas (engine, rota, sucesso, motivo de falha) |
| `duration_s` | Tempo total |
| `worker_id` | Qual máquina worker processou |
| `artifact_path` | Caminho do JSON aceito |
| `failover_occurred` | Booleano: true se houve mudança de engine |
| `created_at`, `started_at`, `completed_at` | Timestamps |

Permite ao PMO ver: distribuição Claude vs Codex, tempo médio, taxa de fallback.

---

## 7. Indicadores e Estrutura do Report

### 7.1. KPIs do Projeto

| Indicador | Definição | Fonte |
|---|---|---|
| SPI — Schedule Performance Index | Percentual de progresso real vs. planejado | Entregas do report |
| CPI — Cost Performance Index | Custo realizado vs. orçamento (se disponível) | Campo opcional |
| Risco Geral | Nível médio ponderado dos riscos abertos | Módulo de riscos |
| Taxa de Resolução de Pendências | Pendências fechadas / abertas no período | Módulo de atividades |
| Desvio de Escopo Acumulado | % de entregas com prazo ou conteúdo revisado | Comparação com baseline |
| Estabilidade do Status RAG | Quantos reports consecutivos no mesmo status | Histórico de reports |

### 7.2. Campos Obrigatórios vs. Opcionais por Report

| Campo | Obrigatoriedade |
|---|---|
| Status RAG por dimensão (prazo, escopo, qualidade) | Obrigatório |
| Justificativa por dimensão | Obrigatório se Amarelo ou Vermelho |
| Atualização de progresso das entregas | Obrigatório |
| Revisão de riscos existentes | Obrigatório |
| Atualização de planos de ação existentes | Obrigatório |
| Destaques do período | Obrigatório |
| Próximos passos | Obrigatório |
| Novos riscos / planos / pendências | Opcional |
| Atualização de orçamento | Opcional |

---

## 8. Visões por Perfil

### 8.1. Visão do GP
- Dashboard do projeto com todos os KPIs
- Formulário de report guiado
- Alertas e sugestões do agente de IA
- Histórico completo de reports do projeto
- Linha do tempo de evolução dos indicadores
- Status das pendências com o cliente

### 8.2. Visão do PMO
- Dashboard de portfólio: semáforo de todos os projetos com Health Score visível
- Fila de reports aguardando aprovação
- Alertas críticos consolidados
- Análise de padrões cruzados pelo agente de IA
- Drill-down em qualquer projeto
- Tela de configuração de pesos do Health Score
- Relatórios gerenciais do portfólio (exportável)
- Configurações de templates e critérios

### 8.3. Visão do Cliente
- Status visual do projeto (semáforo simples)
- Health Score do projeto
- Progresso das entregas em linguagem não técnica
- Próximos marcos e datas
- Riscos relevantes explicados de forma acessível
- Pendências que dependem do cliente em destaque
- Histórico de reports aprovados
- Possibilidade de confirmar leitura do report

**Importante:** o Portal do Cliente é deliberadamente **mais simples** que o Dashboard do GP. Sem filtros, sem drill-down, sem operações de edição. Se uma tela do cliente parece complicada, está errada.

---

## 9. Arquitetura Técnica Detalhada

### 9.1. Componentes Railway

| Serviço | Tecnologia | Função |
|---|---|---|
| `frontend` | Next.js 14 + TypeScript + shadcn/ui | UI dos perfis de usuário |
| `backend` | Python 3.12 + FastAPI + Pydantic v2 | API REST, autenticação, fluxo de aprovação |
| `postgres` | PostgreSQL 16 (Railway managed) | Persistência |
| `redis` | Redis (Railway managed) | Fila de jobs + cache |
| `notifications` | Resend (SMTP) + SSE no backend | Notificações |

### 9.2. Componentes da máquina Worker

| Serviço | Tecnologia | Função |
|---|---|---|
| `jump-agent-runner` | Python 3.12 + asyncio | Biblioteca de execução de agentes |
| `worker` | Python | Puxa jobs e invoca o runner |
| `WSL2 + Ubuntu` | Microsoft + Canonical | Ambiente Linux para tmux e CLIs |
| `tmux` | apt | Sessões persistentes `project-claude` e `project-codex` |
| `claude` CLI | npm `@anthropic-ai/claude-code` | Engine Claude |
| `codex` CLI | install.sh | Engine Codex |

### 9.3. Comunicação Railway ↔ Worker

**Direção: Worker → Railway (sempre)**
- Worker conecta ao Redis do Railway via TLS, autenticado por senha
- Worker faz HTTP POST de resultados em endpoint interno autenticado com:
  - Token compartilhado (`WORKER_SHARED_SECRET`) no header
  - Assinatura HMAC-SHA256 do payload com chave `WORKER_HMAC_KEY`
  - Timestamp para evitar replay (janela de 5 minutos)

**Direção: Railway → Worker (nunca)** — backend nunca abre conexão TCP para a máquina worker.

### 9.4. Modelo de fila

Fila Redis: `jobs.agent`. Estrutura do job:

```json
{
  "run_id": "ext-prop-2026-05-06-001",
  "task_type": "proposal_extraction",
  "engine_primary": "claude",
  "engine_fallback": "codex",
  "input": { "file_url": "...", "file_sha256": "...", "project_id": "...", "language": "pt-BR" },
  "output_schema_url": "https://.../schemas/proposal_extraction.json",
  "result_callback_url": "https://api.../internal/agent-results/...",
  "result_callback_token": "...",
  "timeout_hard_s": 600,
  "heartbeat_s": 30,
  "enqueued_at": "...",
  "ttl_s": 14400
}
```

**Idempotência:** `run_id` é a chave. Reentregas não geram processamento duplicado.
**TTL:** 4h para descarte automático com notificação ao PMO.
**Dead-letter:** após 3 falhas consecutivas no mesmo `run_id`, vai para `jobs.agent.dead`.

### 9.5. Modelo de dados (entidades principais)

| Entidade | Campos Principais |
|---|---|
| `User` | id, name, email, password_hash, role (GP/PMO/CLIENT/OPERATOR), created_at |
| `Project` | id, name, code, client_id, gp_id, status, start_date, end_date, periodicity |
| `Proposal` | id, project_id, version, file_path, raw_text, processed_at |
| `Baseline` | id, project_id, proposal_id, version, status (draft/active/archived), confirmed_at, confirmed_by |
| `Deliverable` | id, baseline_id, ext_id, name, description, phase, type, planned_date, acceptance_criteria, dependencies, source_excerpt, status |
| `Report` | id, project_id, period_start, period_end, status_schedule, status_scope, status_quality, justification_schedule, justification_scope, justification_quality, highlights, next_steps, submitted_at, approved_at, approved_by |
| `DeliveryProgress` | id, report_id, deliverable_id, completion_pct, revised_date, deviation_flag, acceptance_confirmed |
| `Risk` | id, project_id, report_id, description, probability, impact, level, status, mitigation_plan, owner |
| `ActionPlan` | id, project_id, report_id, action, objective, owner, due_date, status, linked_risk_id, linked_deliverable_id |
| `PendingItem` | id, project_id, report_id, description, responsible_type, open_date, due_date, status, impact |
| `AIInsight` | id, project_id, report_id, type, message, priority, source_agent, scope (project/portfolio), acknowledged_at |
| `ScopeChange` | id, project_id, baseline_from_id, baseline_to_id, change_type, description, approved_by, approved_at |
| `ReportApproval` | id, report_id, approver_id, stage (PMO/CLIENT), decision (approved/approved_with_comment/requested_changes), comment, decided_at |
| `ProjectRetrospective` | id, project_id, delivered_vs_proposed, materialized_risks, would_do_differently, client_feedback, closed_at |
| `PortfolioConfig` | id (singleton), health_score_weights (JSONB), updated_at, updated_by |
| `AgentRunLog` | run_id (PK), task_type, engine_used, route_used, attempts (JSONB), duration_s, worker_id, artifact_path, failover_occurred, status, failure_reason, created_at, completed_at |
| `WorkerHeartbeat` | worker_id (PK), last_seen_at, status, sessions_status (JSONB), jobs_processed_today, jobs_failed_today |
| `DataProcessingRecord` | id, subject_type, subject_id, processing_purpose, legal_basis, retention_period, created_at |

---

## 10. Melhorias do Processo Incorporadas

Esta seção contém prescrições funcionais detalhadas que **estavam na v2.0/v2.1 e devem ser implementadas conforme aqui descrito**.

### 10.1. Fluxo de Aprovação em Três Estágios

> **Conformidade obrigatória:** o produto deve oferecer ao PMO **três caminhos distintos** ao revisar um report. Os três caminhos são parte do contrato com o usuário PMO, não capacidade implícita do schema.

Antes de o report ficar visível ao cliente, o PMO escolhe entre:

| Estágio | Comportamento |
|---|---|
| **Aprovar direto** | Report segue automaticamente para o cliente. Sem comentário interno. |
| **Aprovar com comentário** | Report segue para o cliente. **Comentário interno** anexado, visível apenas ao GP (não ao cliente). Útil para "aprovado, mas atenção a X no próximo report". |
| **Devolver para revisão** | Report **não vai** ao cliente. GP recebe notificação com o que precisa ajustar. Comentário obrigatório. |

**Implementação obrigatória:**
- UI do PMO mostra três botões/ações distintas, não menu escondido
- Modal de "Aprovar com comentário" deve indicar **explicitamente** que o comentário é nota interna ao GP, não vai ao cliente
- `ReportApproval.decision` tem 3 valores possíveis: `approved`, `approved_with_comment`, `requested_changes`
- Histórico mostra ícone diferente para "aprovado direto" vs "aprovado com comentário"
- O comentário interno é visível ao GP no histórico, mas não aparece no Portal do Cliente

### 10.2. Modo de Report Assistido por IA

Ao criar novo report, o backend pré-popula campos com base no report anterior:
- Riscos do report anterior trazidos automaticamente, GP confirma se ainda estão ativos
- Entregas com prazo previsto no período em destaque
- Sugestões geradas pelo agente como placeholders ("Na semana passada o risco X estava em monitoramento. Ainda está ativo?")

Disparado por task `prepopulate_report(project_id, period)` na criação do draft.

### 10.3. Health Score Automático do Projeto

> **Conformidade obrigatória:** Health Score usa fórmula com **5 componentes**, não 4. A implementação deve ser revisada para alinhar.

```
Health Score (0-100) =
  (Status RAG médio       × 0.35) +
  (SPI                    × 0.25) +
  (Risco geral inverso    × 0.20) +
  (Taxa de resolução      × 0.10) +
  (Estabilidade do status × 0.10)
```

**Definições precisas:**

| Componente | Definição | Fonte |
|---|---|---|
| Status RAG médio | Média numérica do RAG das 3 dimensões do último report. Verde=100, Amarelo=50, Vermelho=0. Média das 3 dimensões. | `Report.status_schedule/scope/quality` |
| SPI | (% médio de conclusão das entregas previstas até agora) ÷ (% planejado até agora). Cap em 100. | `DeliveryProgress.completion_pct` vs `Deliverable.planned_date` |
| Risco geral inverso | 100 menos a média ponderada dos níveis de risco abertos. Critical=100, High=75, Medium=50, Low=25. | `Risk.level` quando `status` ∈ identified/monitoring |
| Taxa de resolução | (Pendências fechadas no período) ÷ (Pendências abertas no período) × 100 | `PendingItem.status` |
| Estabilidade | Quantos reports consecutivos no mesmo status RAG agregado. 5+ reports no mesmo Verde = 100; 5+ reports no mesmo Vermelho = 0; oscilação = 50. | Histórico de `Report.status_*` |

**Pesos** são editáveis pelo PMO via tela de configuração (`PortfolioConfig.health_score_weights`), com **defaults ancorados nesta spec** (35/25/20/10/10). Mudança de pesos afeta o Health Score de todos os projetos imediatamente.

**Recálculo:** a cada submissão de report.

**Classificação textual:**
- 70-100: "Saudável" (verde)
- 40-69: "Atenção" (âmbar)
- 0-39: "Crítico" (vermelho)

### 10.4. Ciclo de Retrospectiva ao Fim de Cada Projeto

Ao encerrar um projeto, o GP realiza um **report final estruturado** (não opcional, parte do encerramento):

| Campo | Descrição |
|---|---|
| Entregue vs. Proposto | Lista comparativa do que foi entregue contra o baseline original |
| Riscos materializados | Quais riscos viraram realidade e como foram tratados |
| O que faria diferente | Aprendizados acionáveis |
| Feedback do cliente | Texto estruturado capturado em conversa final |

Esses dados alimentam diretamente o **Agente de Inteligência Cruzada** para projetos futuros.

Endpoint: `POST /projects/{id}/close` exige preenchimento da retrospectiva. Modelo `ProjectRetrospective`.

### 10.5. Versionamento de Escopo

Quando o escopo precisar mudar formalmente:
- GP faz upload de proposta v2
- Agente compara v1 vs v2 e gera diff (adicionados, removidos, prazo alterado, escopo alterado)
- GP e PMO revisam mudanças
- Após aprovação, novo baseline é criado (v1 arquivado, v2 ativo)
- `ScopeChange` registra o quê, por quê, impacto, quem aprovou

Cada item adicionado/removido/alterado entre versões gera um `ScopeChange` linkado ao baseline.

### 10.6. Integrações futuras (fora do escopo do MVP)
- Jira / Azure DevOps
- Google Calendar / Outlook
- Google Drive / SharePoint
- Slack / Teams (notificações)

---

## 11. Implicações Operacionais e Mitigações

### 11.1. Disponibilidade da máquina worker

**Implicação:** se a máquina worker estiver desligada, todo upload de proposta fica preso na fila.

**Mitigações:**
- Máquina **dedicada** (não laptop pessoal), sempre ligada, com no-break
- `WorkerHeartbeat` com alerta ao operador se ausente > 10 min em horário comercial
- UI honesta: GP que faz upload vê tempo estimado de fila
- Política explícita: "fora do horário comercial, processamento pode demorar até a próxima manhã"

### 11.2. Governança das contas Claude/ChatGPT

**Implicação:** assinaturas pessoais criam dependência humana.

**Mitigações:**
- Conta corporativa Jump dedicada para cada provider (`agentes@jump.com.br`)
- Senha em cofre Jump (1Password/Bitwarden) com 2+ pessoas com acesso
- Custo das assinaturas é despesa do produto

### 11.3. Re-login interativo

**Mitigações:**
- Quando broker detecta `LOGIN_REQUIRED`, emite evento `user_login_required`
- Backend cria notificação no dashboard do operador
- Operador acessa máquina (presencial ou Anydesk/RDP), executa `wsl tmux attach -t project-claude`, completa login
- Após sucesso, operador roda `jump-runner login-confirm claude`
- Job que disparou o login é re-enfileirado automaticamente

### 11.4. Latência percebida

**Mitigações:**
- Frontend é **assíncrono honesto**
- SSE para atualização em tempo real
- Email de notificação como fallback
- Estimativa de tempo na UI baseada em estatísticas reais

### 11.5. Crescimento (mais workers)

**Suporte nativo:** modelo já comporta N workers lendo da mesma fila Redis. Critério: "quando média de tempo na fila exceder 10 min por 3 dias seguidos, adicionar segundo worker".

### 11.6. Plano de transição (saída para API se necessário)

Após 3 meses de operação, comparar custo das assinaturas + custo operacional vs. custo de API. Plano técnico de migração: `jump-agent-runner` ganha terceiro provider `APIProvider`, configuração troca, mesma interface.

A decisão atual **não é irreversível**.

---

## 12. LGPD e Governança de Dados

### 12.1. Dados pessoais e sensíveis envolvidos

| Categoria | Origem | Onde repousa |
|---|---|---|
| Nome, email de usuários | Cadastro | PostgreSQL Railway |
| Conteúdo de propostas comerciais | Upload | Storage R2 + workspace temp do worker |
| Conteúdo de reports | Preenchimento dos GPs | PostgreSQL Railway |
| Logs de execução de IA (prompts e respostas) | Worker | Disco local + agregado em PostgreSQL |

### 12.2. Bases legais

- **Funcionários da Jump (GPs, PMO):** legítimo interesse para gestão de trabalho
- **Clientes (Bradesco, futuros):** execução de contrato
- **Dados pessoais em propostas de terceiros:** depende do contrato com cada cliente

### 12.3. Política de retenção

| Dado | Retenção |
|---|---|
| Propostas (originais) | 5 anos após encerramento do projeto |
| Reports | 5 anos após encerramento do projeto |
| Workspace temp do worker | 7 dias |
| Logs do agent-runner | 90 dias |
| `AgentRunLog` (metadados) | 5 anos |

### 12.4. Cláusulas obrigatórias com providers

Antes do piloto Bradesco enviar dados reais:
- Anthropic: confirmar opt-out de uso de dados para treinamento
- OpenAI: desativar "Improve the model for everyone" em Data Controls
- Operador da máquina é treinado a verificar essas configs em cada conta corporativa

### 12.5. Trânsito de dados

Cada salto está sob TLS. Workspace local com permissões restritas. Limpeza automática após 7 dias.

### 12.6. Direitos do titular

- `GET /me/data-export`: ZIP com todos os dados do titular autenticado
- `POST /me/data-deletion-request`: pedido revisado pelo PMO
- Para clientes externos sem conta: pedidos via `lgpd@jump.com.br`, atendidos em até 15 dias

### 12.7. Documentação obrigatória

`docs/lgpd.md` versionado com: controlador, encarregado (DPO), operadores (Anthropic, OpenAI, Cloudflare/R2, Railway), bases legais, retenção, procedimento para incidentes, RAT.

---

## 13. Plano de Implementação em Fases

### Fase 0 — Decisões operacionais e setup
Provisionar máquina worker, criar contas corporativas, anotar proposta gold-standard do Bradesco, setup do monorepo, CI verde.

### Fase 1 — `jump-agent-runner`
Tipos, validador, observer, headless Claude, headless Codex, broker WSL+tmux, providers, runner com fallback, observabilidade, setup script.

### Fase 2 — Backend Railway + Worker integrado
Auth+RBAC, CRUD projetos/propostas, fila Redis, callback HMAC, dashboard operador, cadastro Bradesco end-to-end.

### Fase 3 — Frontend GP
Telas de criação, upload, revisão de baseline, formulário de report, dashboard GP, histórico.

### Fase 4 — PMO, Cliente, Aprovação, Health Score, Versionamento, Notificações
Dashboard PMO com Health Score visível, fluxo de aprovação em 3 estágios, portal do cliente, agente de análise, comparação de propostas.

### Fase 5 — Inteligência cruzada, retrospectiva, exportação, LGPD, deploy
Agente de portfólio, modo assistido, retrospectiva, export PDF/PPTX, LGPD documentado, deploy em produção.

### Fase 6 — Hardening contínuo
Feedback dos GPs, refinamento de prompts, otimizações, segundo worker se necessário.

---

## 14. Métricas e Riscos

### 14.1. Métricas de produto

| Métrica | Meta |
|---|---|
| Tempo médio para preencher report | < 15 min |
| Taxa de adoção pelos GPs | > 80% |
| Precisão do agente leitor | > 85% sem edição manual |
| Reports liberados ao cliente no prazo | > 90% |
| NPS interno | > 7/10 |

### 14.2. Métricas operacionais

| Métrica | Meta |
|---|---|
| Disponibilidade do worker em horário comercial | > 99% |
| Tempo médio em fila | < 2 min |
| Tempo médio de execução de tarefa | < 3 min |
| Taxa de fallback Claude → Codex | < 10% |
| Tarefas com re-login interativo | < 1 por semana |

### 14.3. Métricas de negócio

| Métrica | Meta em 12 meses |
|---|---|
| Horas economizadas | 960h |
| Economia direta | R$ 96.000,00 |
| Escopo recuperado | reportado por projeto |
| Custo das assinaturas | < R$ 400/mês total (Claude + ChatGPT corporativos) |

### 14.4. Riscos do projeto

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Máquina worker indisponível | Média | No-break, monitoramento, segundo worker planejado |
| Login expira fora de horário comercial | Média | SLA "atendimento até início do próximo dia útil" |
| Quota da assinatura excedida | Baixa-Média | Fallback Claude→Codex; possível upgrade |
| Dados sensíveis vazam por má config | Baixa | Procedimento documentado, checklist no setup |
| Custo das assinaturas sobe | Baixa | Plano de transição para API |
| Erro do agente leitor gera disputa contratual | Baixa | Modo shadow na Fase 1 |

---

*Este documento é um artefato vivo. Revisado ao final de cada fase. Versões anteriores em `docs/spec_history/`.*
