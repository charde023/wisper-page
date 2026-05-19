# Create a new workspace folder for a video, seeded with _template scripts.
#
# Usage:
#   .\workflow\new_workspace.ps1 -VideoFile "C:\path\to\video.mp4"
#   .\workflow\new_workspace.ps1 -VideoFile "video.mp4"   (looks in workspaces/)
#
# Creates: <project-root>/workspaces/<video-basename>/  with transcribe.py + make_html.py
# Saves the video's absolute path in .video-path inside the workspace folder so
# extract_audio.ps1 can find it later without re-typing.
param(
    [Parameter(Mandatory)][string]$VideoFile
)
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$rootDir = Split-Path -Parent $scriptDir
$workspacesDir = Join-Path $rootDir "workspaces"
$template = Join-Path $scriptDir "_template"

# Resolve video path: absolute, relative to cwd, or filename inside workspaces/
if ([System.IO.Path]::IsPathRooted($VideoFile)) {
    $videoPath = $VideoFile
} elseif (Test-Path $VideoFile) {
    $videoPath = (Resolve-Path $VideoFile).Path
} else {
    Write-Error "video file not found: $VideoFile (try an absolute path)"
    exit 1
}

if (-not (Test-Path $videoPath)) {
    Write-Error "video file not found at resolved path: $videoPath"
    exit 1
}

$base = [System.IO.Path]::GetFileNameWithoutExtension($videoPath)
$workspace = Join-Path $workspacesDir $base

if (-not (Test-Path $workspacesDir)) {
    New-Item -ItemType Directory -Path $workspacesDir | Out-Null
}

if (Test-Path $workspace) {
    Write-Warning "workspace already exists, leaving as-is: $workspace"
    exit 0
}

New-Item -ItemType Directory -Path $workspace | Out-Null
Write-Host "created workspace: $workspace"

foreach ($file in @("transcribe.py", "make_html.py")) {
    Copy-Item (Join-Path $template $file) (Join-Path $workspace $file)
    Write-Host "copied: $file"
}

# Remember the source video path so subsequent scripts don't need it again.
Set-Content -Path (Join-Path $workspace ".video-path") -Value $videoPath -Encoding utf8 -NoNewline
Write-Host "remembered video path: $videoPath"

Write-Host ""
Write-Host "next: .\workflow\extract_audio.ps1 -Workspace `"$workspace`""
