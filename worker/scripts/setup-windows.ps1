# setup-windows.ps1 - provisiona a maquina worker da Jump
#
# Idempotente: reexecutar e seguro. Cada passo verifica antes de modificar.
# Detalhes e troubleshooting em docs/runbooks/setup-worker-wsl.md.
#
# Uso:
#   Primeira execucao (precisa instalar WSL2): PowerShell elevado.
#     powershell -ExecutionPolicy Bypass -File setup-windows.ps1
#   Reexecucoes (WSL2 ja instalado): PowerShell normal e suficiente.

$ErrorActionPreference = "Stop"

# Forca encoding UTF-8 no PowerShell — wsl.exe emite UTF-16LE por default,
# o que quebra comparacoes -match com strings normais (NUL bytes intercalados).
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding           = [System.Text.UTF8Encoding]::new()

# Contadores para relatorio final
$script:Done    = New-Object System.Collections.ArrayList
$script:Skipped = New-Object System.Collections.ArrayList
$script:Failed  = New-Object System.Collections.ArrayList

function Mark-Done($step)    { [void]$script:Done.Add($step) }
function Mark-Skipped($step) { [void]$script:Skipped.Add($step) }
function Mark-Failed($step)  { [void]$script:Failed.Add($step) }

# ---- 1. WSL2 instalado ----
Write-Host "==> [1/4] WSL2..." -ForegroundColor Cyan
wsl --status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL2 ausente. Instalando..." -ForegroundColor Yellow
    wsl --install -d Ubuntu-22.04
    Mark-Done "1. WSL2 + Ubuntu-22.04 instalados (REBOOT necessario)"
    Write-Host ""
    Write-Host "REBOOT necessario. Reexecute este script apos reboot." -ForegroundColor Yellow
    exit 0
}
Mark-Skipped "1. WSL2 ja instalado"

# ---- 2. Distro Ubuntu-22.04 + default ----
Write-Host "==> [2/4] Distro Ubuntu-22.04..." -ForegroundColor Cyan
# Defesa em profundidade: limpa NUL bytes residuais caso o encoding UTF-8
# acima ainda nao tenha vencido o comportamento UTF-16 do wsl.exe nessa versao.
$distros = ((wsl -l -q | Out-String) -replace "`0", "").Trim()
if ($distros -notmatch "Ubuntu-22\.04") {
    Write-Host "Ubuntu-22.04 ausente. Instalando..." -ForegroundColor Yellow
    wsl --install -d Ubuntu-22.04
    wsl --set-default Ubuntu-22.04
    Mark-Done "2. Ubuntu-22.04 instalado e definido como default"
} else {
    wsl --set-default Ubuntu-22.04 2>&1 | Out-Null
    Mark-Skipped "2. Ubuntu-22.04 ja presente"
}
wsl --update 2>&1 | Out-Null

# ---- 3. Setup do ambiente Linux (idempotente bloco unico) ----
Write-Host "==> [3/4] Provisionando ambiente Linux (apt, Node 20, claude, codex, tmux)..." -ForegroundColor Cyan

$linuxSetup = @'
set -eu
set -o pipefail

ACTIONS_FILE=/tmp/jump-setup-actions.txt
: > "$ACTIONS_FILE"

note_done()    { echo "done|$1"    >> "$ACTIONS_FILE"; }
note_skipped() { echo "skipped|$1" >> "$ACTIONS_FILE"; }

# 3.1 systemd em /etc/wsl.conf
if ! grep -q "^systemd=true" /etc/wsl.conf 2>/dev/null; then
    sudo tee -a /etc/wsl.conf >/dev/null <<EOF

[boot]
systemd=true
EOF
    note_done "3.1 /etc/wsl.conf: systemd=true escrito (requer wsl --shutdown)"
else
    note_skipped "3.1 systemd ja habilitado no /etc/wsl.conf"
fi

# 3.2 Pacotes do sistema (instalar apenas os ausentes)
sudo apt-get update -y >/dev/null
NEED_APT=""
for pkg in tmux curl jq python3 python3-pip ca-certificates; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        NEED_APT="$NEED_APT $pkg"
    fi
done
if [ -n "$NEED_APT" ]; then
    sudo apt-get install -y $NEED_APT >/dev/null
    note_done "3.2 apt instalou:$NEED_APT"
else
    note_skipped "3.2 pacotes apt ja presentes (tmux/curl/jq/python3/...)"
fi

