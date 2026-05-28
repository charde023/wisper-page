# Wrapper for transcribe.py that eliminates exit-127 ambiguity.
#
# Documented fix for: "Whisper exits 127 even on success"
# Real success is determined by artifact validation, NOT the Python exit code.
#
# Usage:
#   .\workflow\transcribe.ps1 -Workspace "C:\workspace\wisper-page\workspaces\my-video"
#   .\workflow\transcribe.ps1 -Workspace "..." -Language "auto"
#   .\workflow\transcribe.ps1 -Workspace "..." -Model "large-v3" -Device "cuda"
#   .\workflow\transcribe.ps1 -Workspace "..." -Device "cpu"
#
# Exit 0: artifacts are valid (transcript.txt, segments.json, transcribe.done all present
#         and non-empty).
# Exit 1: artifacts missing or empty — transcription failed.
param(
    [Parameter(Mandatory)][string]$Workspace,
    [string]$Language = "ko",
    [string]$Model,
    [string]$Device
)
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# 1. Resolve workspace path
# ---------------------------------------------------------------------------
$Workspace = (Resolve-Path $Workspace -ErrorAction Stop).Path

if (-not (Test-Path $Workspace)) {
    Write-Error "workspace not found: $Workspace"
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Resolve Python
# ---------------------------------------------------------------------------
$pythonExe = $null
try { $pythonExe = (Get-Command python -ErrorAction Stop).Source } catch {}
if (-not $pythonExe) {
    try { $pythonExe = (Get-Command python3 -ErrorAction Stop).Source } catch {}
}
if (-not $pythonExe) {
    Write-Error "python not found on PATH. Install Python 3.11+ and ensure it is accessible."
    exit 1
}
Write-Host "python: $pythonExe"

# ---------------------------------------------------------------------------
# 3. Locate canonical transcribe.py
# ---------------------------------------------------------------------------
$transcribePy = Join-Path $PSScriptRoot "_template\transcribe.py"
if (-not (Test-Path $transcribePy)) {
    Write-Error "transcribe.py not found at expected location: $transcribePy"
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Build argument list
# ---------------------------------------------------------------------------
$pyArgs = @(
    $transcribePy,
    "--workspace", $Workspace,
    "--language", $Language
)

if ($Model -and $Device) {
    $pyArgs += "--model", $Model
    $pyArgs += "--device", $Device
} elseif ($Model -and -not $Device) {
    Write-Error "--Model requires --Device to be specified together (both or neither)."
    exit 1
} elseif ($Device -and -not $Model) {
    Write-Error "--Device requires --Model to be specified together (both or neither)."
    exit 1
}

# ---------------------------------------------------------------------------
# 5. Pre-run: remove stale sentinel so we don't confuse a previous run's
#    transcribe.done with this run's success
# ---------------------------------------------------------------------------
$sentinelPath = Join-Path $Workspace "transcribe.done"
if (Test-Path $sentinelPath) {
    Remove-Item $sentinelPath -Force
    Write-Host "removed stale transcribe.done sentinel"
}

# ---------------------------------------------------------------------------
# 6. Invoke transcribe.py — capture output; deliberately ignore exit code
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "starting transcription..."
Write-Host "  workspace : $Workspace"
Write-Host "  language  : $Language"
if ($Model) { Write-Host "  model     : $Model / $Device" }
Write-Host ""

# Run and stream output in real time; $rawExit captures the raw exit code.
# We use a temporary script block to avoid losing $LASTEXITCODE across pipe stages.
$rawExit = $null
& $pythonExe @pyArgs
$rawExit = $LASTEXITCODE

Write-Host ""
Write-Host "Python process exited with code: $rawExit  (exit codes <= 127 may indicate OS-level launcher issues; artifacts are the authoritative signal)"

# ---------------------------------------------------------------------------
# 7. Artifact validation — this is the REAL success check
# ---------------------------------------------------------------------------
$transcriptPath = Join-Path $Workspace "transcript.txt"
$segmentsPath   = Join-Path $Workspace "segments.json"

$transcriptOk = (Test-Path $transcriptPath) -and ((Get-Item $transcriptPath).Length -gt 0)
$segmentsOk   = (Test-Path $segmentsPath)   -and ((Get-Item $segmentsPath).Length -gt 0)
$sentinelOk   = Test-Path $sentinelPath

# Parse segments count from segments.json (best-effort)
$segCount = 0
$transcribeDoneContent = ""
if ($segmentsOk) {
    try {
        $seg = Get-Content $segmentsPath -Raw -Encoding utf8 | ConvertFrom-Json
        $segCount = $seg.segments.Count
    } catch {
        Write-Warning "could not parse segments.json: $_"
    }
}

# Also read transcribe.done for informational content if present
if ($sentinelOk) {
    $transcribeDoneContent = (Get-Content $sentinelPath -Raw -Encoding utf8).Trim()
}

# Also scan progress.log for TRANSCRIBE_OK as an alternate success marker
$progressPath = Join-Path $Workspace "progress.log"
$hasOkMarker  = $false
if (Test-Path $progressPath) {
    $progressTail = Get-Content $progressPath -Tail 20 -Encoding utf8 -ErrorAction SilentlyContinue
    if ($progressTail -match "TRANSCRIBE_OK") {
        $hasOkMarker = $true
    }
}
# Also check stdout captured above — but since we streamed it, scan progress.log is enough.
# Additionally check if TRANSCRIBE_OK was printed to stdout by re-reading progress.log which
# transcribe.py appends to concurrently.

Write-Host ""
Write-Host "=" * 60
Write-Host "ARTIFACT VALIDATION RESULTS"
Write-Host "=" * 60

$transcriptStatus = if ($transcriptOk) { "OK  ($([math]::Round((Get-Item $transcriptPath).Length / 1KB, 1)) KB)" } else { "MISSING or EMPTY" }
$segmentsStatus   = if ($segmentsOk)   { "OK  ($segCount segments)" }                                             else { "MISSING or EMPTY" }
$sentinelStatus   = if ($sentinelOk)   { "PRESENT  ($transcribeDoneContent)" }                                    else { "ABSENT" }
$okMarkerStatus   = if ($hasOkMarker)  { "FOUND in progress.log" }                                                else { "not found in progress.log" }

Write-Host "  transcript.txt  : $transcriptStatus"
Write-Host "  segments.json   : $segmentsStatus"
Write-Host "  transcribe.done : $sentinelStatus"
Write-Host "  TRANSCRIBE_OK   : $okMarkerStatus"
Write-Host ""

# Success = transcript.txt AND segments.json exist/non-empty,
#           PLUS at least one of: transcribe.done OR TRANSCRIBE_OK marker.
# This tolerates exit-127 (OS launcher quirk) as long as artifacts are real.
$artifactsValid = $transcriptOk -and $segmentsOk -and ($sentinelOk -or $hasOkMarker)

if ($artifactsValid) {
    Write-Host "RESULT: SUCCESS — transcription complete."
    Write-Host "  segments : $segCount"
    if ($transcribeDoneContent) { Write-Host "  sentinel : $transcribeDoneContent" }
    Write-Host ""

    # Best-effort: stamp 'transcribed' stage in pipeline manifest
    $manifestPy = Join-Path $PSScriptRoot "lib\manifest.py"
    if (Test-Path $manifestPy) {
        try {
            & $pythonExe $manifestPy $Workspace set transcribed 2>$null
        } catch {}
    }

    Write-Host "next: process transcript_clean.md, then run make_html.py via"
    Write-Host "  python `"$PSScriptRoot\_template\make_html.py`" --workspace `"$Workspace`""
    exit 0
} else {
    Write-Host "RESULT: FAILURE — one or more required artifacts are missing or empty."
    Write-Host ""
    Write-Host "Diagnosis:"
    if (-not $transcriptOk) { Write-Host "  - transcript.txt is missing or empty (check progress.log for errors)" }
    if (-not $segmentsOk)   { Write-Host "  - segments.json is missing or empty (transcription may not have produced output)" }
    if (-not $sentinelOk)   { Write-Host "  - transcribe.done sentinel absent (transcribe.py did not reach its final write)" }
    if (-not $hasOkMarker)  { Write-Host "  - TRANSCRIBE_OK not found in progress.log" }
    Write-Host ""
    Write-Host "Check progress.log for details:"
    Write-Host "  Get-Content `"$progressPath`" -Tail 40"
    exit 1
}
