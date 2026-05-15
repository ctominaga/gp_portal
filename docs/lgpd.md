# Política de Tratamento de Dados Pessoais — Sistema de Report Jump

**Versão:** v1.0 piloto Bradesco — revisão jurídica externa pendente para v1.1
**Data:** 2026-05-14
**Encarregado (DPO) responsável:** Christopher Tominaga — `christopher.tominaga@jumplabel.com.br`
**Aprovação:** Christopher Tominaga, DPO designado, em 2026-05-14.

Este documento descreve o tratamento de dados pessoais realizado pela Jump Label no contexto do Sistema de Report Jump (Sistema), em conformidade com a Lei 13.709/2018 (Lei Geral de Proteção de Dados Pessoais — LGPD). Tom técnico-jurídico; finalidade é registro auditável, não comunicação comercial.

Referências normativas adotadas: LGPD arts. 5º (definições), 6º (princípios), 7º (bases legais), 9º (informação ao titular), 16 (conservação após término do tratamento), 18 (direitos do titular), 19 (prazo de resposta), 41 (Encarregado), 46–49 (segurança e incidentes).

---

## §1. Controlador e Encarregado

**Controlador (art. 5º VI LGPD):** Jump Label, pessoa jurídica de direito privado, inscrita no CNPJ 09.032.085/0001-64, com endereço em Alameda Rio Negro, 500 — Torre B, 15º andar, Barueri/SP, Brasil — CEP 06454-000.

**Encarregado / DPO (art. 5º VIII e art. 41 LGPD):** Christopher Tominaga.

- E-mail funcional do DPO: `christopher.tominaga@jumplabel.com.br`
- Canal LGPD para titulares externos (sem conta no Sistema): `anderson.argentoni@jumplabel.com.br`
- Atribuições: recepção de comunicações dos titulares e da ANPD, orientação interna sobre proteção de dados, coordenação da resposta a incidentes (§7).

Os papéis acima são designações internas. O Encarregado responde pela conformidade do tratamento, mas o controlador é a pessoa jurídica.

---

## §2. Inventário de operadores

Operadores (art. 5º VII LGPD) — terceiros que tratam dados pessoais por ordem da Jump Label:

| Operador | Finalidade | Categorias de dados tratadas | Localização do tratamento |
|---|---|---|---|
| Anthropic | Execução do agente leitor de propostas (modelo Claude) | Conteúdo textual de propostas comerciais submetidas pelos GPs | Estados Unidos |
| OpenAI | Fallback do agente leitor (modelo Codex) — atualmente em pausa operacional | Mesmas categorias da Anthropic, quando ativado | Estados Unidos |
| Cloudflare R2 | Armazenamento de PDFs de propostas, artefatos do worker e ZIPs gerados para titulares | Conteúdo de propostas, identificadores de titulares (no nome de objeto) | União Europeia / Estados Unidos |
| Railway | Hospedagem da aplicação (PostgreSQL, Redis, backend, frontend) | Todos os metadados estruturados do Sistema (usuários, projetos, relatórios, aprovações, logs de execução) | Estados Unidos |
| Resend | Envio de e-mail transacional | Endereços de e-mail de destinatários, conteúdo das mensagens enviadas | Estados Unidos |

Os contratos de operação adotam, no mínimo, as cláusulas listadas na §8 (cláusulas obrigatórias com operadores).

---

## §3. Categorias de dados pessoais tratadas

| Categoria | Origem | Onde repousa | Observação |
|---|---|---|---|
| Nome e e-mail corporativo de usuários internos (GP, PMO, OPERATOR) | Cadastro pela Jump Label | PostgreSQL Railway | Identificação para autenticação e atribuição de responsabilidades |
| Nome e e-mail corporativo de representantes do cliente contratante (CLIENT) | Cadastro mediante contrato comercial | PostgreSQL Railway | Acesso ao portal de aprovação de relatórios |
| Conteúdo de propostas comerciais | Upload realizado pelo GP | Cloudflare R2 (PDF) + PostgreSQL Railway (texto extraído) + workspace temporário do worker | Pode conter dados pessoais de terceiros mencionados pelo cliente; consulta o §4 sobre base legal |
| Conteúdo de relatórios executivos | Preenchimento pelo GP | PostgreSQL Railway | Texto livre pode mencionar pessoas envolvidas no projeto (limitação tratada em §10 — débito F5.7.X) |
| Logs de execução do agente leitor (prompts e respostas) | Worker | Disco local efêmero do worker + agregado em `AgentRunLog` no PostgreSQL | Auditoria de qualidade da extração e investigação de incidentes |
| Registros de pedidos do titular (`DataProcessingRecord`) | Sistema | PostgreSQL Railway | Necessário para demonstrar atendimento (art. 6º X — responsabilização e prestação de contas) |

