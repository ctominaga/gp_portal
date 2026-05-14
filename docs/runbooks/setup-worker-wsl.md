# Runbook — Setup limpo da máquina worker (WSL2 + Ubuntu-22.04)

**Última revisão:** 2026-05-13 (F5.6a)
**Aplica-se a:** máquina Windows 10/11 que vai rodar o processo `jump-worker`.
**Objetivo:** instalar `claude` e `codex` **nativamente no Linux** (WSL2) com tudo idempotente, login interativo persistente em `tmux`, e ambiente pronto pra `jump-runner smoke` retornar verde.

> **Quem chegou aqui sem contexto:** este runbook substitui o setup descrito no `worker/scripts/setup-windows.ps1` quando você quer entender o "porquê" de cada passo. O script PowerShell executa esses mesmos passos automaticamente, mas em recuperação ou troubleshooting você quase sempre vai querer rodar manualmente.

---

## 0. Por que esse setup específico?

O agente leitor (`jump_agent_runner`) invoca `claude -p` em modo headless. Em sessão anterior do projeto (ADR `2026-05-11 — F2.8 adiado para F5`) foi observado que `claude` instalado no Windows e acessado via mount WSL (`/mnt/c/Users/.../npm/claude`) sofre de bug onde **login interativo reporta sucesso mas invocação headless retorna `Not logged in`**. A solução durável é instalar `@anthropic-ai/claude-code` **diretamente no Linux do WSL**, com o usuário do WSL como dono dos arquivos de credencial em `~/.claude/`.

Pré-requisitos da máquina:

- Windows 10 versão 2004+ ou Windows 11
- Conta Windows com privilégio de administrador (somente para o passo 1, instalação inicial do WSL)
- Acesso à internet com saída pra `*.anthropic.com`, `*.openai.com`, `deb.nodesource.com`, `*.ubuntu.com`
- ~5 GB livres em disco (Ubuntu-22.04 + Node + binários)

Tempo total estimado: **30–45 minutos** (10 min instalação + 5 min login claude + 5 min login codex + buffer pra bugs).

---

## 1. Garantir WSL2 + distro Ubuntu-22.04

**Verifica:** em PowerShell normal, `wsl --list --verbose`.

- Se `Ubuntu-22.04` aparece com `STATE=Running` ou `Stopped` e `VERSION=2`: ✅ pular para o passo 2.
- Se ausente ou em VERSION 1: prosseguir.

**Faz** (PowerShell **elevado**):

```powershell
wsl --install -d Ubuntu-22.04
# Se este é o primeiro WSL da máquina, ele instala o kernel WSL2 também.
# Reboote a máquina após o `--install` completar (Windows pede explicitamente).
```

**Sanity após reboot:** primeira vez que você roda `wsl -d Ubuntu-22.04` o Ubuntu pede para criar um usuário e senha. **Anote a senha** — ela é usada para `sudo` nos passos seguintes.

```powershell
wsl --list --verbose                 # Ubuntu-22.04 deve aparecer
wsl --set-default Ubuntu-22.04       # default da máquina
wsl --update                         # garante kernel WSL atualizado
```

---

## 2. Habilitar `systemd` no WSL

**Por quê:** sem `systemd`, vários serviços comuns no Linux (timers, cron, futuros daemons) não rodam. Embora F5.6a não dependa diretamente, ele é um vetor de bugs futuros e é trivial de habilitar agora.

**Verifica** (dentro do WSL):

```bash
grep -q "systemd=true" /etc/wsl.conf 2>/dev/null && echo "OK systemd já habilitado" || echo "FALTA habilitar systemd"
```

**Faz** (só se faltar):

```bash
sudo tee -a /etc/wsl.conf <<'EOF'

[boot]
systemd=true
EOF
```

**Aplica:** em PowerShell **fora** do WSL:

```powershell
wsl --shutdown
# Aguarda 8 segundos antes de reabrir (WSL precisa terminar processos).
# Reabrir: wsl -d Ubuntu-22.04
```

**Sanity** (de volta no WSL):

