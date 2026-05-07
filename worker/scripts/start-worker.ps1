# start-worker.ps1 — inicia o processo worker da Jump
#
# Pre-requisitos: setup-windows.ps1 ja rodou; venv com agent-runner + worker
# instalados; .env do worker preenchido com REDIS_URL, BACKEND_URL,
# WORKER_SHARED_SECRET, WORKER_HMAC_KEY apontando para Railway.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"

if (-not (Test-Path $venv)) {
    Write-Host "Criando venv em $venv..."
    py -3.12 -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install --upgrade pip
    & "$venv\Scripts\python.exe" -m pip install -e "$root\..\jump_agent_runner"
    & "$venv\Scripts\python.exe" -m pip install -e $root
}

Write-Host "Iniciando jump-worker..."
& "$venv\Scripts\jump-worker.exe"
