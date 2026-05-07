# setup-windows.ps1 — provisiona a maquina worker da Jump
#
# Uso (PowerShell elevado):
#     powershell -ExecutionPolicy Bypass -File setup-windows.ps1
#
# Pre-requisitos:
#   - Windows 10/11
#   - Conta com privilegio de administrador
#   - Acesso a internet
#
# Apos rodar:
#   1. Rebote a maquina se WSL2 foi instalado.
#   2. Em PowerShell normal: 'wsl -d Ubuntu-22.04 --' para entrar no Linux
#      e completar `claude /login` e `codex login`.
#   3. Inicie o jump-worker conforme worker/scripts/start-worker.ps1.

$ErrorActionPreference = "Stop"

Write-Host "==> Verificando WSL2..."
$wslStatus = wsl --status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL nao instalado. Instalando WSL2 + Ubuntu-22.04..."
    wsl --install -d Ubuntu-22.04
    Write-Host "Reboot necessario apos instalacao do WSL2. Rode este script novamente apos o reboot."
    exit 0
}

Write-Host "==> Garantindo distro Ubuntu-22.04..."
$distros = wsl -l -q
if ($distros -notmatch "Ubuntu-22\.04") {
    wsl --install -d Ubuntu-22.04
}

Write-Host "==> Atualizando WSL e definindo Ubuntu-22.04 como default..."
wsl --update
wsl --set-default Ubuntu-22.04

Write-Host "==> Instalando dependencias dentro da Ubuntu-22.04..."
wsl -d Ubuntu-22.04 -- bash -c @'
set -e
sudo apt-get update -y
sudo apt-get install -y tmux curl jq python3 python3-pip nodejs npm
# Claude Code via npm (oficial)
if ! command -v claude > /dev/null; then
  sudo npm install -g @anthropic-ai/claude-code
fi
# Codex CLI via instalador oficial
if ! command -v codex > /dev/null; then
  curl -fsSL https://codex.openai.com/install.sh | sh
  if ! grep -q '.codex/bin' ~/.bashrc; then
    echo 'export PATH=$HOME/.codex/bin:$PATH' >> ~/.bashrc
  fi
fi
echo "Versao tmux: $(tmux -V)"
echo "Versao node: $(node --version)"
echo "Versao claude: $(claude --version 2>/dev/null || echo 'NAO INSTALADO')"
echo "Versao codex: $(codex --version 2>/dev/null || echo 'NAO INSTALADO')"
'@

Write-Host "==> Criando sessoes tmux iniciais (project-claude e project-codex)..."
wsl -d Ubuntu-22.04 -- tmux kill-session -t project-claude 2>$null
wsl -d Ubuntu-22.04 -- tmux kill-session -t project-codex 2>$null
wsl -d Ubuntu-22.04 -- tmux new-session -d -s project-claude
wsl -d Ubuntu-22.04 -- tmux new-session -d -s project-codex

Write-Host "==> OK. Proximos passos:"
Write-Host "  1. wsl -d Ubuntu-22.04 -- tmux attach -t project-claude"
Write-Host "     dentro da sessao: claude /login (segue o fluxo no browser)"
Write-Host "     desanexe com Ctrl+B D"
Write-Host "  2. wsl -d Ubuntu-22.04 -- tmux attach -t project-codex"
Write-Host "     dentro da sessao: codex login (segue o fluxo no browser)"
Write-Host "     desanexe com Ctrl+B D"
Write-Host "  3. python -m pip install -e <caminho>/jump_agent_runner"
Write-Host "  4. jump-runner smoke"
