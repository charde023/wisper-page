# run_youtube.ps1 — Orchestrator: queue of YouTube URLs -> audio -> transcript.
#
# Serialised to avoid GPU VRAM contention. Note authoring is a separate step
# (Claude / agent batch) once transcripts exist.
#
# Usage:
#   .\workflow\youtube\run_youtube.ps1 -Queue workflow\youtube\state\curated_queue.json
#   .\workflow\youtube\run_youtube.ps1 -Url "https://youtu.be/ID1","https://youtu.be/ID2"
#   .\workflow\youtube\run_youtube.ps1 -Queue ... -Limit 5     # first 5 only (test)
param(
    [string]$Queue,
    [string[]]$Url,
    [string]$RootDir,
    [int]$Limit = 0,
    [string]$Model = "large-v3",
    [string]$Device = "cuda",
    [string]$Language = "auto"
)
$ErrorActionPreference = "Stop"

$ytDir    = $PSScriptRoot
$wfDir    = Split-Path -Parent $ytDir
$projRoot = if ($RootDir) { $RootDir } else { Split-Path -Parent $wfDir }

$fetchPs1     = Join-Path $ytDir "yt_fetch.ps1"
$transcribePs1 = Join-Path $wfDir "transcribe.ps1"

# Resolve target URLs
$urls = @()
if ($Queue) {
    if (-not (Test-Path $Queue)) { Write-Error "queue not found: $Queue"; exit 1 }
    $q = Get-Content $Queue -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($v in $q.videos) {
        if ($v.url) { $urls += $v.url } elseif ($v.id) { $urls += "https://youtu.be/$($v.id)" }
    }
} elseif ($Url) {
    $urls = $Url
} else {
    Write-Error "pass -Queue <curated_queue.json> or -Url <list>"; exit 1
}

if ($Limit -gt 0 -and $urls.Count -gt $Limit) { $urls = $urls[0..($Limit - 1)] }
Write-Host "queued $($urls.Count) video(s)"

$results = @()
$i = 0
foreach ($u in $urls) {
    $i++
    Write-Host ""
    Write-Host "================================================================"
    Write-Host "[$i/$($urls.Count)] $u"
    Write-Host "================================================================"

    # Resolve id deterministically -> workspace path
    $id = $null
    try { $id = (& yt-dlp --js-runtimes node --skip-download --no-warnings --print "%(id)s" $u 2>$null | Select-Object -First 1) } catch {}
    if ($id) { $id = $id.Trim() }
    if (-not $id) {
        Write-Warning "could not resolve id; skipping"
        $results += [ordered]@{ Url = $u; Workspace = "-"; Status = "FAILED"; Note = "id resolve failed" }
        continue
    }
    $ws = Join-Path (Join-Path $projRoot "workspaces") "yt-$id"

    # Fetch audio
    Write-Host "[fetch] downloading audio..."
    try {
        & $fetchPs1 -Url $u -RootDir $projRoot
    } catch {
        $results += [ordered]@{ Url = $u; Workspace = $ws; Status = "FAILED"; Note = "fetch: $_" }
        continue
    }
    $audio = Join-Path $ws "audio.wav"
    if (-not (Test-Path $audio)) {
        $results += [ordered]@{ Url = $u; Workspace = $ws; Status = "FAILED"; Note = "no audio.wav" }
        continue
    }

    # Idempotency: skip transcription if transcript.txt already present
    $transcript = Join-Path $ws "transcript.txt"
    if ((Test-Path $transcript) -and ((Get-Item $transcript).Length -gt 0)) {
        Write-Host "[transcribe] transcript.txt exists — skipping (cached)"
        $results += [ordered]@{ Url = $u; Workspace = $ws; Status = "transcribed"; Note = "cached" }
        continue
    }

    # Transcribe
    Write-Host "[transcribe] $Model / $Device ..."
    & $transcribePs1 -Workspace $ws -Language $Language -Model $Model -Device $Device | Out-Host
    $transcript = Join-Path $ws "transcript.txt"
    if ((Test-Path $transcript) -and ((Get-Item $transcript).Length -gt 0)) {
        $results += [ordered]@{ Url = $u; Workspace = $ws; Status = "transcribed"; Note = "-" }
    } else {
        $results += [ordered]@{ Url = $u; Workspace = $ws; Status = "FAILED"; Note = "no transcript.txt" }
    }
}

# Summary
Write-Host ""
Write-Host "================================================================"
Write-Host "SUMMARY"
Write-Host "================================================================"
$ok = ($results | Where-Object { $_.Status -eq "transcribed" }).Count
Write-Host "transcribed $ok / $($results.Count)"
Write-Host ""
foreach ($r in $results) {
    Write-Host ("{0,-12} {1}" -f $r.Status, $r.Workspace) -NoNewline
    if ($r.Note -and $r.Note -ne "-") { Write-Host "  ($($r.Note))" } else { Write-Host "" }
}
Write-Host ""
Write-Host "next: author notes from each transcript.txt + youtube.json into the Obsidian vault."
