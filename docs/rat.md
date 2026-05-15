# Registro de Atividades de Tratamento (RAT)

**Versão:** v1.0 piloto Bradesco — revisão jurídica externa pendente para v1.1
**Data:** 2026-05-14
**Encarregado (DPO) responsável:** Christopher Tominaga — `christopher.tominaga@jumplabel.com.br`
**Canal LGPD para titulares externos:** `christopher.tominaga@jumplabel.com.br`

Este Registro de Atividades de Tratamento descreve, para cada atividade do Sistema de Report Jump, a finalidade, os dados tratados, os titulares envolvidos, a base legal (LGPD art. 7º), a retenção e os operadores. É o complemento técnico de [`docs/lgpd.md`](lgpd.md); decisões sobre direitos do titular e procedimento de incidentes ficam lá.

A modelagem técnica de cada atividade está em [`backend/app/models/domain.py`](../backend/app/models/domain.py). As remissões abaixo apontam diretamente para as entidades e enums onde os dados repousam.

Controlador: Jump Label, CNPJ 09.032.085/0001-64, endereço Alameda Rio Negro, 500 — Torre B, 15º andar, Barueri/SP, Brasil — CEP 06454-000.

---

## A1. Autenticação de usuários internos

| Campo | Conteúdo |
|---|---|
| Finalidade | Autenticar funcionários da Jump Label (papéis GP, PMO, OPERATOR) e operar controle de acesso aos recursos do Sistema |
| Categorias de dados | Nome, e-mail corporativo, hash de senha (bcrypt), papel (`role`), data de cadastro |
| Titulares | Funcionários da Jump Label |
| Base legal | Execução de contrato de trabalho — LGPD art. 7º V |
| Retenção | Enquanto vigente a relação de trabalho. Após desligamento ou pedido de eliminação: anonimização irreversível (`users.anonymized_at`) com preservação de integridade referencial em projetos vivos (art. 16 II) |
| Operadores envolvidos | Railway (PostgreSQL) |
| Compartilhamentos internacionais | Estados Unidos (Railway) |
| Localização técnica | Entidade [`User`](../backend/app/models/user.py) |

---

## A2. Atendimento do cliente contratante

| Campo | Conteúdo |
|---|---|
| Finalidade | Disponibilizar o portal de aprovação de relatórios aos representantes do cliente contratante (papel CLIENT) |
| Categorias de dados | Nome, e-mail corporativo, hash de senha, papel (`role=CLIENT`), vínculo com projetos via `Project.client_user_id` |
| Titulares | Representantes do cliente contratante autorizados a acessar o portal (em v1.0: Bradesco) |
| Base legal | Execução de contrato comercial — LGPD art. 7º V |
| Retenção | Enquanto vigente o contrato com o cliente. Após encerramento: anonimização nas condições da A1 |
| Operadores envolvidos | Railway, Resend (para envio de notificações de aprovação pendente) |
| Compartilhamentos internacionais | Estados Unidos (Railway, Resend) |
| Localização técnica | Entidades [`User`](../backend/app/models/user.py), [`Project`](../backend/app/models/domain.py) |

---

## A3. Upload e leitura de propostas comerciais

| Campo | Conteúdo |
|---|---|
| Finalidade | Receber a proposta comercial em PDF enviada pelo GP, extrair o escopo estruturado (entregáveis, premissas, fora-de-escopo) por meio do agente leitor, e registrar o `Baseline` que serve de referência para os relatórios futuros |
| Categorias de dados | Conteúdo textual da proposta (PDF original e texto extraído), nome do arquivo original, hash SHA-256 do arquivo, identificação do GP que realizou o upload. O conteúdo pode mencionar pessoas envolvidas no projeto do cliente |
| Titulares | GP da Jump Label (uploader); pessoas eventualmente nomeadas na proposta (terceiros) |
| Base legal | Execução de contrato (art. 7º V) para o GP; legítimo interesse com base na finalidade contratada pelo cliente (art. 7º IX) para terceiros nomeados |
| Retenção | 5 anos após o encerramento do projeto. Workspace temporário do worker: 7 dias |
| Operadores envolvidos | Cloudflare R2 (PDF original e artefatos), Railway (texto extraído e metadados), Anthropic (execução do agente leitor), OpenAI (fallback do agente, atualmente em pausa operacional) |
| Compartilhamentos internacionais | União Europeia / Estados Unidos (Cloudflare R2), Estados Unidos (Railway, Anthropic, OpenAI) |
| Localização técnica | Entidades [`Proposal`](../backend/app/models/domain.py), [`Baseline`](../backend/app/models/domain.py), [`Deliverable`](../backend/app/models/domain.py) |

