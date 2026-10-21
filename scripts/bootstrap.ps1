# One-time install of Stability's TFLite runtime (CPU, Windows x64).
# Creates upstream/optimized/tflite/.venv, installs requirements, downloads the
# small model bundles. Models are cached outside this repo after the first run.
param(
    [string]$Python = '',
    [string]$Models = 'sm-music,sm-sfx'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tfl = Join-Path $root 'upstream\optimized\tflite'
if (-not (Test-Path $tfl)) {
    throw "upstream missing at $tfl - run: git clone --depth 1 https://github.com/Stability-AI/stable-audio-3.git upstream"
}

# ai_edge_litert needs Python 3.10-3.13. Prefer PATH, then the local installs.
if (-not $Python) {
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) {
        $Python = $onPath.Source
    } else {
        $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match 'Python3(10|11|12|13)\\python\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($found) { $Python = $found.FullName }
    }
}
if (-not $Python) { throw 'no Python 3.10-3.13 found (set PATH or pass -Python <path>)' }
Write-Output ("python: {0}" -f $Python)

$venv = Join-Path $tfl '.venv'
$py = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Output 'creating venv...'
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed ($LASTEXITCODE)" }
}

Write-Output 'installing requirements...'
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $tfl 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw "pip install failed ($LASTEXITCODE)" }

# install.py re-checks pip unless told not to; we just did it.
$env:INSTALL_SKIP_PIP = '1'
try {
    & $py (Join-Path $tfl 'scripts\install.py') --download $Models
} finally {
    Remove-Item Env:INSTALL_SKIP_PIP -ErrorAction SilentlyContinue
}
if ($LASTEXITCODE -ne 0) { throw "model download failed ($LASTEXITCODE)" }

Write-Output 'installed. try: scripts\gen.ps1 -Mode music -Prompt "calm ambient bed" -Seconds 30'
