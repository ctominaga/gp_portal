# F2.8 — Smoke real do agente leitor contra Bradesco (F5.6b)

**Data:** 2026-05-14
**Run ID:** `f28-bradesco-1778780537`
**Prompt:** `docs/prompts/proposal_reader_v1.md`
**Proposta (texto):** `backend/tests/fixtures/proposals/bradesco_sas_databricks.txt`
**Expected (gold F0):** `backend/tests/fixtures/proposals/bradesco_sas_databricks.expected.json`
**Engine:** claude (headless, 1 tentativa(s), 159.2s)

---

## Decisão operacional

| Critério | Score | Veredito |
|---|---|---|
| Recall **simples** (média não-ponderada) | 64.8% | **SHADOW** |
| Recall **ponderado** (criticidade do campo) | 81.5% | **PASS** |

**Critério (cada métrica):** PASS se ≥ 80%; SHADOW se 50–80%; FAIL se < 50%.
Recall = % de itens do `expected.json` cobertos pelo `actual.json` (normalize + substring + Jaccard ≥ 0.45). Extras encontrados pelo agente NÃO penalizam recall.

Pesos da métrica ponderada:
- `project`: 1.0
- `phases`: 1.0
- `deliverables`: 2.0
- `key_premises`: 0.5
- `out_of_scope`: 0.5

Justificativa dos pesos: `deliverables` e `phases` formam o backlog operacional do baseline (peso 1–2). `key_premises` e `out_of_scope` são importantes mas a comparação por Jaccard de palavras é ruim para sinônimos ("código SAS legado" vs "scripts SAS originais", "acesso ao Databricks" vs "disponibilização dos ambientes Databricks"). Falsos negativos dessa heurística não devem dominar o veredito. Inspeção visual dos extras valida que a substância está coberta.

---

## Métricas por chave

| Chave | Expected | Actual | Match | Recall |
|---|---|---|---|---|
| `project` (campos) | 11 | 11 + 0 extras | 10 | **90.9%** |
| `phases` | 4 | 4 | 4 | **100.0%** |
| `deliverables` | 21 | 21 | 21 | **100.0%** |
| `key_premises` | 4 | 16 | 0 | **0.0%** |
| `out_of_scope` | 3 | 18 | 1 | **33.3%** |

---

## `project` — campos

- ✅ client_name
- ✅ project_name
- ✅ proposal_number
- ✅ domain
- ✅ scenario_recommended_by_jump
- ✅ team_composition
- ❌ **estimated_capacity_per_sprint_hours**
  - expected: `320`
  - actual:   `None`
- ✅ estimated_total_capacity_hours
- ✅ duration_sprints
- ✅ sprint_length_weeks
- ✅ expected_acceleration_pct

---

## `phases` — match por id

- ✅ `sprint-1` (Sprint 1 — Convergência inicial) → actual: Sprint 1 — Convergência inicial
- ✅ `sprint-2` (Sprint 2 — Escala e padronização) → actual: Sprint 2 — Escala e consolidação
- ✅ `sprint-3` (Sprint 3 — Fechamento técnico) → actual: Sprint 3 — Fechamento técnico regulatório
- ✅ `phaseout` (Phaseout — Transição assistida) → actual: Phaseout — Transição Estratégica e Suporte Supervisionado

---

## `deliverables` — match por id ou title

- ✅ `d-001` Migração de Custos PD/AED/LGD para PySpark/Databricks
- ✅ `d-002` Migração de RSA (Risco de Spread Atuarial) para PySpark/Databricks
- ✅ `d-003` Migração de Dash Orçamento para PySpark/Databricks
- ✅ `d-004` Migração de Instifina para PySpark/Databricks
- ✅ `d-005` Migração de Depósitos Judiciais para PySpark/Databricks
- ✅ `d-006` Migração de Veículo para PySpark/Databricks
- ✅ `d-007` Migração de RATI para PySpark/Databricks
- ✅ `d-008` Migração de Resumoc para PySpark/Databricks
- ✅ `d-009` Migração de CERM para PySpark/Databricks
- ✅ `d-010` Migração de Outros Riscos para PySpark/Databricks
- ✅ `d-011` Migração de AlertCli_Sale para PySpark/Databricks
- ✅ `d-012` Migração de DDR para PySpark/Databricks
- ✅ `d-013` Migração de Segmentação para PySpark/Databricks
- ✅ `d-014` Migração de SARS para PySpark/Databricks
- ✅ `d-015` Migração de IRRBB (Interest Rate Risk in the Banking Book) para PySpark/Databric
- ✅ `d-016` Migração de FRTB (Fundamental Review of the Trading Book) para PySpark/Databrick
- ✅ `d-017` Migração de RML para PySpark/Databricks
- ✅ `d-018` Migração de Restritivo Socioambiental para PySpark/Databricks
- ✅ `d-019` Documentação técnica final das rotinas migradas (rastreabilidade SAS↔PySpark)
- ✅ `d-020` Shadowing e transferência de conhecimento para o time interno do Bradesco
- ✅ `d-021` Estabilização do ambiente Databricks pós-migração (suporte à operação)

