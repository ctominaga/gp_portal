# Briefing inicial — F5.7 LGPD

> **Como usar:** copie tudo abaixo da linha `===== INÍCIO DO PROMPT =====` até `===== FIM DO PROMPT =====` (sem incluir os delimitadores). Substitua os marcadores `[RESPONDA AQUI]` pelas decisões do momento. Cole como primeiro prompt em uma sessão Claude Code nova.

---

```
===== INÍCIO DO PROMPT =====

F5.6 (a+b) fechada com débito K zerado. Próximo: F5.7 LGPD
(spec v3.1 §12, governança de dados). Modo: híbrido — você
produz o texto técnico de docs/lgpd.md como rascunho, eu (DPO
designado) reviso e assino; você implementa os endpoints e
testes; checkpoint humano antes do commit final do texto LGPD.

==== F5.7 — LGPD (governança completa) ====

DECISÕES JÁ TOMADAS (não precisa pedir):

- Eu (Christopher Tominaga) sou DPO designado. Email:
  christopher.tominaga@jumplabel.com.br.
- Encarregado/controlador da Jump Label: a própria Jump Label
  (empresa, não pessoa física).
- Operadores conhecidos a listar no docs/lgpd.md:
    * Anthropic (Claude — agente leitor + agente cruzado)
    * OpenAI (Codex — fallback do agente, em pausa até URL
      installer voltar)
    * Cloudflare/R2 (storage de propostas e artefatos)
    * Railway (host backend + frontend + Postgres + Redis,
      a partir de F5.9)
    * Resend (email transacional)
  Se algum mudou desde 2026-05-14, pergunte antes de listar.
- SLA legal de resposta a titulares: 15 dias úteis (LGPD art. 19).
- Bases legais primárias: execução de contrato (art. 7º V) para
  dados do titular cliente; legítimo interesse (art. 7º IX) para
  logs operacionais; consentimento (art. 7º I) para email opcional
  de marketing — confirme se vamos ter esse caso ou se pulamos.

DECISÃO PENDENTE #3 do plano F5 (responda antes de começar):

   [RESPONDA AQUI]
   Opções:
   (a) Texto técnico produzido por você vale como versão piloto.
       Eu assino como DPO. Cabeçalho do lgpd.md diz "v1.0 piloto
       Bradesco — revisão jurídica externa pendente para v1.1".
   (b) Texto técnico vai com cabeçalho "RASCUNHO TÉCNICO — pendente
       revisão jurídica externa". Sem assinatura DPO. Endpoints
       e testes vão como costume; só o documento aguarda.
   (c) Outro caminho — descreva.

PASSO 1 — Inventário do estado atual

Verifique:

1. backend/app/models/domain.py — quais campos tem o modelo
   DataProcessingRecord (mencionado em §9.5 da spec). Existe? Já
   tem subject_id, processing_purpose, legal_basis, retention_
   period? Quais enums estão definidos?
2. backend/app/api/v1/ — endpoints já em /me/* (auth, profile)?
   Há rota /me/data-export ou /me/data-deletion-request stub?
3. docs/ — existe algum docs/lgpd.md, docs/privacidade.md,
   ou doc sobre retenção/RAT/RPS?
4. spec v3.1 §12 — quais sub-itens precisamos cobrir (lista
   completa). Cite por número de linha onde estiver.
5. Frontend: existe alguma tela /admin/data-requests ou similar
   pra PMO processar os pedidos de titular?

PARE após inventário e proponha plano + lista de coisas que
preciso responder (Q1/Q2/...) antes de você tocar em código.

PASSO 2 — Plano (após meu OK do inventário)

Esperado (subdivisão do fase-5-plano.md §F5.7):

A) docs/lgpd.md (~15k):
   - Cabeçalho com versão + data + status (rascunho/piloto/aprovado)
   - Controlador (Jump Label) + Encarregado (Christopher Tominaga
     DPO) + dados de contato pra titular
   - Inventário de operadores (5+ acima) com finalidade de cada um
   - Bases legais por categoria de dado
   - Retenção: tabela com Categoria × Tempo × Gatilho de exclusão
   - RAT (Relatório de Atividades de Tratamento) resumido
   - Procedimento de incidentes (1 página, papéis claros)
   - Direitos do titular + canal de atendimento (formulário web
     + email do DPO)

B) Backend — endpoint GET /me/data-export (~15k):
   - Service backend/app/services/data_export_service.py
   - Coleta todos os dados associados ao User autenticado:
     próprio User, Projects (como GP ou CLIENT), Reports, Approvals
     vinculadas, AgentRunLog dos Projects, ScopeChanges, etc.
   - Empacota em ZIP com JSON estruturado + README.txt explicando
     o conteúdo.
   - Endpoint retorna o ZIP via streaming. Log no DataProcessingRecord.
   - Testes pytest: smoke (zip não-vazio), conteúdo (cobre todas
     as entidades), autenticação (só o próprio User).

C) Backend — POST /me/data-deletion-request (~10k):
   - Cria DataProcessingRecord com request_type=DELETION,
     status=PENDING, SLA 15 dias úteis.
   - Endpoint admin GET /admin/data-requests (role PMO).
   - Endpoint admin POST /admin/data-requests/{id}/fulfill que
     executa a exclusão (hard delete ou anonymize — decisão técnica
     vai virar Q1 ou Q2 do plano).
   - Notificação ao DPO via Resend quando request é criado.
   - Testes pytest.

D) Frontend — tela mínima PMO (~5k):
   - Página /admin/data-requests com lista + filtros + ação
     "Atender" que dispara confirm modal + POST /fulfill.
   - Vitest cobrindo a tela.

E) Testes E2E + atualizações de docs (~5k):
   - conformidade-v3.1.md: linha §12 marcada ✅
   - fase-5-progresso.md: seção F5.7 fechada
   - decisoes.md: ADR de fechamento

Decisões esperadas a serem propostas como Q1/Q2/Q3 (a confirmar
pela leitura do código):

   Q1 — Exclusão: hard delete vs anonymize?
   Q2 — Export inclui dados de Projects em que User é CLIENT
        (visão limitada) ou só onde é GP/owner?
   Q3 — Notificação de criação de request: só ao DPO ou também
        ao titular como recibo?

PASSO 3 — Execução (modo híbrido)

Checkpoint humano #1: ao fim do PASSO 1, ver inventário + plano
Q1/Q2/Q3 antes de seguir.

Checkpoint humano #2: rascunho do docs/lgpd.md pronto, antes de
commitar. Quero ler o texto inteiro.

Checkpoint humano #3 (opcional): após backend implementado,
demonstrar o /me/data-export contra meu user em ambiente local
e revisar o ZIP gerado antes do commit final.

PASSO 4 — Commits

Estrutura sugerida:

Commit 1: docs(lgpd): F5.7 docs/lgpd.md v1.0 piloto
- Cabeçalho + 8 seções (controlador, encarregado, operadores,
  bases legais, retenção, RAT, incidentes, direitos do titular)
- Tabela de retenção
- ADR em decisoes.md sobre decisão #3 e Q1/Q2/Q3

Commit 2: feat(backend): F5.7 GET /me/data-export
- Service + endpoint + testes

Commit 3: feat(backend): F5.7 POST /me/data-deletion-request + admin
- Endpoints titular + admin + notificação + testes

Commit 4: feat(frontend): F5.7 tela /admin/data-requests + vitest

Commit 5: test+docs: F5.7 encerramento
- E2E spec
- conformidade-v3.1.md ✅
- fase-5-progresso.md
- ADR fechamento

==== ATENÇÃO ESPECIAL ====

A. Linguagem do docs/lgpd.md mais formal que o resto do projeto
   — referenciar artigos da LGPD com número (art. 7º, art. 19,
   art. 48 incidentes). Manter tom técnico mas com precisão
   jurídica. Evitar marketing ("nossa missão é proteger seus
   dados") e foco em fatos.

B. Procedimento de incidentes precisa caber em 1 página da
   versão impressa do docs/lgpd.md. Estrutura mínima: quem
   detecta, quem comunica internamente (DPO), prazo da
   comunicação a ANPD (48h após conhecimento se houver risco
   relevante), formato do registro, retenção do registro.

C. Endpoint /me/data-export pode incluir dados de Projects em
   que User é CLIENT — esses dados são da Jump Label como
   controlador, MAS o titular (CLIENT) tem direito de acesso
   aos próprios dados pessoais que estejam lá (ex: nome, email,
   identificação da empresa cliente). NÃO incluir dados de
   OUTROS titulares (ex: outros CLIENTs da Jump). Service tem
   que filtrar isso cirurgicamente.

D. NOPASSWD sudoers temp não está mais ativo (revogado em
   2026-05-14 após F5.6a). Se precisar de privilégio elevado
   pra alguma migração, pedir explicitamente.

E. Auto-update do Claude Code CLI continua sem pin de versão.
   Se durante a sessão aparecer comportamento estranho do agente
   (ex: novos flags, mudança de defaults), verificar versão com
   `wsl -d Ubuntu-22.04 -- claude --version` e cruzar com o que
   está documentado no dev_notes.md.

==== INICIE COM PASSO 1 (INVENTÁRIO) ====

Após inventário, PARE e proponha plano + Q1/Q2/Q3. Aguardo OK
antes de tocar em código.

NÃO inicie escrita do docs/lgpd.md antes do plano ser aprovado.
NÃO tente sugerir texto jurídico antes do meu OK na decisão #3
(que define se o documento sai como piloto assinado ou rascunho
pendente de revisão).

===== FIM DO PROMPT =====
```
