# One-time install of Stability's TFLite runtime (CPU, Windows x64).
# Downloads the runtime and model weights; models are cached outside this repo.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tfl = Join-Path $root 'upstream\optimized\tflite'

if (-not (Test-Path $tfl)) {
    throw "upstream missing at $tfl - run: git clone --depth 1 https://github.com/Stability-AI/stable-audio-3.git upstream"
}

Push-Location $tfl
try {
    Write-Output 'running upstream install.bat (first run downloads model weights)...'
    & cmd.exe /c install.bat
    if ($LASTEXITCODE -ne 0) { throw "install.bat exited $LASTEXITCODE" }
    Write-Output 'installed. try: scripts\gen.ps1 -Mode music -Prompt "calm ambient bed" -Seconds 30'
} finally {
    Pop-Location
}