# 3.3 Node 20 LTS via NodeSource — versao manual (gpg + tee + apt-get) em vez do
# instalador oficial `curl ... | sudo -E bash -`. Razao: o sudoers granular
# usado durante F5.6a (/etc/sudoers.d/jump-setup-f56a) restringe NOPASSWD a
# apt-get, tee em arquivos especificos e gpg — NAO inclui `bash -`. Manual
# fica mais seguro mesmo em produção (sem shell root de fonte externa).
NODE_RAW=$(node --version 2>/dev/null || echo "")
NODE_MAJOR=$(echo "$NODE_RAW" | sed -E "s/^v([0-9]+).*/\\1/" | grep -E "^[0-9]+$" || echo 0)
if [ "$NODE_MAJOR" -lt 18 ]; then
    # Dependencias da operacao (idempotente; ja vieram do 3.2 mas garantia extra)
    sudo apt-get install -y curl gnupg ca-certificates >/dev/null
    # Importa chave do NodeSource em /etc/apt/trusted.gpg.d/ (presente na Ubuntu 22.04)
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | sudo gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/nodesource.gpg
    # Adiciona repo — 'nodistro' funciona transversalmente em Ubuntu/Debian
    echo "deb https://deb.nodesource.com/node_20.x nodistro main" \
      | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
    sudo apt-get update -y >/dev/null
    sudo apt-get install -y nodejs >/dev/null
    if [ -z "$NODE_RAW" ]; then
        note_done "3.3 Node 20 LTS instalado via NodeSource (era ausente)"
    else
        note_done "3.3 Node 20 LTS instalado via NodeSource (era $NODE_RAW)"
    fi
else
    note_skipped "3.3 Node $NODE_RAW ja >= 18"
fi

# 3.4 npm prefix em ~/.npm-global (globais sem sudo)
mkdir -p "$HOME/.npm-global"
CURRENT_PREFIX=$(npm config get prefix 2>/dev/null || echo "")
if [ "$CURRENT_PREFIX" != "$HOME/.npm-global" ]; then
    npm config set prefix "$HOME/.npm-global"
    note_done "3.4 npm prefix definido para ~/.npm-global (era $CURRENT_PREFIX)"
else
    note_skipped "3.4 npm prefix ja em ~/.npm-global"
fi

# 3.5 PATH em ~/.bashrc E ~/.profile - ~/.npm-global/bin precede /mnt/c/.../npm
# Razao do .profile (alem de .bashrc):
#   - bash interativo le .bashrc
#   - bash -lc (login shell) le .profile/.bash_profile, NAO .bashrc
#   - subprocess de Python (claude_headless.py) e wsl -- <cmd> heredam o
#     ambiente do login shell. Sem PATH no .profile, o `claude` resolvido
#     vira o do mount Windows (/mnt/c/.../npm/claude) que nao tem login.
PATH_LINE='export PATH="$HOME/.npm-global/bin:$PATH"'
for rcfile in ~/.bashrc ~/.profile; do
    if ! grep -qxF "$PATH_LINE" "$rcfile" 2>/dev/null; then
        echo "$PATH_LINE" >> "$rcfile"
        note_done "3.5 PATH ~/.npm-global/bin adicionado ao $rcfile"
    else
        note_skipped "3.5 PATH ~/.npm-global/bin ja em $rcfile"
    fi
done

# Garante PATH na sessao atual (proximas etapas dependem disso)
export PATH="$HOME/.npm-global/bin:$PATH"

# 3.6 Claude Code CLI nativo no Linux
if [ ! -f "$HOME/.npm-global/bin/claude" ]; then
    npm install -g @anthropic-ai/claude-code >/dev/null 2>&1
    hash -r 2>/dev/null || true
    note_done "3.6 claude instalado nativamente em ~/.npm-global/bin/claude"
else
    note_skipped "3.6 claude nativo ja presente em ~/.npm-global/bin/"
fi

# 3.7 Codex CLI via installer oficial — com curl -I preventivo (debito F5.6a.X)
# Antes de gastar 5-10min num download que pode falhar, valida que a URL
# responde 200. Se 4xx/5xx, aborta cedo com mensagem clara apontando o runbook.
if [ ! -f "$HOME/.codex/bin/codex" ]; then
    if ! curl -I -fsS https://codex.openai.com/install.sh >/dev/null 2>&1; then
        note_done "3.7 ERRO: URL https://codex.openai.com/install.sh nao retornou 200. Plano B 1/2/3 em docs/runbooks/setup-worker-wsl.md (Solucao de problemas)."
    elif curl -fsSL https://codex.openai.com/install.sh | sh >/dev/null 2>&1; then
        note_done "3.7 codex instalado via installer oficial OpenAI"
    else
        note_done "3.7 ERRO: codex installer baixou (HEAD 200) mas execucao falhou; ver Plano B no runbook"
    fi