```bash
systemctl --version    # deve imprimir 'systemd 249' ou mais recente
ps -p 1 -o comm=       # deve imprimir 'systemd' (não 'init')
```

---

## 3. Pacotes do sistema (apt)

**Verifica & faz** (idempotente — `apt install` não reinstala o que já está):

```bash
sudo apt-get update -y
sudo apt-get install -y tmux curl jq python3 python3-pip ca-certificates
```

**Sanity:**

```bash
tmux -V        # esperado tmux 3.2 ou superior
jq --version   # qualquer versão recente
```

---

## 4. Node 20 LTS via NodeSource (não via apt)

**Por quê:** o pacote `nodejs` do apt do Ubuntu-22.04 entrega Node 12, que é antigo demais pra `@anthropic-ai/claude-code`. NodeSource publica binários atualizados.

**Verifica:**

```bash
NODE_MAJOR=$(node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' | grep -E '^[0-9]+$' || echo 0)
if [ "$NODE_MAJOR" -ge 18 ]; then
  echo "OK Node $(node --version) já é >= 18"
else
  echo "FALTA Node 20 (atual: ${NODE_MAJOR:-ausente})"
fi
```

**Faz** (só se faltar) — versão manual sem `bash -` root:

```bash
sudo apt-get install -y curl gnupg ca-certificates
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | sudo gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/nodesource.gpg
echo "deb https://deb.nodesource.com/node_20.x nodistro main" \
  | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
sudo apt-get update -y
sudo apt-get install -y nodejs
```

> 💡 O script `setup-windows.ps1` faz exatamente isso. A alternativa em "uma linha" `curl ... | sudo -E bash -` (instalador oficial NodeSource) também funciona, mas executa um shell root vindo da internet — preferimos o caminho manual em qualquer setup automatizado.

**Sanity:**

```bash
node --version    # esperado v20.x.x
npm --version     # esperado 10.x.x
which node        # esperado /usr/bin/node (não /mnt/c/...)
```

---

## 5. `npm prefix` para `~/.npm-global` (instalar globais sem sudo)

**Por quê:** `npm install -g` por padrão tenta gravar em `/usr/lib/node_modules` (precisa sudo). Configurando prefix pra `~/.npm-global` evita sudo e mantém os binários no home do usuário do WSL — fácil de inspecionar, fácil de remover.

**Verifica & faz** (idempotente):

```bash
mkdir -p ~/.npm-global
npm config set prefix "$HOME/.npm-global"
```

**PATH em `~/.bashrc`** (precisa preceder `/mnt/c/.../npm` pra que `which claude` encontre o nativo, não o mount Windows):

```bash
LINE='export PATH="$HOME/.npm-global/bin:$PATH"'
grep -qxF "$LINE" ~/.bashrc || echo "$LINE" >> ~/.bashrc
# Aplica na sessão atual também:
export PATH="$HOME/.npm-global/bin:$PATH"
```

**Sanity:**

```bash
echo "$PATH" | tr ':' '\n' | head -3
# Primeira linha deve ser /home/<user>/.npm-global/bin
```

---

## 6. Claude Code CLI (`@anthropic-ai/claude-code`) **nativamente no Linux**

**Verifica:**

```bash
[ -f "$HOME/.npm-global/bin/claude" ] && echo "OK claude nativo já presente" || echo "FALTA instalar claude"
which claude
# which DEVE retornar /home/<user>/.npm-global/bin/claude
# Se retornar /mnt/c/..., o PATH ainda não tá certo — volte ao passo 5
```

**Faz** (só se faltar):

```bash
npm install -g @anthropic-ai/claude-code
hash -r    # força bash a re-resolver claude no novo path
```

**Sanity:**

```bash
which claude     # /home/<user>/.npm-global/bin/claude
claude --version # imprime versão
```

> ⚠️ Se `which claude` ainda apontar pra `/mnt/c/...` depois disso, abra um shell novo (`exec bash`) ou veja "Solução de problemas → claude continua resolvendo pra Windows".

---

## 7. Codex CLI (OpenAI)

**Verifica:**

