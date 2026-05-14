# Briefings de sub-fase para sessões Claude Code

Cada arquivo aqui é um **template de prompt inicial** para começar uma sub-fase
em uma sessão nova do Claude Code (após `/clear` ou novo chat). O Claude entra
na sessão sem o contexto da conversa anterior — mas com a [memória
persistente](../../../.claude/projects/c--Users-chris-OneDrive-Documentos-VSCode-Jump-GP-portal/memory/MEMORY.md)
do projeto carregada automaticamente.

## Como usar

1. Abra o template da sub-fase que vai iniciar (ex: `f57-lgpd.md`).
2. Procure por `[RESPONDA AQUI]` — substitua pelos valores ou decisões do momento.
3. Cole o conteúdo inteiro como **primeiro prompt** da nova sessão.
4. O Claude vai começar por **PASSO 1 — Inventário** e parar para você aprovar
   o plano antes de codar.

## Convenções

- Todo template inclui **PASSO 1 — Inventário** que força o Claude a parar e
  propor plano antes de mexer em código. Espelha o feedback memory "construção
  em fases com pausas".
- **DECISÕES JÁ TOMADAS** lista o que o Claude NÃO precisa perguntar — economiza
  rodadas no início.
- **ATENÇÃO ESPECIAL** captura armadilhas conhecidas da sub-fase (encoding,
  dependências externas, limites legais, etc.).
- **Commits sugeridos** dá a estrutura típica de 4 commits — Claude pode
  ajustar, mas o esqueleto economiza decisões de granularidade.

## Templates disponíveis

| Arquivo | Sub-fase | Estado |
|---|---|---|
| `f57-lgpd.md` | F5.7 — LGPD (`lgpd.md` + endpoints `/me/data-*` + admin PMO) | Pronto |