else
    note_skipped "3.7 codex ja presente em ~/.codex/bin/"
fi

# 3.8 PATH ~/.codex/bin em ~/.bashrc E ~/.profile (mesmo motivo do 3.5)
CODEX_PATH_LINE='export PATH="$HOME/.codex/bin:$PATH"'
for rcfile in ~/.bashrc ~/.profile; do
    if ! grep -qxF "$CODEX_PATH_LINE" "$rcfile" 2>/dev/null; then
        echo "$CODEX_PATH_LINE" >> "$rcfile"
        note_done "3.8 PATH ~/.codex/bin adicionado ao $rcfile"
    else
        note_skipped "3.8 PATH ~/.codex/bin ja em $rcfile"
    fi
done
export PATH="$HOME/.codex/bin:$PATH"

# 3.9 tmux sessions PERSISTENTES - NUNCA mata sessao existente (login pode estar la)
if ! tmux has-session -t project-claude 2>/dev/null; then
    tmux new-session -d -s project-claude
    note_done "3.9 tmux session project-claude criada"
else
    note_skipped "3.9 tmux project-claude ja existe (preservada)"
fi
if ! tmux has-session -t project-codex 2>/dev/null; then
    tmux new-session -d -s project-codex
    note_done "3.10 tmux session project-codex criada"
else
    note_skipped "3.10 tmux project-codex ja existe (preservada)"
fi

# === F5.6b: Python 3.12 + venv worker (sem sudo, sem curl|sh) ===
# Razao: jump-worker e seu pyproject exigem Python >=3.12; Ubuntu 22.04 traz
# 3.10. Usamos `uv` (toolchain manager Astral) instalado em userspace via
# pip --user, NAO via `curl|sh` (mesma decisao do F5.6a.X — NodeSource sem
# bash root). uv baixa Python 3.12 pre-compilado no home, cria venv isolado
# em ~/.jump-runner/.venv-worker, e instala editable o pacote do worker e do
# jump_agent_runner. Resultado: `jump-worker` e `jump-runner` callable de
# dentro do WSL Linux com claude nativo no PATH.

# 3.11 uv via pip --user (sem `curl|sh`)
if [ ! -f "$HOME/.local/bin/uv" ]; then
    python3 -m pip install --user --quiet uv >/dev/null 2>&1
    note_done "3.11 uv instalado via pip --user (~/.local/bin/uv)"
else
    note_skipped "3.11 uv ja presente em ~/.local/bin/"
fi

# uv requer ~/.local/bin no PATH; Ubuntu .profile default ja inclui se exists.
export PATH="$HOME/.local/bin:$PATH"

# 3.12 Python 3.12 (pre-compilado pelo uv, instalado em userspace)
if ! uv python list --only-installed 2>/dev/null | grep -q "3.12"; then
    uv python install 3.12 >/dev/null 2>&1
    note_done "3.12 Python 3.12 instalado via uv (userspace)"
else
    note_skipped "3.12 Python 3.12 ja instalado via uv"
fi

# 3.13 venv worker em ~/.jump-runner/.venv-worker
mkdir -p "$HOME/.jump-runner"
if [ ! -f "$HOME/.jump-runner/.venv-worker/bin/python" ]; then
    uv venv --python 3.12 "$HOME/.jump-runner/.venv-worker" >/dev/null 2>&1
    note_done "3.13 venv ~/.jump-runner/.venv-worker criado (Python 3.12)"
else
    note_skipped "3.13 venv ~/.jump-runner/.venv-worker ja existe"
fi

# 3.14 Instalar jump_agent_runner + worker editable no venv
# `--cd <repo_root>` do `wsl -- bash` (chamado pelo PowerShell wrapper) faz
# `$PWD` apontar para a raiz do monorepo `jump-report/`. Caminhos relativos
# abaixo funcionam tanto em CI quanto em workstation.
if [ ! -f "$HOME/.jump-runner/.venv-worker/bin/jump-worker" ]; then
    uv pip install \
        --python "$HOME/.jump-runner/.venv-worker/bin/python" \
        --quiet \
        -e "$PWD/jump_agent_runner" \
        -e "$PWD/worker" >/dev/null 2>&1
    note_done "3.14 jump_agent_runner + worker instalados editable no venv"
else
    note_skipped "3.14 jump-worker entrypoint ja existe (instalacao previa)"
fi