```bash
[ -f "$HOME/.codex/bin/codex" ] && echo "OK codex já presente" || echo "FALTA instalar codex"
```

**Faz** (só se faltar) — com verificação preventiva da URL antes de baixar (débito F5.6a.X):

```bash
# 1) HEAD request — confirma que a URL responde 200 antes de gastar tempo no download.
#    Se 4xx/5xx, aborta e vai pra "Solução de problemas" abaixo (Plano B 1/2/3).
curl -I -fsS https://codex.openai.com/install.sh

# 2) Se OK, baixa e executa
curl -fsSL https://codex.openai.com/install.sh | sh
```

> A URL `https://codex.openai.com/install.sh` é a oficial em 2026-05. **A OpenAI não publica checksum fixo** — o script é regenerado conforme versões saem. Se preferir auditar, baixe e inspecione antes:
>
> ```bash
> curl -fsSL https://codex.openai.com/install.sh -o /tmp/codex-install.sh
> less /tmp/codex-install.sh    # inspeção
> sh /tmp/codex-install.sh
> ```
>
> Se a URL estiver fora do ar ou retornar 404, ver "Solução de problemas → codex installer URL mudou".

**PATH do codex em `~/.bashrc`** (o instalador adiciona uma linha; verifique):

```bash
LINE='export PATH="$HOME/.codex/bin:$PATH"'
grep -qxF "$LINE" ~/.bashrc || echo "$LINE" >> ~/.bashrc
export PATH="$HOME/.codex/bin:$PATH"
```

**Sanity:**

```bash
which codex      # /home/<user>/.codex/bin/codex
codex --version  # imprime versão
```

---

## 8. Sessões `tmux` persistentes

**Por quê:** o `jump_agent_runner` usa o `WSLTmuxBroker` como fallback do modo headless. Quando o headless falha por `LOGIN_REQUIRED` ou `INTERACTIVE_MODE_DETECTED`, o broker tenta executar dentro de sessões `tmux` dedicadas onde o login interativo foi feito a partir do `tmux attach` (browser do Windows abre via WSLg). Sem essas sessões pré-criadas, o broker reporta `BROKER_UNAVAILABLE`.

**Verifica:**

```bash
tmux has-session -t project-claude 2>/dev/null && echo "OK sessão project-claude existe" || echo "FALTA project-claude"
tmux has-session -t project-codex  2>/dev/null && echo "OK sessão project-codex existe"  || echo "FALTA project-codex"
```

**Faz** (só as que faltarem):

```bash
tmux has-session -t project-claude 2>/dev/null || tmux new-session -d -s project-claude
tmux has-session -t project-codex  2>/dev/null || tmux new-session -d -s project-codex
```

**Sanity:**

```bash
tmux list-sessions
# Esperado 2 linhas: project-claude e project-codex
```

> 💡 Sessões `tmux` morrem se o WSL desligar completamente (`wsl --shutdown`). O `setup-windows.ps1` recria automaticamente em re-execução. Login feito dentro da sessão **persiste em `~/.claude/`** mesmo após sessão morrer — só refaça login se as credenciais expirarem.

---

## 9. Login interativo do Claude

**Faz** (terminal Windows, PowerShell normal):

```powershell
wsl -d Ubuntu-22.04 -- tmux attach -t project-claude
```

Você fica anexado à sessão (terminal vira o do tmux). Dentro dela:

```bash
claude /login
```

Claude imprime uma URL. **WSLg abre o browser do Windows automaticamente**; se não abrir, copie a URL e cole manualmente. Complete o fluxo no browser (autorize o acesso). De volta no terminal, Claude reporta sucesso.

**Desanexa da sessão tmux** (mantém ela viva em background):

- Pressione **`Ctrl+B`** seguido de **`D`** (modo prefix-then-letter do tmux).

**Sanity** (fora do tmux):

```bash
wsl -d Ubuntu-22.04 -- bash -lc "claude -p 'responda apenas: ok' --bare --output-format json"
```

A resposta JSON deve ter `"is_error": false`. Se vier `"is_error": true` com mensagem "Not logged in", consulte "Solução de problemas → claude retorna Not logged in".

