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

if (-not (Test-Path $VideoFile)) {
    Write-Error "source video not found: $VideoFile"
    exit 1
}

$audio = Join-Path $Workspace "audio.wav"
if (Test-Path $audio) {
    Write-Host "audio.wav already exists, skipping: $audio"
    exit 0
}

Write-Host "extracting: $VideoFile -> $audio"
ffmpeg -i $VideoFile -ar 16000 -ac 1 $audio
if ($LASTEXITCODE -ne 0) {
    Write-Error "ffmpeg failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "done: $audio"
Write-Host ""
Write-Host "next: python `"$Workspace\transcribe.py`""
