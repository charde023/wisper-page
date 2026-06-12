# Create a new workspace folder for a video.
#
# Usage:
#   .\workflow\new_workspace.ps1 -VideoFile "C:\path\to\video.mp4"
#   .\workflow\new_workspace.ps1 -VideoFile "video.mp4" -Name "my-custom-ws"
#   .\workflow\new_workspace.ps1 -VideoFile "video.mp4" -Force
#
# Creates: <project-root>/workspaces/<sanitized-basename>/
# Saves the video absolute path in .video-path and initialises pipeline.json.
# Scripts (transcribe.py, make_html.py) are NOT copied — the canonical versions
# in workflow/_template/ are invoked centrally with --workspace.
param(
    [Parameter(Mandatory)][string]$VideoFile,
    [string]$Name,
    [switch]$Force
)
$ErrorActionPreference = "Stop"

$scriptDir  = $PSScriptRoot
$rootDir    = Split-Path -Parent $scriptDir
$workspacesDir = Join-Path $rootDir "workspaces"

# ---------------------------------------------------------------------------
# Resolve video path
# ---------------------------------------------------------------------------
if ([System.IO.Path]::IsPathRooted($VideoFile)) {
    $videoPath = $VideoFile
} elseif (Test-Path -LiteralPath $VideoFile) {
    $videoPath = (Resolve-Path -LiteralPath $VideoFile).Path
} else {
    Write-Error "video file not found: $VideoFile (try an absolute path)"
    exit 1
}

# -LiteralPath: filenames like "[지피터스] ...mp4" contain '[' ']' which
# PowerShell otherwise treats as wildcard character classes (match fails).
if (-not (Test-Path -LiteralPath $videoPath)) {
    Write-Error "video file not found at resolved path: $videoPath"
    exit 1
}

# ---------------------------------------------------------------------------
# Determine workspace folder name
# ---------------------------------------------------------------------------
$originalBase = [System.IO.Path]::GetFileNameWithoutExtension($videoPath)

if ($Name) {
    $wsName = $Name
} else {
    # Sanitize: replace spaces, parentheses, brackets, and other shell-hostile
    # characters with '-'. Korean characters, existing dashes, underscores, and
    # dots are preserved.
    $wsName = $originalBase -replace '[\s()\[\]{}&!@#$%^*+=|\\/<>:;,"''`~]', '-'
    # Collapse multiple consecutive dashes into one
    $wsName = $wsName -replace '-{2,}', '-'
    # Trim leading/trailing dashes
    $wsName = $wsName.Trim('-')
    if (-not $wsName) { $wsName = "workspace" }
}

Write-Host "original filename : $originalBase"
Write-Host "workspace name    : $wsName"

$workspace = Join-Path $workspacesDir $wsName

# ---------------------------------------------------------------------------
# Create workspaces root if needed
# ---------------------------------------------------------------------------
if (-not (Test-Path $workspacesDir)) {
    New-Item -ItemType Directory -Path $workspacesDir | Out-Null
}

# ---------------------------------------------------------------------------
# Handle existing workspace
# ---------------------------------------------------------------------------
if (Test-Path $workspace) {
    if ($Force) {
        Write-Host "workspace already exists — -Force given, re-initialising: $workspace"
    } else {
        Write-Warning "workspace already exists, leaving as-is: $workspace"
        exit 0
    }
} else {
    New-Item -ItemType Directory -Path $workspace | Out-Null
    Write-Host "created workspace : $workspace"
}

# ---------------------------------------------------------------------------
# Write .video-path
# ---------------------------------------------------------------------------
Set-Content -Path (Join-Path $workspace ".video-path") -Value $videoPath -Encoding utf8 -NoNewline
Write-Host "video path stored : $videoPath"

# ---------------------------------------------------------------------------
# ffprobe — best-effort duration
# ---------------------------------------------------------------------------
$ffprobeDuration = $null
try {
    $ffprobeCmd = Get-Command ffprobe -ErrorAction SilentlyContinue
    if ($ffprobeCmd) {
        $durStr = & ffprobe -i $videoPath -show_entries format=duration -v quiet -of csv="p=0" 2>$null
        if ($durStr -and $durStr -match '^\d') {
            $ffprobeDuration = [double]$durStr
            $mins = [math]::Round($ffprobeDuration / 60, 1)
            $hrs  = $ffprobeDuration / 3600
            $gpuEst  = [math]::Ceiling($hrs * 5)
            $cpuEst  = [math]::Ceiling($hrs * 30)
            Write-Host ""
            Write-Host "video duration    : $mins min"
            Write-Host "transcription est : ~${gpuEst} min (GPU) / ~${cpuEst} min (CPU)"
        }
    } else {
        Write-Host "(ffprobe not found — skipping duration check)"
    }
} catch {
    Write-Host "(ffprobe failed — skipping duration check)"
}

# ---------------------------------------------------------------------------
# Initialise pipeline.json via manifest.py
# ---------------------------------------------------------------------------
Write-Host ""
$pythonCmd = $null
try { $pythonCmd = (Get-Command python -ErrorAction Stop).Source } catch {}
if (-not $pythonCmd) {
    try { $pythonCmd = (Get-Command python3 -ErrorAction Stop).Source } catch {}
}

$manifestPy = Join-Path $scriptDir "lib\manifest.py"

if ($pythonCmd -and (Test-Path $manifestPy)) {
    Write-Host "initialising pipeline.json..."
    & $pythonCmd $manifestPy $workspace init --video $videoPath --language ko --mode lecture
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "manifest.py exited with code $LASTEXITCODE — pipeline.json may be incomplete"
    }
} else {
    if (-not $pythonCmd) { Write-Warning "python not found — skipping pipeline.json init" }
    if (-not (Test-Path $manifestPy)) { Write-Warning "manifest.py not found at $manifestPy — skipping pipeline.json init" }
}

# ---------------------------------------------------------------------------
# Next step hint
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "next steps:"
Write-Host "  1. .\workflow\extract_audio.ps1 -Workspace `"$workspace`""
Write-Host "  2. .\workflow\transcribe.ps1    -Workspace `"$workspace`"   (or run transcribe.py with --workspace)"
