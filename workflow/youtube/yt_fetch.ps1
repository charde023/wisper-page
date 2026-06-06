# Fetch a YouTube video's audio into a workspace, ready for transcribe.ps1.
#
# yt-dlp downloads bestaudio and post-processes to 16kHz mono WAV directly
# (collapses download + extract_audio into one step). Writes youtube.json
# (metadata + provenance) and initialises pipeline.json (mode transcribe-only).
#
# Usage:
#   .\workflow\youtube\yt_fetch.ps1 -Url "https://youtu.be/VIDEO_ID"
#   .\workflow\youtube\yt_fetch.ps1 -Url "..." -RootDir "C:\workspace\wisper-page"
param(
    [Parameter(Mandatory)][string]$Url,
    [string]$RootDir,
    [switch]$Force
)
$ErrorActionPreference = "Stop"

$ytDir   = $PSScriptRoot
$wfDir   = Split-Path -Parent $ytDir
$projRoot = if ($RootDir) { $RootDir } else { Split-Path -Parent $wfDir }
$workspacesDir = Join-Path $projRoot "workspaces"

# Resolve yt-dlp + python
if (-not (Get-Command yt-dlp -ErrorAction SilentlyContinue)) {
    Write-Error "yt-dlp not found on PATH."; exit 1
}
$pythonExe = $null
try { $pythonExe = (Get-Command python -ErrorAction Stop).Source } catch {}
if (-not $pythonExe) { try { $pythonExe = (Get-Command python3 -ErrorAction Stop).Source } catch {} }

# Load JS runtime from config (default node)
$jsRuntime = "node"
$cfgExample = Join-Path $ytDir "config.example.json"
$cfgLocal   = Join-Path $ytDir "config.json"
foreach ($c in @($cfgExample, $cfgLocal)) {
    if (Test-Path $c) {
        try { $j = Get-Content $c -Raw -Encoding utf8 | ConvertFrom-Json; if ($j.ytJsRuntime) { $jsRuntime = $j.ytJsRuntime } } catch {}
    }
}

# 1. Resolve video id
Write-Host "resolving video id..."
$videoId = (& yt-dlp --js-runtimes $jsRuntime --skip-download --no-warnings --print "%(id)s" $Url 2>$null | Select-Object -First 1)
if (-not $videoId) { Write-Error "could not resolve video id for: $Url"; exit 1 }
$videoId = $videoId.Trim()
Write-Host "video id          : $videoId"

# 2. Workspace
if (-not (Test-Path $workspacesDir)) { New-Item -ItemType Directory -Path $workspacesDir | Out-Null }
$ws = Join-Path $workspacesDir "yt-$videoId"
if (-not (Test-Path $ws)) { New-Item -ItemType Directory -Path $ws | Out-Null }
Write-Host "workspace         : $ws"
Set-Content -Path (Join-Path $ws ".source-url") -Value $Url -Encoding utf8 -NoNewline

# 3. Download audio -> 16k mono wav (+ info json), unless already present
$audio = Join-Path $ws "audio.wav"
if ((Test-Path $audio) -and ((Get-Item $audio).Length -gt 1KB) -and (-not $Force)) {
    Write-Host "audio.wav exists, skipping download (use -Force to redo)"
} else {
    Write-Host "downloading audio (16kHz mono wav)..."
    & yt-dlp --js-runtimes $jsRuntime -x --audio-format wav `
        --postprocessor-args "-ar 16000 -ac 1" `
        --write-info-json --no-warnings `
        -o "$ws\audio.%(ext)s" $Url
    if (-not (Test-Path $audio) -or ((Get-Item $audio).Length -le 1KB)) {
        Write-Error "audio.wav not produced or too small. (If throttled, try: yt-dlp --remote-components ejs:github ...)"
        exit 1
    }
}
Write-Host "audio ok          : $([math]::Round((Get-Item $audio).Length / 1MB, 1)) MB"

# 4. youtube.json (metadata + provenance)
$provPy = Join-Path $ytDir "extract_provenance.py"
if ($pythonExe -and (Test-Path $provPy)) {
    Write-Host "extracting metadata + provenance..."
    & $pythonExe $provPy --workspace $ws
} else {
    Write-Warning "skipping provenance (python or extract_provenance.py missing)"
}

# 5. pipeline.json (mode transcribe-only) + stamp audio
$manifestPy = Join-Path $wfDir "lib\manifest.py"
if ($pythonExe -and (Test-Path $manifestPy)) {
    & $pythonExe $manifestPy $ws init --mode "transcribe-only" --language "auto" --video $Url 2>$null
    & $pythonExe $manifestPy $ws set audio 2>$null
}

Write-Host ""
Write-Host "next: .\workflow\transcribe.ps1 -Workspace `"$ws`" -Language auto -Model large-v3 -Device cuda"
# Emit workspace path on the last line for orchestrators to capture
Write-Output $ws