---

## 10. Login interativo do Codex

**Faz** (PowerShell):

```powershell
wsl -d Ubuntu-22.04 -- tmux attach -t project-codex
```

Dentro do tmux:

```bash
codex login
```

Mesmo fluxo: URL imprimida → browser abre via WSLg → autoriza → volta pro terminal.

**Desanexa** com `Ctrl+B D`.

**Sanity:**

```bash
wsl -d Ubuntu-22.04 -- bash -lc "codex exec --skip-git-repo-check --json 'responda apenas: ok'"
```

Esperado JSON sem erro de autenticação.

---

## 11. Smoke test do `jump-agent-runner`

Esse é o teste E2E que valida que todos os passos anteriores realmente funcionaram juntos.

**Pré-req:** o pacote `jump_agent_runner` precisa estar instalado num venv Python no Windows (não no WSL — o CLI `jump-runner` roda no Windows mas invoca WSL por dentro).

```powershell
# No Windows, dentro de jump-report\worker\:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ..\jump_agent_runner
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\jump-runner.exe smoke
```

**Esperado:** linha final do tipo:

```
OK engine=claude route=headless duration=5.2s attempts=1
artifact: {"ok": true}
```

Se falhar com `engine=codex route=broker` (deu fallback completo), funcionou mas o headless do Claude está com problema — vá para "Solução de problemas".

---

## 11.5. Python 3.12 + venv do worker no WSL Linux (F5.6b)

**Por quê:** o `jump-worker` (e portanto `jump_agent_runner`) precisa rodar **dentro do WSL Linux** pra que `claude` resolvido pelo `subprocess` aponte para o binário nativo (`~/.npm-global/bin/claude`) — caso contrário cai no bug `Not logged in` do ADR 2026-05-11. Ubuntu 22.04 traz Python 3.10; `pyproject.toml` do worker exige `>=3.12`. Usamos `uv` (toolchain manager) instalado **em userspace via `pip --user`** (não `curl|sh` — mesma decisão de segurança do F5.6a.X NodeSource).

**Verifica:**

```bash
[ -f ~/.local/bin/uv ] && echo "OK uv" || echo "FALTA uv"
[ -f ~/.jump-runner/.venv-worker/bin/python ] && echo "OK venv" || echo "FALTA venv"
[ -f ~/.jump-runner/.venv-worker/bin/jump-worker ] && echo "OK jump-worker" || echo "FALTA install"
```

**Faz** (só o que faltar):

```bash
# 1) uv via pip --user
python3 -m pip install --user uv

# Garante ~/.local/bin no PATH da sessão (Ubuntu default .profile já inclui)
export PATH="$HOME/.local/bin:$PATH"

# 2) Python 3.12 (uv baixa pré-compilado em ~/.local/share/uv/python/)
uv python install 3.12

# 3) Venv isolado em ~/.jump-runner/.venv-worker
mkdir -p ~/.jump-runner
uv venv --python 3.12 ~/.jump-runner/.venv-worker

# 4) jump_agent_runner + worker editable. Use o path do repo via /mnt/c/...
REPO=/mnt/c/Users/<user>/.../jump-report   # ajuste para sua máquina
uv pip install \
  --python ~/.jump-runner/.venv-worker/bin/python \
  -e "$REPO/jump_agent_runner" \
  -e "$REPO/worker"
```

**Sanity:**

```bash
~/.jump-runner/.venv-worker/bin/python --version    # Python 3.12.x
~/.jump-runner/.venv-worker/bin/jump-runner smoke --help
```

> 💡 O `setup-windows.ps1` automatiza esses passos (3.11–3.14) usando `wsl --cd <repoRoot>` para que `$PWD` aponte pra raiz do monorepo dentro do bash. Manual fica como documentação e troubleshooting.

## 12. Validação final consolidada

