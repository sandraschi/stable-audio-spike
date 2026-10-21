# A/B run: one 60s bed plus five effects, timed, results in out/ab.csv.
# Run scripts\bootstrap.ps1 first (models download on first generate).
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$gen = Join-Path $PSScriptRoot 'gen.ps1'
$rows = @()

$jobs = @(
    @{ Mode = 'music'; Prompt = 'calm ambient instrumental bed, sparse piano, no vocals, loopable'; Seconds = 60 },
    @{ Mode = 'sfx'; Prompt = 'single camera shutter click, close, dry'; Seconds = 2 },
    @{ Mode = 'sfx'; Prompt = 'soft UI transition whoosh, short'; Seconds = 2 },
    @{ Mode = 'sfx'; Prompt = 'single mouse click, crisp'; Seconds = 1 },
    @{ Mode = 'sfx'; Prompt = 'short paper page turn, close'; Seconds = 2 },
    @{ Mode = 'sfx'; Prompt = 'deep boom impact, cinematic, short tail'; Seconds = 3 }
)

foreach ($job in $jobs) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $out = Join-Path $root ("out\ab-{0}-{1}.wav" -f $job.Mode, $stamp)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $gen -Mode $job.Mode -Prompt $job.Prompt -Seconds $job.Seconds -Out $out
    $sw.Stop()
    $kb = if (Test-Path $out) { [math]::Round((Get-Item $out).Length / 1KB, 1) } else { 0 }
    $rows += [pscustomobject]@{
        mode = $job.Mode; prompt = $job.Prompt; seconds = $job.Seconds
        wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 2); kb = $kb
        ok = [bool](Test-Path $out); path = $out
    }
}

$csv = Join-Path $root 'out\ab.csv'
$rows | Export-Csv -Path $csv -NoTypeInformation -Encoding utf8
$rows | Format-Table mode, seconds, wall_s, kb, ok -AutoSize | Out-String -Width 120
Write-Output ("results: {0}" -f $csv)
