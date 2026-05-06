# jump-agent-runner

Biblioteca Python que executa tarefas de IA invocando Claude Code (`claude -p`) e Codex CLI (`codex exec`) em uma máquina Windows local com WSL2.

Cada engine tem duas rotas: **headless** (chamada direta) e **broker** (sessão `tmux` persistente em WSL2). Headless é prioridade; broker é fallback automático para login expirado / quota / detecção de modo interativo. Se o engine primário falhar de forma definitiva, o runner tenta o secundário com contexto.

## Princípios

1. Headless é sempre prioridade. Broker é fallback.
2. **API Key nunca é usada.** A biblioteca não expõe essa rota.
3. Resultado só é aceito via arquivo JSON canônico (não stdout, não prosa, não sentinel sozinho).
4. Falhas preservam trabalho parcial — próxima tentativa recebe contexto.
5. Logs estruturados permitem auditar todo caminho de decisão.

## Status de implementação

- F0: scaffolding e `pyproject.toml` ✓
- F1 / S0: tipos públicos, `ArtifactValidator`, `Observer` (próximo)
- F1 / S1: `ClaudeHeadlessRoute`
- F1 / S2: `CodexHeadlessRoute`
- F1 / S3: `WSLTmuxBroker`
- F1 / S4-S5: `ClaudeProvider`, `CodexProvider`
- F1 / S6: `AgentRunner` com fallback entre engines
- F1 / S7: CLI + smoke test

## Instalação

```bash
pip install -e ".[dev]"
```

## CLI

Após instalar, `jump-runner` fica disponível:

```bash
jump-runner login-confirm claude   # confirma login Claude e remove sentinela
jump-runner login-confirm codex    # idem para Codex
jump-runner smoke                  # roda tarefa simples end-to-end
```

## Logs

Logs JSONL ficam em `~/.jump-runner/logs/{date}.jsonl`.
