# Generate one clip with Stable Audio 3 (TFLite CPU).
# Mode music -> sm-music, mode sfx -> sm-sfx. Prints wall time and output size.
param(
    [Parameter(Mandatory = $true)][ValidateSet('music', 'sfx')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$Prompt,
    [int]$Seconds = 30,
    [int]$Seed = 0,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sa3 = Join-Path $root 'upstream\optimized\tflite\sa3.ps1'
if (-not (Test-Path $sa3)) { throw "runtime missing - run scripts\bootstrap.ps1 first ($sa3)" }

$dit = if ($Mode -eq 'music') { 'sm-music' } else { 'sm-sfx' }
if (-not $Out) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $Out = Join-Path $root ("out\{0}-{1}.wav" -f $Mode, $stamp)
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Out) | Out-Null

$argv = @('--prompt', $Prompt, '--dit', $dit, '--seconds', "$Seconds", '--out', $Out)
if ($Seed -gt 0) { $argv += @('--seed', "$Seed") }

Write-Output ("{0} | {1}s | {2}" -f $dit, $Seconds, $Prompt)
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $sa3 @argv
$sw.Stop()

if (Test-Path $Out) {
    $kb = [math]::Round((Get-Item $Out).Length / 1KB, 1)
    $secs = [math]::Round($sw.Elapsed.TotalSeconds, 2)
    Write-Output ("wrote {0} ({1} KB) in {2}s" -f $Out, $kb, $secs)
    [pscustomobject]@{
        mode = $Mode; prompt = $Prompt; seconds = $Seconds
        wall_s = $secs; kb = $kb; path = $Out
    } | Export-Csv -Path (Join-Path $root 'out\last-run.csv') -NoTypeInformation -Encoding utf8
} else {
    Write-Output 'no output file produced'
    exit 1
}
