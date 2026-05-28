# deploy.ps1 — One-command publish for steps 6-7 (make_html -> stage -> copy -> index -> git push -> verify).
#
# CALLER NOTE (per CLAUDE.md section 5): Before invoking this script, Claude MUST confirm
# with the user which repository to push to. Default is pageRepoPath from config, but the
# user may specify a different target. Never push without that confirmation.
#
# Usage:
#   .\workflow\deploy.ps1 -Workspace "C:\workspace\wisper-page\workspaces\my-ws" -Slug "2026-05-29-topic"
#   .\workflow\deploy.ps1 -Workspace "..." -Slug "..." -PageRepo "C:\Users\inwon\Documents\page-repo"
#   .\workflow\deploy.ps1 -Workspace "..." -Slug "..." -NoVerify
#
# Steps performed:
#   1. Rebuild index.html if missing or older than guide.md (make_html.py --workspace <ws>)
#   2. Stage artifacts into publish/<slug>/ (stage_publish.py)
#   3. Copy <ws>/publish/<slug> -> <pageRepo>/<slug>
#   4. Regenerate root index.html in pageRepo (update_pages_index.py)
#   5. git add -A; git commit; git pull --rebase origin main; git push origin main
#   6. Poll live URL for HTTP 200 (unless -NoVerify)
#   7. Best-effort: stamp 'deployed' stage in pipeline.json

param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$Slug,
    [string]$PageRepo,
    [switch]$NoVerify
)
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-Python([string[]]$Args, [string]$ErrorContext) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { $cmd = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $cmd) { Write-Error "python not found on PATH"; exit 1 }
    & $cmd.Source @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "${ErrorContext}: python exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

# ---------------------------------------------------------------------------
# Resolve script and project paths
# ---------------------------------------------------------------------------
$scriptDir  = $PSScriptRoot   # workflow/
$projectDir = Split-Path -Parent $scriptDir

# ---------------------------------------------------------------------------
# Load config (pageRepoPath + pageBaseUrl)
# ---------------------------------------------------------------------------
$cfgPath = Join-Path $scriptDir "config.json"
if (-not (Test-Path $cfgPath)) {
    $cfgPath = Join-Path $scriptDir "config.example.json"
}
$cfg = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json

$pageBaseUrl = if ($cfg.pageBaseUrl) { $cfg.pageBaseUrl.TrimEnd('/') } else { "https://charde023.github.io/page" }

