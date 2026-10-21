# One-time setup for the local audio service (its own venv; the model runtime has its own).
$ErrorActionPreference = 'Stop'
$service = $PSScriptRoot
$venv = Join-Path $service '.venv'
$py = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path $py)) {
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    $python = if ($onPath) { $onPath.Source } else {
        $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match 'Python3(10|11|12|13)\\python\.exe$' } |
            Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { $found.FullName } else { $null }
    }
    if (-not $python) { throw 'no Python 3.10-3.13 found' }
    & $python -m venv $venv
}

& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $service 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw "pip install failed ($LASTEXITCODE)" }
Write-Output 'service venv ready. start with: service\start.ps1'