Comando único que confirma todo o setup:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc '
echo "=== Versões ==="
echo "tmux:   $(tmux -V)"
echo "node:   $(node --version)"
echo "npm:    $(npm --version)"
echo "claude: $(claude --version 2>/dev/null | head -1)"
echo "codex:  $(codex --version 2>/dev/null | head -1)"
echo ""
echo "=== Caminhos (devem ser /home/..., NÃO /mnt/c/...) ==="
echo "which claude: $(which claude)"
echo "which codex:  $(which codex)"
echo ""
echo "=== Sessões tmux ==="
tmux list-sessions 2>/dev/null || echo "nenhuma"
echo ""
echo "=== Credenciais (existência, NÃO conteúdo) ==="
[ -f ~/.claude/.credentials.json ]    && echo "OK ~/.claude/.credentials.json existe" || echo "FALTA login claude"
[ -d ~/.codex ]                       && echo "OK ~/.codex/ existe"                   || echo "FALTA login codex"
'
```

Tudo verde = pronto para rodar o `jump-worker`.

---

## Solução de problemas

### `claude` retorna `Not logged in` apesar de `/login` ter dado sucesso (mount cross-OS)

**Causa:** `which claude` ainda aponta pra `/mnt/c/Users/chris/AppData/Roaming/npm/claude` (o claude instalado no Windows, não o nativo). O fluxo `/login` salvou credenciais em `~/.claude/` do Linux, mas o binary lê de `%APPDATA%\claude\` do Windows (caminhos diferentes).

**Diagnóstico:**

```bash
which claude
# Se vier /mnt/c/..., o PATH não está priorizando o ~/.npm-global/bin
```

**Conserto:**

```bash
# Confirma que ~/.npm-global/bin tá no início do PATH
head -3 <(echo "$PATH" | tr ':' '\n')

# Se não tiver: refaz o passo 5
LINE='export PATH="$HOME/.npm-global/bin:$PATH"'
grep -qxF "$LINE" ~/.bashrc || echo "$LINE" >> ~/.bashrc
exec bash    # recarrega shell

which claude    # agora deve ser /home/<user>/.npm-global/bin/claude
```

Se mesmo assim `which` aponta pro mount, é porque `~/.npm-global/bin/claude` não existe (passo 6 não rodou). Reinstale: `npm install -g @anthropic-ai/claude-code`.

### Sessão `tmux` morre / desaparece

**Causa típica:** `wsl --shutdown` foi executado em algum momento (próprio Windows pode disparar isso durante reboot ou updates). Sessões `tmux` são processos do WSL — quando o WSL morre, as sessões morrem junto.

**Conserto:** apenas recriar — login dentro de `~/.claude/` e `~/.codex/` persiste em disco, então não precisa relogin.

```bash
tmux has-session -t project-claude 2>/dev/null || tmux new-session -d -s project-claude
tmux has-session -t project-codex  2>/dev/null || tmux new-session -d -s project-codex
```

> 💡 Pra automatizar a recriação no boot do WSL: criar serviço `systemd --user` que dispara as duas sessões. Não está no escopo de F5.6a; deixar manual por enquanto.

### Auto-update do Claude Code quebra o `PATH` ou o binary

**Sintoma:** `claude --version` reporta versão nova mas qualquer chamada retorna erro estranho. Acontece raramente quando o auto-update do Claude reinstala em local diferente do `npm prefix`.

**Conserto:**

```bash
# Reinstala forçando o prefix
npm uninstall -g @anthropic-ai/claude-code 2>/dev/null
npm install -g @anthropic-ai/claude-code
hash -r
which claude
```

Se persistir, pin de versão (substituir `X.Y.Z` pela versão sabidamente boa):

```bash
npm install -g @anthropic-ai/claude-code@X.Y.Z
```

### Codex installer URL mudou (404 em `https://codex.openai.com/install.sh`)

**Plano B 1 — npm package:** se a OpenAI publicou (ou voltou a publicar) o pacote npm `@openai/codex`:

```bash
npm install -g @openai/codex
which codex
```

**Plano B 2 — releases do GitHub:** a OpenAI mantém o repo `openai/codex` no GitHub. Em "Releases" há binários pré-compilados pra Linux x86_64. Baixa, extrai pra `~/.codex/bin/`, dá `chmod +x`, ajusta `PATH`.