# 3.16 Estado dos componentes (para reporte final no PowerShell)
{
  echo "VERSIONS_START"
  echo "tmux=$(tmux -V 2>/dev/null | head -1)"
  echo "node=$(node --version 2>/dev/null || echo ausente)"
  echo "npm=$(npm --version 2>/dev/null || echo ausente)"
  echo "claude=$(claude --version 2>/dev/null | head -1 || echo ausente)"
  echo "codex=$(codex --version 2>/dev/null | head -1 || echo ausente)"
  echo "which_claude=$(which claude 2>/dev/null || echo ausente)"
  echo "which_codex=$(which codex 2>/dev/null || echo ausente)"
  echo "claude_login=$([ -f $HOME/.claude/.credentials.json ] && echo presente || echo ausente)"
  echo "codex_login=$([ -d $HOME/.codex ] && echo presente || echo ausente)"
  echo "worker_venv=$([ -f $HOME/.jump-runner/.venv-worker/bin/python ] && echo presente || echo ausente)"
  echo "jump_worker=$([ -f $HOME/.jump-runner/.venv-worker/bin/jump-worker ] && echo presente || echo ausente)"
  echo "VERSIONS_END"
} >> "$ACTIONS_FILE"

cat "$ACTIONS_FILE"
rm -f "$ACTIONS_FILE"
'@

# Escreve o bloco bash em arquivo temp e executa via path. Passar via
# 'bash -c $bigString' quebra com parenteses, aspas e heredocs aninhados —
# o PowerShell + wsl.exe nao escapam consistentemente strings multi-linha.
$tmpScript = Join-Path $env:TEMP ("jump-setup-" + [guid]::NewGuid().ToString("N") + ".sh")
# Grava UTF-8 SEM BOM (bash nao gosta de BOM no primeiro byte)
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($tmpScript, $linuxSetup, $utf8NoBom)

# Converte path Windows -> WSL manualmente. wslpath via wsl.exe sofre quoting
# inconsistente das backslashes em alguns ambientes (vimos perda de '\' no PS 5.1).
# Caminho manual e deterministico: "C:\path\to" -> "/mnt/c/path/to".
function ConvertTo-WslPath($winPath) {
    $drive = $winPath.Substring(0, 1).ToLower()
    $rest = $winPath.Substring(2) -replace '\\', '/'
    return "/mnt/$drive$rest"
}
$wslScriptPath = ConvertTo-WslPath $tmpScript

# Raiz do monorepo jump-report/ (parent de worker/, que e parent de scripts/).
# Convertido para path Linux. `wsl --cd $repoRootWsl` faz `$PWD` dentro do
# bash apontar para a raiz — passos 3.14 (uv pip install -e $PWD/...) dependem.
$repoRootWin = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRootWsl = ConvertTo-WslPath $repoRootWin

$linuxOutput = wsl -d Ubuntu-22.04 --cd $repoRootWsl -- bash $wslScriptPath
$linuxExit = $LASTEXITCODE
Remove-Item -LiteralPath $tmpScript -ErrorAction SilentlyContinue

if ($linuxExit -ne 0) {
    Write-Host "Falha no setup Linux. Output completo:" -ForegroundColor Red
    Write-Host $linuxOutput
    Mark-Failed "3. Bloco Linux abortou (exit code $linuxExit)"
}

# Parser do output: classifica em done/skipped/versions
$inVersions = $false
$versions = @{}
foreach ($rawLine in ($linuxOutput -split "`n")) {
    $line = $rawLine.Trim()
    if ([string]::IsNullOrEmpty($line)) { continue }
    if ($line -eq "VERSIONS_START") { $inVersions = $true; continue }
    if ($line -eq "VERSIONS_END")   { $inVersions = $false; continue }
    if ($inVersions) {
        if ($line -match "^([^=]+)=(.+)$") {
            $versions[$Matches[1]] = $Matches[2]
        }
        continue
    }
    if ($line -match "^done\|(.+)$")          { Mark-Done    $Matches[1] }
    elseif ($line -match "^skipped\|(.+)$")   { Mark-Skipped $Matches[1] }
}

# ---- 4. wsl --shutdown necessario? ----
$systemdChanged = @($script:Done | Where-Object { $_ -match "systemd=true escrito" }).Count -gt 0
if ($systemdChanged) {
    Mark-Done "4. systemd PENDENTE de wsl --shutdown (manual - ver proximos passos)"
} else {
    Mark-Skipped "4. systemd ja estava aplicado"
}