---

## `key_premises` — recall do expected

- ❌ Disponibilidade do código SAS legado para análise prévia
   - melhor match no actual: Concessão de acessos técnicos à equipe Jump para os ambientes SAS e Databricks (credenciais, repositórios de código, scr (score 0.17)
- ❌ Acesso ao ambiente Databricks na Azure já provisionado pelo Bradesco
   - melhor match no actual: Acesso às ferramentas de versionamento e orquestração utilizadas pelo Bradesco (Git, IWS ou equivalentes) (score 0.21)
- ❌ Validação técnica e funcional pelo Bradesco em até 5 dias úteis após cada entrega
   - melhor match no actual: Prazo de validação por parte do Bradesco de até 5 (cinco) dias úteis por entrega disponibilizada (após esse prazo a entr (score 0.37)
- ❌ Reuniões de planejamento e revisão quinzenais (cadência de sprint)
   - melhor match no actual: Reuniões semanais de acompanhamento técnico para ajuste de direcionamentos e mitigação de riscos operacionais (score 0.07)

### Extras do actual (16)
> Listados para validação humana opcional. Não penalizam recall.

- Disponibilização dos ambientes de desenvolvimento, homologação e produção no Databricks devidamente configurados
- Acesso às ferramentas de versionamento e orquestração utilizadas pelo Bradesco (Git, IWS ou equivalentes)
- Tabelas consumidas pelas rotinas SAS previamente disponibilizadas e acessíveis no ambiente Databricks
- Disponibilização do mapeamento de/para caso existam alterações nos nomes de tabelas ou campos em relação ao ambiente SAS original
- Concessão de acessos técnicos à equipe Jump para os ambientes SAS e Databricks (credenciais, repositórios de código, scripts e bases)
- Entrega dos scripts SAS originais (.sas), incluindo macros e dependências entre rotinas
- Disponibilização de dicionários de dados, layouts, mapeamentos e documentação técnica existente
- Compartilhamento de logs de execução ou evidências que auxiliem na interpretação das lógicas SAS
- Designação de pontos focais técnicos e funcionais do Bradesco para suporte e validação durante as fases de migração
- Participação ativa dos representantes de negócio na validação funcional dos outputs e na homologação dos resultados
- Definição conjunta entre Jump e Bradesco das prioridades de migração conforme valor de negócio e criticidade
- Prazo de validação por parte do Bradesco de até 5 (cinco) dias úteis por entrega disponibilizada (após esse prazo a entrega é tacitamente validada)
- Solicitações de ajustes ou revisões após o período de validação serão tratadas como transbordo da sprint vigente e replanejadas
- Concessão de acesso e autorização para uso do MigrateMind pela Jump (caso não seja viabilizado, capacidade e cronograma serão replanejados)
- Reuniões semanais de acompanhamento técnico para ajuste de direcionamentos e mitigação de riscos operacionais
- Critérios objetivos de aceitação definidos conjuntamente, incluindo margem técnica aceitável para variações numéricas entre engines SAS e Databricks

---

## `out_of_scope` — recall do expected

- ✅ Correção de incidentes fora do período de phaseout e shadowing
   - actual: Monitoramento contínuo, suporte técnico de produção ou correção de incidentes fora do período de phaseout (score 0.45)
- ❌ Rotinas SAS que envolvam macros customizadas não documentadas previamente
   - melhor match no actual: Intervenções em rotinas SAS que não estejam incluídas no escopo do backlog priorizado (score 0.27)
- ❌ Mudanças no modelo de dados de origem
   - melhor match no actual: Implementação de novas políticas de segurança, mascaramento ou anonimização de dados (score 0.1)

### Extras do actual (17)
> Listados para validação humana opcional. Não penalizam recall.

- Sustentação e suporte operacional contínuo após o período de phaseout e shadowing supervisionado
- Responsabilidade sobre o agendamento e execução recorrente dos pipelines em ambiente produtivo
- Alterações ou melhorias nas regras de negócio das rotinas SAS originais não relacionadas ao processo de migração
- Criação de novos cálculos, indicadores ou estruturas analíticas não previstos no levantamento técnico
- Construção de novas rotinas SAS ou Databricks fora do escopo mapeado
- Integração com sistemas externos ou bases adicionais não mencionadas no levantamento técnico
- Criação de APIs, dashboards ou camadas de visualização analítica
- Implementação de novas políticas de segurança, mascaramento ou anonimização de dados
- Alterações estruturais nas políticas de governança e acessos do Databricks fora das diretrizes já estabelecidas
- Configuração, atualização ou suporte à infraestrutura de cloud e instâncias Databricks
- Custos ou gestão de licenças associadas ao Databricks, SAS, SQL Server, Mainframe ou demais ferramentas
- Provisionamento de novos ambientes além dos já disponibilizados para o projeto
- Suporte técnico, correção de erros ou manutenção evolutiva do ambiente SAS após a migração
- Intervenções em rotinas SAS que não estejam incluídas no escopo do backlog priorizado
- Atividades de refatoração, performance tuning ou reestruturação lógica das rotinas além do necessário para a equivalência funcional SAS → Databricks
- Otimizações de queries e pipelines visando fine tuning de performance não diretamente ligadas à equivalência técnica
- Atividades de ingestão produtiva, que serão conduzidas internamente pelo Bradesco

---

## Recomendação operacional para o piloto Bradesco

**Decisão final (aprovada por Christopher Tominaga em 2026-05-14): PASS técnico + SHADOW operacional na 1ª semana, com upgrade para automático condicional.**

| Aspecto | Veredito |
|---|---|
| **Técnico** | **PASS** (recall ponderado 81.5%). O agente leitor v1 extrai corretamente os campos críticos do baseline (deliverables 100%, phases 100%, project 90.9%). Discrepâncias em `key_premises`/`out_of_scope` são majoritariamente wording dependent (Jaccard de palavras fraco para sinônimos); inspeção visual dos 16+17 extras valida que a substância da proposta foi extraída. Não há motivo técnico para iterar v1.1 antes do piloto. |
| **Operacional (semana 1)** | **SHADOW**. Spec v3.1 §1.5 já prevê modo shadow inicial. Mantém GP no loop como auditor do primeiro baseline real. Custo: GP revisa premises/oos antes de ativar baseline na primeira proposta. |
| **Operacional (semana 2+)** | **Upgrade condicional para AUTOMÁTICO**. Critério: se o GP não tocar em premises/oos do primeiro baseline (ou tocar pouco), agente passa para modo automático. Se editar muito, fica em shadow indefinidamente e reabre ciclo de iteração v1.1. |

**Gatilho do upgrade:** registrar no `ProjectRetrospective` do primeiro projeto ativo (ou em um diário operacional) se houve edição relevante em premises/oos do baseline gerado pelo agente. Decisão é binária e fica documentada para auditoria.

**Riscos residuais conhecidos:**

1. Campo `project.estimated_capacity_per_sprint_hours` (320) **não foi extraído** pelo agente. Para a proposta Bradesco, é calculável trivialmente (`estimated_total_capacity_hours / duration_sprints = 960 / 3 = 320`). Mitigação: GP pode preencher manualmente, ou prompt v1.1 adiciona instrução para derivar. Não bloqueia o piloto.

2. 2 itens de `out_of_scope` do `expected.json` **não foram capturados** pelo agente:
   - "Rotinas SAS que envolvam macros customizadas não documentadas previamente"
   - "Mudanças no modelo de dados de origem"

   Esses ficam como risco controlado: GP valida `out_of_scope` na primeira semana e adiciona manualmente se aplicável. Recall de OOS é o componente mais frágil da heurística atual.

3. Métrica `key_premises` 0% strict é **artefato do Jaccard**, não defeito real do agente — extraiu 16 premises plausíveis e literais. Em iteração futura (F5.9 ou hardening), substituir Jaccard por embedding similarity (sentence-transformers local ou Cohere) elimina esse falso negativo.

## Conclusão

- Métrica **simples**: 64.8% → **SHADOW** (heurística penalizada por Jaccard de palavras).
- Métrica **ponderada** (recomendada): 81.5% → **PASS** (criticidade-aware: deliverables/phases pesam mais).
- **Decisão final operacional:** PASS técnico + SHADOW na semana 1 + upgrade condicional para automático.

Confidence score auto-reportada pelo agente: 82/100. Tempo: 159.2s. Engine: Claude headless, 1 tentativa, sem fallback.

Esse relatório fecha o débito K (`F2.8 — smoke real do agente leitor`) aberto desde o ADR `2026-05-11 — F2.8 adiado para F5`.
