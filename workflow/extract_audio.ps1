# Extract 16kHz mono WAV from a workspace's source video.
#
# Usage:
#   .\workflow\extract_audio.ps1 -Workspace "C:\workspace\wisper-page\workspaces\my-video"
#
# Reads <workspace>/.video-path (written by new_workspace.ps1) to find the source.
# If .video-path is missing, pass -VideoFile explicitly.
param(
    [Parameter(Mandatory)][string]$Workspace,
    [string]$VideoFile
)
$ErrorActionPreference = "Stop"

# (a) Check ffmpeg is on PATH
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    $Error.Clear()
    Write-Error "ffmpeg not found on PATH. Install ffmpeg and ensure it is accessible."
    exit 1
}

if (-not (Test-Path $Workspace)) {
    Write-Error "workspace not found: $Workspace"
    exit 1
}

$videoMemo = Join-Path $Workspace ".video-path"
if (-not $VideoFile) {
    if (Test-Path $videoMemo) {
        $VideoFile = (Get-Content $videoMemo -Raw -Encoding utf8).Trim()
    } else {
        Write-Error "no .video-path in workspace, pass -VideoFile explicitly"
        exit 1
    }
}

# -LiteralPath: '[' ']' in filenames (e.g. "[지피터스]") are wildcard chars otherwise.
if (-not (Test-Path -LiteralPath $VideoFile)) {
    Write-Error "source video not found: $VideoFile"
    exit 1
}

$audio = Join-Path $Workspace "audio.wav"

# (c) If audio.wav already exists, validate it is > 1KB; if smaller, remove and re-extract
if (Test-Path $audio) {
    $audioSize = (Get-Item $audio).Length
    if ($audioSize -gt 1KB) {
        Write-Host "audio.wav already exists and is valid, skipping: $audio"
        exit 0
    } else {
        Write-Warning "stale/empty audio removed: $audio (size: $audioSize bytes)"
        Remove-Item $audio -Force
    }
}

Write-Host "extracting: $VideoFile -> $audio"
# (b) Invoke ffmpeg via call operator with quoted paths and -y flag
& ffmpeg -i "$VideoFile" -ar 16000 -ac 1 -y "$audio"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ffmpeg failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "done: $audio"

# (d) Best-effort: stamp the 'audio' stage in the pipeline manifest
try {
    $manifestPy = Join-Path $PSScriptRoot "lib\manifest.py"
    python "$manifestPy" "$Workspace" set audio 2>$null
} catch {}

Write-Host ""
# (e) Updated next: hint points to transcribe.ps1
Write-Host "next: .\workflow\transcribe.ps1 -Workspace `"$Workspace`""