# -PageRepo param overrides config; if neither set, error out
if (-not $PageRepo) {
    $PageRepo = $cfg.pageRepoPath
}
if (-not $PageRepo) {
    Write-Error "PageRepo is not set. Pass -PageRepo or set pageRepoPath in workflow/config.json."
    exit 1
}
$PageRepo = $PageRepo.TrimEnd('\').TrimEnd('/')

# ---------------------------------------------------------------------------
# Validate workspace and slug
# ---------------------------------------------------------------------------
$Workspace = $Workspace.TrimEnd('\').TrimEnd('/')
if (-not (Test-Path $Workspace)) {
    Write-Error "workspace not found: $Workspace"
    exit 1
}
if (-not (Test-Path $PageRepo)) {
    Write-Error "page repo not found: $PageRepo"
    exit 1
}

Write-Host "workspace : $Workspace"
Write-Host "slug      : $Slug"
Write-Host "page repo : $PageRepo"
Write-Host "base url  : $pageBaseUrl"

# ---------------------------------------------------------------------------
# Step 1: Rebuild index.html if missing or stale
# ---------------------------------------------------------------------------
Write-Step "Step 1: Checking index.html freshness"

$htmlPath   = Join-Path $Workspace "index.html"
$guidePath  = Join-Path $Workspace "guide.md"
$makeHtmlPy = Join-Path $scriptDir "_template\make_html.py"

if (-not (Test-Path $guidePath)) {
    Write-Error "guide.md not found in workspace: $Workspace"
    exit 1
}

$needRebuild = $false
if (-not (Test-Path $htmlPath)) {
    Write-Host "index.html missing — rebuilding."
    $needRebuild = $true
} else {
    $htmlMtime  = (Get-Item $htmlPath).LastWriteTimeUtc
    $guideMtime = (Get-Item $guidePath).LastWriteTimeUtc
    if ($guideMtime -gt $htmlMtime) {
        Write-Host "index.html is older than guide.md — rebuilding."
        $needRebuild = $true
    } else {
        Write-Host "index.html is up to date."
    }
}

if ($needRebuild) {
    Invoke-Python @($makeHtmlPy, "--workspace", $Workspace) -ErrorContext "make_html.py"
    Write-Host "index.html rebuilt."
}

# ---------------------------------------------------------------------------
# Step 2: Stage artifacts into publish/<slug>/
# ---------------------------------------------------------------------------
Write-Step "Step 2: Staging artifacts"

$stagePy = Join-Path $scriptDir "stage_publish.py"
Invoke-Python @($stagePy, $Workspace, "--slug", $Slug, "--page-url", $pageBaseUrl) `
    -ErrorContext "stage_publish.py"

$publishDir = Join-Path $Workspace "publish\$Slug"
if (-not (Test-Path $publishDir)) {
    Write-Error "expected publish dir not found after staging: $publishDir"
    exit 1
}
Write-Host "staged at: $publishDir"

# ---------------------------------------------------------------------------
# Step 3: Copy to page repo
# ---------------------------------------------------------------------------
Write-Step "Step 3: Copying to page repo"

$destDir = Join-Path $PageRepo $Slug
# Copy-Item -Recurse -Force handles both new and existing destination dirs
Copy-Item -Path $publishDir -Destination $PageRepo -Recurse -Force
Write-Host "copied -> $destDir"

# ---------------------------------------------------------------------------
# Step 4: Regenerate root index.html
# ---------------------------------------------------------------------------
Write-Step "Step 4: Updating root index.html"

$updateIndexPy = Join-Path $scriptDir "update_pages_index.py"
Invoke-Python @($updateIndexPy, $PageRepo) -ErrorContext "update_pages_index.py"

# update_pages_index.py writes index.html.bak as a safety net; don't commit it into the page repo.
$bakPath = Join-Path $PageRepo "index.html.bak"
if (Test-Path $bakPath) { Remove-Item $bakPath -Force; Write-Host "removed index.html.bak (not committed)" }

# ---------------------------------------------------------------------------
# Step 5: git add / commit / pull --rebase / push  (in pageRepo)
# ---------------------------------------------------------------------------
Write-Step "Step 5: git commit + push"

Push-Location $PageRepo
try {
    git add -A
    if ($LASTEXITCODE -ne 0) { Write-Error "git add failed"; exit 1 }

    # Check if there is anything to commit
    $statusOut = git status --porcelain
    if (-not $statusOut) {
        Write-Host "nothing to commit — page repo already up to date."
    } else {
        git commit -m "add $Slug"
        if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed"; exit 1 }
    }

    # Always pull --rebase before push to avoid 'fetch first' rejection
    Write-Host "pulling with --rebase..."
    git pull --rebase origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git pull --rebase failed. Resolve conflicts, then push manually."
        exit 1
    }

    Write-Host "pushing..."
    git push origin main
    if ($LASTEXITCODE -ne 0) {
        # One retry after a second pull --rebase (handles rare race with concurrent push)
        Write-Warning "push failed — retrying after another pull --rebase..."
        git pull --rebase origin main
        git push origin main
        if ($LASTEXITCODE -ne 0) {
            Write-Error "git push failed after retry. Push manually: cd `"$PageRepo`" && git push origin main"
            exit 1
        }
    }

    Write-Host "pushed to origin/main."
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Step 6: Poll live URL for HTTP 200 (unless -NoVerify)
# ---------------------------------------------------------------------------
$liveUrl = "$pageBaseUrl/$Slug/"

if ($NoVerify) {
    Write-Host ""
    Write-Host "(-NoVerify set — skipping live check)"
    Write-Host "live URL: $liveUrl"
} else {
    Write-Step "Step 6: Verifying live URL (up to 10 tries x 15 s)"
    Write-Host "target: $liveUrl"

    $maxTries  = 10
    $delaySec  = 15
    $confirmed = $false

    for ($i = 1; $i -le $maxTries; $i++) {
        Write-Host "  attempt $i/$maxTries ..." -NoNewline
        try {
            # UseBasicParsing avoids IE engine dependency; -TimeoutSec keeps each try snappy
            $resp = Invoke-WebRequest -Uri $liveUrl -UseBasicParsing -TimeoutSec 10 `
                        -ErrorAction SilentlyContinue
            if ($resp -and $resp.StatusCode -eq 200) {
                Write-Host " 200 OK"
                $confirmed = $true
                break
            } else {
                $code = if ($resp) { $resp.StatusCode } else { "no response" }
                Write-Host " $code"
            }
        } catch {
            Write-Host " error: $($_.Exception.Message)"
        }

        if ($i -lt $maxTries) {
            Write-Host "  waiting ${delaySec}s..."
            Start-Sleep -Seconds $delaySec
        }
    }

    if ($confirmed) {
        Write-Host ""
        Write-Host "live and verified: $liveUrl" -ForegroundColor Green
    } else {
        Write-Warning "URL did not return 200 within $($maxTries * $delaySec) s. GitHub Pages may still be building."
        Write-Host "check manually: $liveUrl"
    }
}

# ---------------------------------------------------------------------------
# Step 7: Best-effort manifest stamp
# ---------------------------------------------------------------------------
try {
    $manifestPy = Join-Path $scriptDir "lib\manifest.py"
    python $manifestPy "$Workspace" set deployed 2>$null
} catch {}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "deploy complete." -ForegroundColor Green
Write-Host "  slug     : $Slug"
Write-Host "  live url : $liveUrl"