---

## A4. Geração de relatórios executivos

| Campo | Conteúdo |
|---|---|
| Finalidade | Permitir ao GP registrar a evolução do projeto em ciclos periódicos (status RAG por dimensão, progresso por entregável, riscos, planos de ação, pendências, destaques e próximos passos) e entregar o relatório aos demais atores (PMO, cliente) |
| Categorias de dados | Texto livre nas seções narrativas e descritivas, identificação do GP autor, datas do período coberto, identificação dos entregáveis e seus status, riscos com responsável atribuído |
| Titulares | GP autor; demais pessoas eventualmente nomeadas nos textos livres (responsáveis por risco, owner de plano de ação, parte responsável por pendência) |
| Base legal | Execução de contrato (art. 7º V) — entrega contratada ao cliente; legítimo interesse (art. 7º IX) para identificação de responsáveis em risco e ação |
| Retenção | 5 anos após o encerramento do projeto. Eliminação programática de texto livre é débito v1.1 — F5.7.X |
| Operadores envolvidos | Railway (PostgreSQL) |
| Compartilhamentos internacionais | Estados Unidos (Railway) |
| Localização técnica | Entidades [`Report`](../backend/app/models/domain.py), [`DeliveryProgress`](../backend/app/models/domain.py), [`Risk`](../backend/app/models/domain.py), [`ActionPlan`](../backend/app/models/domain.py), [`PendingItem`](../backend/app/models/domain.py) |

---

## A5. Aprovação multi-stage de relatórios

| Campo | Conteúdo |
|---|---|
| Finalidade | Registrar o fluxo de aprovação do relatório (estágios PMO e CLIENT) com decisão, comentário interno (PMO) e carimbo de data |
| Categorias de dados | Identificação do aprovador, estágio, decisão (aprovado, aprovado com comentário, mudanças requeridas), comentário em texto livre, timestamp |
| Titulares | Aprovador (PMO ou representante do cliente) |
| Base legal | Execução de contrato — LGPD art. 7º V |
| Retenção | 5 anos após o encerramento do projeto |
| Operadores envolvidos | Railway (PostgreSQL), Resend (para notificar partes em cada decisão) |
| Compartilhamentos internacionais | Estados Unidos (Railway, Resend) |
| Localização técnica | Entidade [`ReportApproval`](../backend/app/models/domain.py) |

---

## A6. Execução do agente leitor e logs de IA

| Campo | Conteúdo |
|---|---|
| Finalidade | Auditar a execução do agente leitor (Claude / Codex) para fins de qualidade da extração, investigação de falhas, comparação contra baseline e análise de regressão entre versões do prompt |
| Categorias de dados | `run_id`, tipo de tarefa, identificação do projeto/proposta/relatório, motor utilizado, rota (`headless` / `broker`), número de tentativas, duração, identificação do worker, caminho do artefato, status final e motivo de falha. O conteúdo bruto do prompt e da resposta é gravado em arquivo no disco local efêmero do worker, não no banco |
| Titulares | Pessoas eventualmente nomeadas nos prompts (mesmas categorias da A3) |
| Base legal | Legítimo interesse — auditoria, segurança e qualidade do agente — LGPD art. 7º IX |
| Retenção | Metadados estruturados (`AgentRunLog`): 5 anos. Logs brutos no disco local do worker: 90 dias com rotação automática. Workspace temporário: 7 dias |
| Operadores envolvidos | Railway (metadados), Anthropic (execução), OpenAI (fallback) |
| Compartilhamentos internacionais | Estados Unidos (Railway, Anthropic, OpenAI) |
| Localização técnica | Entidade [`AgentRunLog`](../backend/app/models/domain.py) |

