# run.ps1 — Orchestrator for wisper-page steps 1–4 (workspace init → audio → transcribe)
#
# Usage:
#   .\workflow\run.ps1 -VideoFile "C:\path\to\video.mp4"
#   .\workflow\run.ps1 -VideoFile "v1.mp4","v2.mp4"            # batch
#   .\workflow\run.ps1 -VideoFile "video.mp4" -Language "en"
#   .\workflow\run.ps1 -VideoFile "video.mp4" -TranscribeOnly   # stop after transcription
#   .\workflow\run.ps1 -VideoFile "video.mp4" -Name "my-ws"    # custom workspace name (single video only)
#   .\workflow\run.ps1 -VideoFile "video.mp4" -Force            # re-initialise existing workspace
#
# After transcription (unless -TranscribeOnly) prints the Claude hand-off message.
# All transcriptions are serialised to avoid GPU VRAM contention.
param(
    [Parameter(Mandatory)][string[]]$VideoFile,
    [string]$Language = "ko",
    [switch]$TranscribeOnly,
    [string]$Name,
    [switch]$Force
)
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Validate -Name is only used with a single video
# ---------------------------------------------------------------------------
if ($Name -and $VideoFile.Count -gt 1) {
    Write-Error "-Name may only be specified when processing a single video file."
    exit 1
}

# ---------------------------------------------------------------------------
# Resolve canonical script paths
# ---------------------------------------------------------------------------
$scriptDir        = $PSScriptRoot
$rootDir          = Split-Path -Parent $scriptDir
$workspacesDir    = Join-Path $rootDir "workspaces"
$newWorkspacePs1  = Join-Path $scriptDir "new_workspace.ps1"
$extractAudioPs1  = Join-Path $scriptDir "extract_audio.ps1"
$transcribePs1    = Join-Path $scriptDir "transcribe.ps1"
$manifestPy       = Join-Path $scriptDir "lib\manifest.py"

# Resolve python command once
$pythonCmd = $null
try { $pythonCmd = (Get-Command python  -ErrorAction Stop).Source } catch {}
if (-not $pythonCmd) {
    try { $pythonCmd = (Get-Command python3 -ErrorAction Stop).Source } catch {}
}

# ---------------------------------------------------------------------------
# Helper: derive workspace path using the same sanitization new_workspace.ps1
#         applies. This must stay in sync with new_workspace.ps1.
# ---------------------------------------------------------------------------
function Get-WorkspacePath {
    param([string]$VideoPath, [string]$CustomName)

    $base = [System.IO.Path]::GetFileNameWithoutExtension($VideoPath)

    if ($CustomName) {
        $wsName = $CustomName
    } else {
        $wsName = $base -replace '[\s()\[\]{}&!@#$%^*+=|\\/<>:;,"''`~]', '-'
        $wsName = $wsName -replace '-{2,}', '-'
        $wsName = $wsName.Trim('-')
        if (-not $wsName) { $wsName = "workspace" }
    }

    return Join-Path $workspacesDir $wsName
}

# ---------------------------------------------------------------------------
# Per-video status tracking
# ---------------------------------------------------------------------------
$results = @()   # array of [ordered]@{Video=…; Workspace=…; Status=…; Note=…}