# ---- 5. Relatorio final colorido ----
Write-Host ""
Write-Host "===== Relatorio do setup =====" -ForegroundColor Cyan
Write-Host ""
Write-Host ("Acoes executadas nesta rodada ({0}):" -f $script:Done.Count) -ForegroundColor Green
if ($script:Done.Count -eq 0) {
    Write-Host "  (nenhuma - ambiente ja estava 100% provisionado)" -ForegroundColor DarkGray
} else {
    foreach ($it in $script:Done) { Write-Host "  [OK]   $it" -ForegroundColor Green }
}
Write-Host ""
Write-Host ("Itens ja conformes - pulados ({0}):" -f $script:Skipped.Count) -ForegroundColor DarkGray
foreach ($it in $script:Skipped) { Write-Host "  [SKIP] $it" -ForegroundColor DarkGray }

if ($script:Failed.Count -gt 0) {
    Write-Host ""
    Write-Host ("Falhas ({0}):" -f $script:Failed.Count) -ForegroundColor Red
    foreach ($it in $script:Failed) { Write-Host "  [FAIL] $it" -ForegroundColor Red }
}

Write-Host ""
Write-Host "===== Estado final dos componentes =====" -ForegroundColor Cyan
function Show-State($label, $value, $okPattern) {
    if ([string]::IsNullOrEmpty($value)) { $value = "(sem valor)" }
    $isOk = $value -match $okPattern
    $glyph = if ($isOk) { "[OK]" } else { "[!!]" }
    $color = if ($isOk) { "Green" } else { "Red" }
    Write-Host ("  {0,-6} {1,-14} {2}" -f $glyph, $label, $value) -ForegroundColor $color
}

Show-State "tmux"         $versions["tmux"]         '^tmux'
Show-State "node"         $versions["node"]         '^v[0-9]+'
Show-State "npm"          $versions["npm"]          '^[0-9]+'
Show-State "claude"       $versions["claude"]       '^[0-9]'
Show-State "codex"        $versions["codex"]        '.'
Show-State "which claude" $versions["which_claude"] '^/home/'
Show-State "which codex"  $versions["which_codex"]  '^/home/'
Show-State "claude login" $versions["claude_login"] '^presente$'
Show-State "codex login"  $versions["codex_login"]  '^presente$'
Show-State "worker venv"  $versions["worker_venv"]  '^presente$'
Show-State "jump-worker"  $versions["jump_worker"]  '^presente$'

$loginPending = ($versions["claude_login"] -ne "presente") -or ($versions["codex_login"] -ne "presente")

# ---- 6. Proximos passos manuais ----
Write-Host ""
Write-Host "===== Proximos passos =====" -ForegroundColor Cyan

if ($systemdChanged) {
    Write-Host "  1. wsl --shutdown                       (encerra todas as distros)" -ForegroundColor Yellow
    Write-Host "  2. wsl -d Ubuntu-22.04                  (reabre - systemd ativo)" -ForegroundColor Yellow
    Write-Host ""
}

if ($versions["claude_login"] -ne "presente") {
    Write-Host "  Login Claude (executar depois do wsl --shutdown se aplicavel):" -ForegroundColor Yellow
    Write-Host "    wsl -d Ubuntu-22.04 -- tmux attach -t project-claude" -ForegroundColor White
    Write-Host "    [dentro do tmux] claude /login                  (browser abre via WSLg)" -ForegroundColor White
    Write-Host "    [dentro do tmux] Ctrl+B  D                      (desanexa, sessao continua)" -ForegroundColor White
    Write-Host ""
}

if ($versions["codex_login"] -ne "presente") {
    Write-Host "  Login Codex:" -ForegroundColor Yellow
    Write-Host "    wsl -d Ubuntu-22.04 -- tmux attach -t project-codex" -ForegroundColor White
    Write-Host "    [dentro do tmux] codex login" -ForegroundColor White
    Write-Host "    [dentro do tmux] Ctrl+B  D" -ForegroundColor White
    Write-Host ""
}

if (-not $loginPending -and -not $systemdChanged -and $script:Failed.Count -eq 0) {
    Write-Host "  Ambiente esta pronto. Validacao end-to-end:" -ForegroundColor Green
    Write-Host "    .\scripts\start-worker.ps1               (cria venv se ausente + boot)" -ForegroundColor White
    Write-Host "  Smoke isolado do agent-runner (sem worker):" -ForegroundColor Green
    Write-Host "    .\.venv\Scripts\jump-runner.exe smoke" -ForegroundColor White
}

Write-Host ""
Write-Host "Runbook detalhado: docs/runbooks/setup-worker-wsl.md" -ForegroundColor DarkGray