---

## A7. Notificação por e-mail transacional

| Campo | Conteúdo |
|---|---|
| Finalidade | Comunicar eventos operacionais relevantes aos atores envolvidos (submissão de relatório, decisão de aprovação, mudança de escopo aprovada/rejeitada, pedidos LGPD criados, recibo ao titular) |
| Categorias de dados | E-mail do destinatário, assunto, corpo da mensagem (texto livre que pode mencionar o projeto e seus atores) |
| Titulares | Usuários internos da Jump Label, representantes do cliente, titulares que comunicam pedido LGPD |
| Base legal | Execução de contrato — LGPD art. 7º V (notificações operacionais inerentes ao Sistema) |
| Retenção | Conforme política do operador Resend (a confirmar contratualmente — débito de §8 do `lgpd.md` quando da renovação contratual) |
| Operadores envolvidos | Resend |
| Compartilhamentos internacionais | Estados Unidos (Resend) |
| Localização técnica | Serviço [`backend/app/services/notifications.py`](../backend/app/services/notifications.py) |

---

## A8. Atendimento a pedidos LGPD

| Campo | Conteúdo |
|---|---|
| Finalidade | Registrar e atender pedidos do titular previstos no art. 18 LGPD (export, eliminação, acesso, retificação), atendendo o prazo do art. 19 (15 dias úteis) e a obrigação de prestação de contas do art. 6º X |
| Categorias de dados | Identificação do titular (usuário com conta via `subject_user_id`, ou e-mail externo via `subject_external_email`), tipo de pedido (`request_type`), estado de atendimento (`status`), responsável pelo atendimento (`handled_by_id`), data do pedido, data do atendimento, notas administrativas em texto livre |
| Titulares | Qualquer titular cujos dados pessoais sejam tratados pelo Sistema |
| Base legal | Cumprimento de obrigação legal — LGPD art. 7º II combinado com arts. 18 e 19 |
| Retenção | 5 anos após o atendimento. Necessário para prestação de contas ao controlador e à ANPD (art. 6º X) |
| Operadores envolvidos | Railway (registro), Resend (notificação ao DPO e recibo ao titular) |
| Compartilhamentos internacionais | Estados Unidos (Railway, Resend) |
| Localização técnica | Entidade [`DataProcessingRecord`](../backend/app/models/domain.py) |

---

## Notas técnicas

**Sobre o modelo do `DataProcessingRecord`.** A spec consolidada v3.1 §9.5 lista os atributos `processing_purpose`, `legal_basis` e `retention_period` como pertencentes a essa entidade. A redação da v1.0 deste RAT reconhece que tais atributos descrevem **atividades de tratamento** da Jump Label (este documento), não **pedidos individuais de titular** (que é o que `DataProcessingRecord` registra). A entidade em código permanece como está; a correção da spec é débito consolidado em v3.2.

**Sobre dados sensíveis.** O Sistema não trata dados pessoais sensíveis (LGPD art. 5º II). Caso uma proposta contenha tais dados como conteúdo do escopo do projeto contratado pelo cliente, a Jump Label atua como operadora do cliente nesse aspecto, aplicando-se as cláusulas específicas do contrato comercial.

**Sobre revisão e atualização.** Este RAT é revisado: (a) sempre que um novo operador for adicionado ao Sistema; (b) sempre que uma atividade nova for criada ou descontinuada; (c) no mínimo anualmente. A versão e o histórico de revisão acompanham a evolução em `docs/lgpd.md` §11.

---

## Histórico de versões

| Versão | Data | Mudanças |
|---|---|---|
| v1.0 piloto Bradesco | 2026-05-14 | Versão inicial. 8 atividades catalogadas. Assinada pelo DPO Christopher Tominaga. Revisão jurídica externa pendente para v1.1. |