# ---------------------------------------------------------------------------
# Main loop — serial to avoid GPU VRAM contention
# ---------------------------------------------------------------------------
foreach ($vf in $VideoFile) {
    $videoAbs = $vf
    if (-not [System.IO.Path]::IsPathRooted($vf)) {
        if (Test-Path $vf) {
            $videoAbs = (Resolve-Path $vf).Path
        }
        # If not resolvable here let new_workspace.ps1 emit the error
    }

    $wsName = if ($Name) { $Name } else { $null }
    $ws = Get-WorkspacePath -VideoPath $videoAbs -CustomName $wsName

    $stepStatus = "ok"
    $stepNote   = ""

    Write-Host ""
    Write-Host "================================================================"
    Write-Host "VIDEO : $videoAbs"
    Write-Host "WS    : $ws"
    Write-Host "================================================================"

    # ------------------------------------------------------------------
    # Step 1 — new_workspace.ps1
    # ------------------------------------------------------------------
    Write-Host ""
    Write-Host "[1/3] Creating workspace..."
    $newWsArgs = @("-VideoFile", $videoAbs)
    if ($Name)  { $newWsArgs += @("-Name",  $Name) }
    if ($Force) { $newWsArgs += "-Force" }

    & $newWorkspacePs1 @newWsArgs
    if ($LASTEXITCODE -ne 0) {
        $stepStatus = "FAILED"
        $stepNote   = "new_workspace.ps1 exited $LASTEXITCODE"
        Write-Warning "new_workspace.ps1 failed for: $videoAbs"
        $results += [ordered]@{
            Video     = $videoAbs
            Workspace = $ws
            Status    = $stepStatus
            Note      = $stepNote
        }
        continue
    }

    # ------------------------------------------------------------------
    # If -TranscribeOnly: update manifest mode to transcribe-only.
    # init is idempotent and does NOT clobber existing stage timestamps.
    # ------------------------------------------------------------------
    if ($TranscribeOnly -and $pythonCmd -and (Test-Path $manifestPy)) {
        Write-Host ""
        Write-Host "[mode] Setting pipeline mode to transcribe-only..."
        # Re-run init with --mode transcribe-only; idempotent — preserves stages.
        # We must pass --video so the required arg is satisfied, but init won't
        # overwrite existing fields when pipeline.json already exists.
        $videoPathForManifest = $videoAbs
        & $pythonCmd $manifestPy $ws init --video $videoPathForManifest --mode "transcribe-only" --language $Language 2>$null
        # Non-fatal: manifest is best-effort
    }

    # ------------------------------------------------------------------
    # Step 2 — extract_audio.ps1
    # ------------------------------------------------------------------
    Write-Host ""
    Write-Host "[2/3] Extracting audio..."
    & $extractAudioPs1 -Workspace $ws
    if ($LASTEXITCODE -ne 0) {
        $stepStatus = "FAILED"
        $stepNote   = "extract_audio.ps1 exited $LASTEXITCODE"
        Write-Warning "extract_audio.ps1 failed for workspace: $ws"
        $results += [ordered]@{
            Video     = $videoAbs
            Workspace = $ws
            Status    = $stepStatus
            Note      = $stepNote
        }
        continue
    }

    # ------------------------------------------------------------------
    # Step 3 — transcribe.ps1
    # ------------------------------------------------------------------
    Write-Host ""
    Write-Host "[3/3] Transcribing (this may take several minutes)..."
    & $transcribePs1 -Workspace $ws -Language $Language
    $transcribeExit = $LASTEXITCODE

    $transcriptPath = Join-Path $ws "transcript.txt"

    # exit code 127 is expected on some systems even when output is valid
    if ($transcribeExit -ne 0 -and $transcribeExit -ne 127) {
        if (-not (Test-Path $transcriptPath)) {
            $stepStatus = "FAILED"
            $stepNote   = "transcribe.ps1 exited $transcribeExit; transcript.txt not found"
            Write-Warning "Transcription failed for workspace: $ws"
            $results += [ordered]@{
                Video     = $videoAbs
                Workspace = $ws
                Status    = $stepStatus
                Note      = $stepNote
            }
            continue
        } else {
            # Output found despite non-zero exit — treat as warning
            $stepNote = "transcribe.ps1 exited $transcribeExit (transcript.txt present, continuing)"
            Write-Warning $stepNote
        }
    }

    # ------------------------------------------------------------------
    # Hand-off message
    # ------------------------------------------------------------------
    Write-Host ""
    if ($TranscribeOnly) {
        Write-Host "DONE (transcribe-only mode)."
        Write-Host "transcript.txt ready at: $transcriptPath"
        $stepStatus = "transcribed"
        $stepNote   = "transcribe-only; no guide authoring"
    } else {
        Write-Host "transcript.txt ready at: $transcriptPath"
        Write-Host ""
        Write-Host "Next (Claude authoring):"
        Write-Host "  1. Write transcript_clean.md  in: $ws"
        Write-Host "  2. Write guide.md              in: $ws"
        Write-Host "  3. Run make_html.py:"
        Write-Host "       python `"$scriptDir\_template\make_html.py`" --workspace `"$ws`""
        Write-Host "  4. Run stage_publish.py:"
        Write-Host "       python `"$scriptDir\stage_publish.py`" `"$ws`" --slug <slug>"
        Write-Host "  5. Run deploy.ps1:"
        Write-Host "       .\workflow\deploy.ps1 -Workspace `"$ws`" -Slug <slug>"
        $stepStatus = if ($stepNote) { "transcribed (warn)" } else { "transcribed" }
    }

    $results += [ordered]@{
        Video     = $videoAbs
        Workspace = $ws
        Status    = $stepStatus
        Note      = $stepNote
    }
}

# ---------------------------------------------------------------------------
# Per-video status table
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "================================================================"
Write-Host "SUMMARY"
Write-Host "================================================================"

$colW = @{V = 0; W = 0; S = 0}
foreach ($r in $results) {
    $vLen = ([string]$r.Video).Length
    $wLen = ([string]$r.Workspace).Length
    $sLen = ([string]$r.Status).Length
    if ($vLen -gt $colW.V) { $colW.V = $vLen }
    if ($wLen -gt $colW.W) { $colW.W = $wLen }
    if ($sLen -gt $colW.S) { $colW.S = $sLen }
}
# Cap columns so the table stays readable in a narrow terminal
$colW.V = [math]::Min($colW.V, 60)
$colW.W = [math]::Min($colW.W, 60)

$header = ("VIDEO".PadRight($colW.V)) + "  " + ("WORKSPACE".PadRight($colW.W)) + "  " + ("STATUS".PadRight($colW.S)) + "  NOTE"
Write-Host $header
Write-Host ("-" * $header.Length)

foreach ($r in $results) {
    $v = ([string]$r.Video).PadRight($colW.V)
    $w = ([string]$r.Workspace).PadRight($colW.W)
    $s = ([string]$r.Status).PadRight($colW.S)
    $n = if ($r.Note) { $r.Note } else { "-" }
    Write-Host "$v  $w  $s  $n"
}

Write-Host ""
