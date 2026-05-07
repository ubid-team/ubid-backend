Param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    python -m venv .venv
}

$activate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
. $activate

Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from template" -ForegroundColor Yellow
}

Write-Host "Starting UBID backend on http://127.0.0.1:$Port" -ForegroundColor Green
uvicorn app.main:app --reload --port $Port