O Sistema **não trata** dados pessoais sensíveis (art. 5º II LGPD) — origem racial ou étnica, convicção religiosa, opinião política, filiação sindical, dados de saúde, vida sexual, genéticos, biométricos. Caso uma proposta contenha tais dados como conteúdo do escopo do projeto, o tratamento incide sobre a Jump Label apenas como o operador do cliente contratante; nesse caso aplica-se a cláusula contratual específica do cliente.

---

## §4. Bases legais

A base legal é aferida por categoria de dado e finalidade. As principais utilizadas no Sistema:

| Categoria / finalidade | Base legal LGPD | Artigo |
|---|---|---|
| Tratamento de dados de funcionários da Jump Label (GP, PMO, OPERATOR) para gestão da relação de trabalho | Execução de contrato de trabalho e obrigações legais correlatas | art. 7º V |
| Tratamento de dados de representantes do cliente contratante para fornecimento do Sistema | Execução do contrato comercial firmado com o cliente | art. 7º V |
| Tratamento de dados de terceiros mencionados em propostas comerciais | Legítimo interesse, com base na finalidade contratada pelo cliente, observada a expectativa razoável do titular | art. 7º IX |
| Tratamento de logs operacionais e de execução do agente leitor para auditoria, segurança e qualidade | Legítimo interesse | art. 7º IX |
| Atendimento de pedidos do titular (export, eliminação, retificação, acesso) | Cumprimento de obrigação legal (LGPD art. 18) | art. 7º II |

Esta versão v1.0 **não** utiliza consentimento (art. 7º I) como base primária. Caso, em versão futura, seja adicionada funcionalidade de comunicação opcional de marketing ou semelhante, esta seção será revisada (débito v1.1).

A documentação detalhada de cada atividade × propósito × base legal × retenção × operador é mantida em [`docs/rat.md`](rat.md) — Registro de Atividades de Tratamento.

---

## §5. Política de retenção

Os prazos abaixo se aplicam após o término do tratamento ou do contrato com o cliente, conforme aplicável. A conservação após o pedido de eliminação observa o art. 16 LGPD — em particular, retenção para cumprimento de obrigação legal ou regulatória e para exercício regular de direitos em processo judicial.

| Dado | Retenção | Gatilho de exclusão | Observação |
|---|---|---|---|
| Propostas comerciais (PDF original e texto extraído) | 5 anos após encerramento do projeto | Job programado | Necessária para defesa de contrato e auditoria do escopo |
| Relatórios executivos (incluindo Reports e Approvals) | 5 anos após encerramento do projeto | Job programado | Histórico do projeto entregue ao cliente |
| Workspace temporário do worker (arquivos `.txt`, intermediários) | 7 dias após a execução | Limpeza automática diária | Permissões 0700 no filesystem local |
| Logs do agent-runner (linha-a-linha) | 90 dias | Rotação automática | Conteúdo bruto de prompts e respostas — sem retenção longa |
| `AgentRunLog` (metadados estruturados de cada execução) | 5 anos | Job programado | Auditoria de qualidade do agente |
| `DataProcessingRecord` (pedidos LGPD do titular) | 5 anos após o atendimento | Job programado | Prestação de contas (art. 6º X LGPD) |
| Backups do PostgreSQL | 30 dias | Rotação automática (provedor) | Conservação curta intencional |
| Notificações in-app (`InAppNotification`) | 1 ano | Job programado | Aviso operacional, não compromisso contratual |

A eliminação de dados pessoais do titular após atendimento de pedido de eliminação segue o procedimento descrito na §6.4.

---

## §6. Direitos do titular

Os direitos abaixo seguem o art. 18 LGPD. Toda solicitação é respondida no prazo máximo de **15 dias úteis** (art. 19 LGPD).

### 6.1. Canais

| Tipo de titular | Canal primário | Observação |
|---|---|---|
| Titular com conta no Sistema (GP, PMO, CLIENT, OPERATOR) | Endpoints autenticados `GET /me/data-export` e `POST /me/data-deletion-request` | Resposta imediata para export; eliminação revisada pelo PMO antes do atendimento |
| Titular externo sem conta no Sistema (terceiros mencionados em propostas, ex-funcionários após eliminação, demais interessados) | E-mail dirigido a `anderson.argentoni@jumplabel.com.br` | Em v1.0 o DPO registra o pedido manualmente no painel administrativo. Formulário web público é débito v1.1 (F5.7.Y) |

