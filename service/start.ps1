# Run the local audio service on its claimed port (11250).
param([int]$Port = 11250)
$ErrorActionPreference = 'Stop'
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "service venv missing - run service\bootstrap-service.ps1" }

$env:SA3_SERVICE_PORT = "$Port"
Push-Location $PSScriptRoot
try {
    Write-Output ("audio service on http://127.0.0.1:{0}  (health: /api/health)" -f $Port)
    & $py -m uvicorn app:app --host 127.0.0.1 --port $Port --log-level info
} finally {
    Pop-Location
}