**Plano B 3 — sem fallback Codex:** F5.6a aceita rodar **só com Claude**. `CodexProvider` reporta `BROKER_UNAVAILABLE` cedo, `AgentRunner` cai pra primary apenas. Logs do worker registram. Operacionalmente aceitável até o piloto Bradesco — depois reavaliar.

### `systemctl` não responde após habilitar `systemd=true`

**Causa:** `wsl --shutdown` não foi executado, ou outra distro WSL2 segura processos do WSL kernel.

**Conserto:**

```powershell
# Em PowerShell:
wsl --shutdown
# Aguarda 10 segundos
Start-Sleep -Seconds 10
wsl -d Ubuntu-22.04
# Dentro do WSL:
ps -p 1 -o comm=    # deve imprimir 'systemd'
```

Se ainda imprimir `init`, valide que `/etc/wsl.conf` está correto:

```bash
cat /etc/wsl.conf
# Deve conter literalmente:
# [boot]
# systemd=true
```

### `npm install -g` pede sudo apesar do `~/.npm-global` configurado

**Causa:** `npm prefix` mudou no `.bashrc` mas o shell atual ainda está no prefix antigo. Ou `~/.npm-global` não foi criado.

**Conserto:**

```bash
mkdir -p ~/.npm-global
npm config set prefix "$HOME/.npm-global"
npm config get prefix    # deve imprimir /home/<user>/.npm-global
```

### `which claude` retorna 2 caminhos (mount + nativo)

Não é um problema funcional, mas pode causar confusão. `which -a claude` mostra todos. O primeiro é o que vence — deve ser `~/.npm-global/bin/claude`. Se o mount aparece primeiro, refaz o passo 5.

---

## Anexos

### A. Onde ficam as credenciais

| Arquivo / pasta | Conteúdo |
|---|---|
| `~/.claude/.credentials.json` (Linux) | Token OAuth do Claude. Cuidado: secret. |
| `~/.claude/` (Linux) | Config geral do Claude Code CLI (settings, history). |
| `~/.codex/` (Linux) | Config e credenciais do Codex CLI. |
| `~/.jump-runner/logs/{date}.jsonl` (Linux) | Logs JSONL do `jump_agent_runner` (auditoria de cada run). |
| `~/.jump-runner/login-pending-{engine}` (Linux) | Sentinela quando broker pediu login interativo; removido por `jump-runner login-confirm`. |

### B. Rotação de tokens

Quando um token vaza ou expira:

```bash
# Claude:
rm ~/.claude/.credentials.json
# Refazer passo 9 (claude /login dentro de tmux project-claude)

# Codex:
rm -rf ~/.codex/auth*       # nomes exatos variam por versão
# Refazer passo 10
```

### C. Variáveis de ambiente do worker

Lidas pelo processo `jump-worker` (preenchidas no `.env` ou diretamente). Detalhes em `worker/.env.example` quando F5.6a Commit 3 estiver mergeado.

| Variável | Para que serve |
|---|---|
| `REDIS_URL` | Fila `jobs.agent` (origem dos jobs do worker) |
| `BACKEND_URL` | URL HTTPS do backend FastAPI (destino dos callbacks) |
| `WORKER_SHARED_SECRET` | Bearer-like header `X-Worker-Token` |
| `WORKER_HMAC_KEY` | HMAC-SHA256 do body do callback (`X-Worker-Signature`) |
| `WORKER_ID` | Identificador único do worker para heartbeat (default: hostname) |
| `WORKSPACE_ROOT` | Onde os jobs criam arquivos temporários (default `~/.jump-runner/jobs/`) |
| `HEARTBEAT_S` | Intervalo do heartbeat ao backend (default 30) |

### D. Onde reportar problemas

Logs do worker:

- `~/.jump-runner/logs/{date}.jsonl` — eventos do `Observer` (jump_agent_runner)
- `stderr` do processo `jump-worker` — eventos do próprio worker
- `WorkerHeartbeat` no banco do backend — status reportado periodicamente

Para investigar falha de job específica, busque pelo `run_id` em ambos.
