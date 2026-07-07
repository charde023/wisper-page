# publish_report.ps1 — MD 보고서 1개를 GitHub Pages에 발행한다.
#
# Usage:
#   .\workflow\publish_report.ps1 `
#       -Report "C:\workspace\obsidian\charde_n\APOM\보고서\주간보고\2026-W23.md" `
#       -Type weekly `
#       -Slug "2026-W23"
#
#   .\workflow\publish_report.ps1 `
#       -Report "...\중간보고\2026-06-02-datacenter.md" `
#       -Type interim `
#       -Slug "2026-06-02-datacenter"
#
# Optional:
#   -PageRepo  "C:\workspace\page"   (default: config.json pageRepoPath)
#   -BaseUrl   "https://..."         (default: config.json pageBaseUrl)
#   -NoVerify                        (skip live URL check)
#
# Steps:
#   1. Validate inputs
#   2. Copy report.md -> page/reports/{type}/{slug}/report.md
#   3. make_report_html.py -> index.html
#   4. update_reports_index.py -> rebuild all index pages
#   5. git add / commit / pull --rebase / push
#   6. Print live URL

param(
    [Parameter(Mandatory)][string]$Report,
    [Parameter(Mandatory)][ValidateSet("weekly","interim")][string]$Type,
    [Parameter(Mandatory)][string]$Slug,
    [string]$PageRepo,
    [string]$BaseUrl,
    [switch]$NoVerify
)
$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Invoke-Py([string[]]$PyArgs, [string]$Ctx) {
    $pyCmd = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $pyCmd) { $pyCmd = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $pyCmd) { Write-Error "python not found"; exit 1 }
    & $pyCmd.Source @PyArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "${Ctx} failed (exit $LASTEXITCODE)"; exit $LASTEXITCODE }
}

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
$scriptDir  = $PSScriptRoot
$projectDir = Split-Path -Parent $scriptDir

$cfgPath = Join-Path $scriptDir "config.json"
if (-not (Test-Path $cfgPath)) { $cfgPath = Join-Path $scriptDir "config.example.json" }
$cfg = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json

if (-not $PageRepo) { $PageRepo = $cfg.pageRepoPath }
if (-not $PageRepo) { Write-Error "PageRepo not set. Pass -PageRepo or set pageRepoPath in config.json"; exit 1 }
$PageRepo = $PageRepo.TrimEnd('\').TrimEnd('/')

if (-not $BaseUrl) { $BaseUrl = if ($cfg.pageBaseUrl) { $cfg.pageBaseUrl.TrimEnd('/') } else { "https://charde023.github.io/page" } }

$reportPath = (Resolve-Path $Report -ErrorAction Stop).Path

if (-not (Test-Path $PageRepo)) { Write-Error "page repo not found: $PageRepo"; exit 1 }
if (-not (Test-Path $reportPath)) { Write-Error "report not found: $reportPath"; exit 1 }

Write-Host "report   : $reportPath"
Write-Host "type     : $Type"
Write-Host "slug     : $Slug"
Write-Host "page repo: $PageRepo"
Write-Host "base url : $BaseUrl"

# ---------------------------------------------------------------------------
# Step 1: Prepare destination folder
# ---------------------------------------------------------------------------
Write-Step "Step 1: Preparing destination folder"

$destDir = Join-Path $PageRepo "reports\$Type\$Slug"
New-Item -ItemType Directory -Force $destDir | Out-Null
Write-Host "dest: $destDir"

# ---------------------------------------------------------------------------
# Step 2: Copy report.md
# ---------------------------------------------------------------------------
Write-Step "Step 2: Copying report.md"

$destMd = Join-Path $destDir "report.md"
Copy-Item -Force $reportPath $destMd
Write-Host "copied -> $destMd"

# ---------------------------------------------------------------------------
# Step 3: Generate index.html
# ---------------------------------------------------------------------------
Write-Step "Step 3: Generating index.html"

$makeReportPy = Join-Path $scriptDir "_template\make_report_html.py"
if (-not (Test-Path $makeReportPy)) {
    Write-Error "make_report_html.py not found at $makeReportPy"
    exit 1
}

Invoke-Py @($makeReportPy, "--input", $destMd, "--base-url", $BaseUrl) -Ctx "make_report_html.py"

$destHtml = Join-Path $destDir "index.html"
if (-not (Test-Path $destHtml)) { Write-Error "index.html not generated"; exit 1 }
Write-Host "generated: $destHtml"

# ---------------------------------------------------------------------------
# Step 4: Rebuild index pages
# ---------------------------------------------------------------------------
Write-Step "Step 4: Rebuilding reports index pages"

$updateIndexPy = Join-Path $scriptDir "update_reports_index.py"
if (-not (Test-Path $updateIndexPy)) {
    Write-Error "update_reports_index.py not found at $updateIndexPy"
    exit 1
}

Invoke-Py @($updateIndexPy, $PageRepo, $BaseUrl) -Ctx "update_reports_index.py"

# ---------------------------------------------------------------------------
# Step 5: git commit + push
# ---------------------------------------------------------------------------
Write-Step "Step 5: git commit + push"

Push-Location $PageRepo
try {
    git add "reports/"
    if ($LASTEXITCODE -ne 0) { Write-Error "git add failed"; exit 1 }

    $statusOut = git status --porcelain
    if (-not $statusOut) {
        Write-Host "nothing to commit — already up to date."
    } else {
        $commitMsg = "report: add $Type/$Slug"
        git commit -m $commitMsg
        if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed"; exit 1 }

        Write-Host "pulling --rebase..."
        git pull --rebase origin main
        if ($LASTEXITCODE -ne 0) { Write-Error "git pull --rebase failed"; exit 1 }

        Write-Host "pushing..."
        git push origin main
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "push failed — retrying after another pull..."
            git pull --rebase origin main
            git push origin main
            if ($LASTEXITCODE -ne 0) { Write-Error "push failed after retry"; exit 1 }
        }
        Write-Host "pushed."
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
$liveUrl = "$BaseUrl/reports/$Type/$Slug/"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "PUBLISHED" -ForegroundColor Green
Write-Host "  type     : $Type"
Write-Host "  slug     : $Slug"
Write-Host "  live URL : $liveUrl"
Write-Host "  index    : $BaseUrl/reports/$Type/"
Write-Host "================================================================" -ForegroundColor Green
