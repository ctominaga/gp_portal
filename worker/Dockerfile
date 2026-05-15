###############################################################################
# Worker Dockerfile — STUB para F6 (worker em container).
#
# Status atual (F5.9a): NÃO USAR EM PRODUÇÃO.
#
# Justificativa: o worker depende do CLI Claude Code nativo no Linux, que
# requer login OAuth interativo persistente (`~/.claude/.credentials.json`).
# Em ambiente headless container persistente, o OAuth Team é frágil — Anthropic
# não publica recipe oficial nem garante longevidade do token de sessão.
#
# F5.6a.Y decidiu: piloto roda worker LOCAL no WSL Linux do Christopher.
# F5.9 mantém essa decisão. railway.json não inclui worker service.
#
# Este Dockerfile fica como ponto de partida para a F6 (rearquitetura para
# usar Anthropic Python SDK em container — vide ADR F5.9 abertura). Quando
# F6 começar, esta Image precisa: (a) trocar `jump_agent_runner` ClaudeHeadless
# por SDK direto, (b) injetar API key via env var, (c) usar Anthropic Python SDK
# normal (sem CLI), (d) revalidar smoke F2.8 contra a proposta Bradesco.
###############################################################################

FROM python:3.12-slim AS placeholder

LABEL maintainer="Jump Label DPO <christopher.tominaga@jumplabel.com.br>"
LABEL status="stub-for-f6"
LABEL warning="worker roda local conforme F5.6a.Y; este Dockerfile NAO eh usado em F5.9"

WORKDIR /app

# Fail-fast se alguém tentar rodar isso em produção sem rever a arquitetura.
ENTRYPOINT ["sh", "-c", "echo 'ERROR: worker em container requer F6 — vide worker/Dockerfile' >&2; exit 1"]