### 6.2. Direito de confirmação e acesso (art. 18 I e II)

Titular logado: executa `GET /me/data-export`. O Sistema retorna, em até 30 segundos, um arquivo ZIP contendo (a) `me.json` com os próprios dados cadastrais, (b) `projects_as_gp.json` com os projetos em que atua como gerente e suas entidades vinculadas, (c) `projects_as_client.json` com os projetos em que atua como representante do cliente, filtrado para excluir dados de outros titulares, (d) `data_processing_records.json` com seus próprios pedidos LGPD anteriores, (e) `README.txt` explicando o conteúdo.

Titular externo: solicita por e-mail; o DPO extrai os dados pertinentes manualmente.

### 6.3. Direito de retificação (art. 18 III)

Titular logado: edita o próprio perfil ou abre pedido pelo canal autenticado. Titular externo: solicita por e-mail.

### 6.4. Direito de eliminação (art. 18 VI)

Procedimento técnico de eliminação adotado em v1.0 é a **anonimização irreversível** do registro de usuário (`users.name`, `users.email` e `users.password_hash` são substituídos por marcadores não reversíveis; é registrado `users.anonymized_at`). A integridade referencial dos projetos, propostas, relatórios e aprovações em que o titular foi GP ou aprovador é preservada, com base no art. 16 II LGPD (conservação para exercício regular de direitos em processo judicial).

Texto livre em campos descritivos (descrição de riscos, pendências, planos de ação, destaques e próximos passos do relatório) pode conter menções nominais ao titular. Em v1.0, esses campos **não** são anonimizados automaticamente; a retenção é justificada como histórico do projeto entregue ao cliente sob o mesmo art. 16 II. A varredura programática de texto livre é débito explícito v1.1 (F5.7.X) e está documentada na §10.

Após anonimização, a tentativa de autenticação do titular anonimizado é rejeitada com erro genérico, sem indicação do estado do registro (sem vazamento da informação de remoção).

### 6.5. Direito de portabilidade (art. 18 V)

Cumprido pelo mesmo endpoint de acesso (§6.2). Os dados são entregues em formato JSON estruturado, legível por máquina.

### 6.6. Direito de informação sobre operadores (art. 18 VII e art. 19 §1 II)

Cumprido por este documento (§2 — Inventário de operadores).

### 6.7. Revogação de consentimento (art. 8º §5)

Não aplicável em v1.0, dado que o consentimento (art. 7º I) não é base legal primária do Sistema. Revisado quando da introdução de funcionalidades baseadas em consentimento (v1.1 ou superior).

---

## §7. Procedimento de incidentes

Aplica-se a qualquer evento de segurança que envolva dados pessoais tratados pelo Sistema. Conforme art. 48 LGPD, a comunicação à ANPD e ao titular é devida quando o incidente puder acarretar risco ou dano relevante.

**Atores e responsabilidades:**

| Ator | Responsabilidade |
|---|---|
| Detector (qualquer membro da equipe, alerta automatizado, ou comunicação externa) | Comunicar internamente ao DPO sem demora |
| Encarregado (DPO — Christopher Tominaga) | Classificar risco, coordenar contenção, decidir comunicação à ANPD e ao titular, manter registro |
| Controlador (Jump Label) | Aprovar comunicação externa e medidas de mitigação |
| Operador envolvido (Anthropic, Cloudflare R2, Railway, etc.) | Apoiar contenção e fornecer informações conforme o contrato |

**Fluxo de tratamento (prazos contados em horas corridas a partir do conhecimento pelo controlador):**

1. **T+0h — Detecção.** Comunicação interna imediata ao DPO por qualquer canal disponível (e-mail, mensagem direta, ligação).
2. **Até T+24h — Classificação preliminar.** O DPO registra o incidente em planilha controlada (campos mínimos: data e hora de detecção, dados envolvidos, número estimado de titulares, vetor, contenção inicial, classificação de risco).
3. **Até T+24h — Contenção.** Medidas técnicas para interromper a exposição (rotacionar credenciais, isolar operador, cortar acesso, restaurar a partir de backup). Concorrente com a classificação quando aplicável.
4. **Até T+48h — Comunicação à ANPD.** Se o risco for relevante (art. 48 §3 LGPD), o DPO comunica à ANPD pelo canal oficial vigente. Conteúdo mínimo: descrição da natureza dos dados, titulares afetados, medidas de segurança em uso, riscos relacionados, medidas adotadas para reverter os efeitos.
5. **Até T+48h — Comunicação aos titulares.** Se houver risco relevante (art. 48 §1), o DPO comunica os titulares afetados pelo canal de e-mail registrado, em linguagem acessível.
6. **Pós-incidente — Investigação e medidas corretivas.** O DPO produz relatório final em até 30 dias, com causa raiz, dano efetivo, medidas adotadas e recomendações estruturais.
7. **Retenção do registro.** O registro do incidente e do tratamento dado é retido por 5 anos a partir do encerramento da investigação.

A omissão da comunicação quando devida sujeita o controlador às sanções do art. 52 LGPD.

---

## §8. Cláusulas obrigatórias com operadores

Antes da abertura do tratamento com cada operador, e antes do piloto Bradesco enviar dados reais, são verificadas as seguintes condições:

- **Anthropic:** opção contratual ou de painel para opt-out de uso dos dados em treinamento de modelos confirmada e ativada na conta corporativa.
- **OpenAI:** Data Controls com "Improve the model for everyone" desativado na conta corporativa.
- **Cloudflare R2:** transporte sob TLS e criptografia em repouso ativada por padrão; chaves de acesso restritas ao backend.
- **Railway:** conexão sob TLS, isolamento de tenant verificado.
- **Resend:** transporte sob TLS; verificar política de retenção do conteúdo de e-mail enviado e ajustar contrato se houver retenção indevida.

O operador da máquina worker é treinado para verificar essas configurações em cada conta corporativa antes de habilitar tratamento de produção. Falhas observadas são tratadas como incidente (§7).

---

## §9. Trânsito e segurança

- Toda comunicação entre componentes do Sistema, e entre o Sistema e operadores, ocorre sob TLS.
- O workspace temporário do worker (filesystem local) é criado com permissões 0700, restrito ao usuário do processo, e limpo automaticamente após 7 dias.
- Credenciais de acesso a operadores são geridas via variáveis de ambiente em ambiente de hospedagem; não há credencial em código-fonte versionado.
- Backups do PostgreSQL são realizados pelo provedor (Railway) com retenção de 30 dias.

Detalhes adicionais de arquitetura técnica estão em [`docs/arquitetura.md`](arquitetura.md).

---

## §10. Débitos abertos para v1.1

Os itens abaixo foram identificados durante a redação desta versão v1.0 e ficam registrados como débitos formais a serem tratados antes da v1.1 ou em sua redação:

- **F5.7.X — Anonimização de texto livre.** Em v1.0 a eliminação anonimiza apenas metadados estruturados da entidade `User`. Texto livre em descrições de risco, pendência, plano de ação e seções narrativas do relatório pode conter menções nominais ao titular; sua retenção é justificada como histórico do projeto entregue ao cliente sob o art. 16 II LGPD. Em v1.1 será implementada varredura programática de texto livre com redaction explícita ou pseudonimização.
- **F5.7.Y — Formulário web público para titulares externos.** Em v1.0 o canal para titulares sem conta é o e-mail dirigido ao DPO, com registro manual no painel administrativo. Em v1.1 será adicionado um formulário web público que cria o `DataProcessingRecord` automaticamente.
- **F5.7.Z — Provisionamento do alias dedicado para canal LGPD.** O canal externo desta v1.0 opera com o e-mail corporativo `anderson.argentoni@jumplabel.com.br` (Anderson Argentoni atua como receptor operacional do canal LGPD, sob coordenação do DPO designado). O provisionamento do alias dedicado `lgpd@jumplabel.com.br` no Workspace e a substituição subsequente do canal documentado são débito v1.1.
- **Revisão jurídica externa.** Esta v1.0 é texto técnico assinado pelo DPO designado para fins de piloto Bradesco. A revisão jurídica externa é pré-requisito para v1.1 e é registrada como dependência explícita.
- **Spec v3.1 §9.5 — modelagem do `DataProcessingRecord`.** A spec lista `processing_purpose`, `legal_basis` e `retention_period` como atributos do `DataProcessingRecord`. A redação desta v1.0 reconhece que esses atributos pertencem ao Registro de Atividades de Tratamento (`docs/rat.md`), não ao log de pedido de titular. Correção da spec é débito da consolidação v3.2.

---

## §11. Histórico de versões

| Versão | Data | Mudanças |
|---|---|---|
| v1.0 piloto Bradesco | 2026-05-14 | Versão inicial. Assinada pelo DPO Christopher Tominaga. Revisão jurídica externa pendente para v1.1. |
