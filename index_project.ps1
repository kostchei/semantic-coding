<#
.SYNOPSIS
    Automated Multi-Project Hybrid Indexer for grepai
.DESCRIPTION
    Mirrors source code from any target project, provisions dual vector store configurations
    (137M text and 7B code), executes parallel indexing via grepai, and registers the project
    in the central hybrid workspace registry for AI daily drivers.
#>

param (
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$ProjectName,
    [string]$TextModel = "text-embedding-nomic-embed-text-v1.5@f32",
    [int]$TextDimensions = 768,
    [string]$CodeModel = "text-embedding-nomic-embed-code",
    [int]$CodeDimensions = 4096,
    [string]$Endpoint = "http://127.0.0.1:1234/v1",
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$BinPath = Join-Path $ScriptDir "bin\grepai.exe"

if (-not (Test-Path $BinPath)) {
    Write-Error "grepai.exe binary not found at $BinPath"
    exit 1
}

# Normalize project path
if (-not (Test-Path $ProjectPath)) {
    Write-Error "Target project path does not exist: $ProjectPath"
    exit 1
}
$ProjectPath = (Resolve-Path $ProjectPath).Path

if (-not $ProjectName) {
    $ProjectName = Split-Path -Leaf $ProjectPath
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       grepai Multi-Project Hybrid Indexing Engine          " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project Name: $ProjectName"
Write-Host "Source Path:  $ProjectPath"

# 1. Retrieve LM Studio token dynamically from Windows Credential Store
Write-Host "`n[1/5] Resolving authentication credentials securely..." -ForegroundColor Yellow
$token = ""
try {
    $token = python -c "import sys; sys.path.insert(0, '$($ScriptDir.Replace('\', '/'))'); import hybrid_search; print(hybrid_search.get_stored_credential('PraetorSilica/LMStudioDev'))"
    $token = $token.Trim()
} catch {
    Write-Warning "Could not read token from Windows Credential Store: $_"
}

if (-not $token) {
    $token = $env:LM_API_TOKEN
}

# 2. Prepare workspace directories
$WorkspaceBase = Join-Path $ScriptDir "workspaces\$ProjectName"
$TextWorkspace = Join-Path $WorkspaceBase "repo-text"
$CodeWorkspace = Join-Path $WorkspaceBase "repo-code"

New-Item -ItemType Directory -Path $TextWorkspace -Force | Out-Null
New-Item -ItemType Directory -Path $CodeWorkspace -Force | Out-Null

# 3. Mirror source files excluding heavy dependencies and build artifacts
Write-Host "`n[2/5] Mirroring source files (respecting exclusion filters)..." -ForegroundColor Yellow
$Excludes = @(
    ".git", ".venv", "venv", "node_modules", "artifacts", ".tools",
    ".stack", "dist", "build", "Cache", "User", "bin", "out", ".bootstrap",
    "AssetProcessorTemp", "_savebackup", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".promptfoo", ".idea", ".vscode"
)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
& robocopy $ProjectPath $TextWorkspace /MIR /XD $Excludes /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
& robocopy $ProjectPath $CodeWorkspace /MIR /XD $Excludes /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
$sw.Stop()

$fileCount = (Get-ChildItem -Path $TextWorkspace -Recurse -File).Count
Write-Host "Mirrored $fileCount source files in $($sw.ElapsedMilliseconds) ms." -ForegroundColor Green

# 4. Generate .grepai/config.yaml for both workspaces
Write-Host "`n[3/5] Provisioning dual vector store configurations..." -ForegroundColor Yellow

function New-GrepaiConfig([string]$model, [int]$dims, [int]$parallelism) {
    return @"
version: 1
embedder:
    provider: openai
    model: $model
    endpoint: $Endpoint
    api_key: $token
    dimensions: $dims
    parallelism: $parallelism
    request_timeout_seconds: 600
    max_retries: 5
store:
    backend: gob
chunking:
    size: 300
    overlap: 50
search:
    hybrid:
        enabled: false
"@
}

New-Item -ItemType Directory -Path (Join-Path $TextWorkspace ".grepai") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $CodeWorkspace ".grepai") -Force | Out-Null

Set-Content -Path (Join-Path $TextWorkspace ".grepai\config.yaml") -Value (New-GrepaiConfig -model $TextModel -dims $TextDimensions -parallelism 4)
Set-Content -Path (Join-Path $CodeWorkspace ".grepai\config.yaml") -Value (New-GrepaiConfig -model $CodeModel -dims $CodeDimensions -parallelism 2)

# Clean previous lock files
Remove-Item (Join-Path $TextWorkspace ".grepai\*.lock") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $CodeWorkspace ".grepai\*.lock") -Force -ErrorAction SilentlyContinue

# 5. Launch parallel indexing daemons
Write-Host "`n[4/5] Launching parallel indexing daemons (137M Text + 7B Code)..." -ForegroundColor Yellow

$stdoutText = Join-Path $TextWorkspace "watch_stdout.log"
$stderrText = Join-Path $TextWorkspace "watch_stderr.log"
$stdoutCode = Join-Path $CodeWorkspace "watch_stdout.log"
$stderrCode = Join-Path $CodeWorkspace "watch_stderr.log"

Remove-Item $stdoutText, $stderrText, $stdoutCode, $stderrCode -Force -ErrorAction SilentlyContinue

$procText = Start-Process -FilePath $BinPath `
    -ArgumentList "watch --no-ui" `
    -WorkingDirectory $TextWorkspace `
    -RedirectStandardOutput $stdoutText `
    -RedirectStandardError $stderrText `
    -PassThru

$procCode = Start-Process -FilePath $BinPath `
    -ArgumentList "watch --no-ui" `
    -WorkingDirectory $CodeWorkspace `
    -RedirectStandardOutput $stdoutCode `
    -RedirectStandardError $stderrCode `
    -PassThru

Write-Host "Process Text (PID: $($procText.Id)) | Process Code (PID: $($procCode.Id)) running." -ForegroundColor Cyan

$startTime = Get-Date
$textDone = $false
$codeDone = $false
$textStable = 0
$codeStable = 0
$lastTextSize = 0
$lastCodeSize = 0

$textIndexPath = Join-Path $TextWorkspace ".grepai\index.gob"
$codeIndexPath = Join-Path $CodeWorkspace ".grepai\index.gob"

while (-not ($textDone -and $codeDone)) {
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    if ($elapsed -gt $TimeoutSec) {
        Write-Warning "Timeout reached ($TimeoutSec s)."
        break
    }

    # Check Text
    if (-not $textDone) {
        if (Test-Path $textIndexPath) {
            $cur = (Get-Item $textIndexPath).Length
            if ($cur -gt 5000) {
                if ($cur -eq $lastTextSize) {
                    $textStable++
                    if ($textStable -ge 3) {
                        $textDone = $true
                        Write-Host "[OK] 137M Text index stabilized ($([math]::Round($cur/1KB, 1)) KB)." -ForegroundColor Green
                    }
                } else {
                    $textStable = 0
                    $lastTextSize = $cur
                }
            }
        }
    }

    # Check Code
    if (-not $codeDone) {
        if (Test-Path $codeIndexPath) {
            $cur = (Get-Item $codeIndexPath).Length
            if ($cur -gt 5000) {
                if ($cur -eq $lastCodeSize) {
                    $codeStable++
                    if ($codeStable -ge 3) {
                        $codeDone = $true
                        Write-Host "[OK] 7B Code index stabilized ($([math]::Round($cur/1KB, 1)) KB)." -ForegroundColor Green
                    }
                } else {
                    $codeStable = 0
                    $lastCodeSize = $cur
                }
            }
        }
    }

    Start-Sleep -Seconds 2
}

Stop-Process -Id $procText.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $procCode.Id -Force -ErrorAction SilentlyContinue

Remove-Item (Join-Path $TextWorkspace ".grepai\*.lock") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $CodeWorkspace ".grepai\*.lock") -Force -ErrorAction SilentlyContinue

# 6. Check indexing statuses
Write-Host "`n[5/5] Verifying index status..." -ForegroundColor Yellow

$textSizeKB = 0
$codeSizeKB = 0
if (Test-Path (Join-Path $TextWorkspace ".grepai\index.gob")) {
    $textSizeKB = [math]::Round(((Get-Item (Join-Path $TextWorkspace ".grepai\index.gob")).Length / 1KB), 1)
}
if (Test-Path (Join-Path $CodeWorkspace ".grepai\index.gob")) {
    $codeSizeKB = [math]::Round(((Get-Item (Join-Path $CodeWorkspace ".grepai\index.gob")).Length / 1KB), 1)
}

Write-Host "Text Index Size: ${textSizeKB} KB" -ForegroundColor Green
Write-Host "Code Index Size: ${codeSizeKB} KB" -ForegroundColor Green

# 7. Update central registry
$RegistryPath = Join-Path $ScriptDir "workspaces\registry.json"
$registry = @{}
if (Test-Path $RegistryPath) {
    try {
        $raw = Get-Content -Path $RegistryPath -Raw | ConvertFrom-Json
        foreach ($prop in $raw.PSObject.Properties) {
            $registry[$prop.Name] = $prop.Value
        }
    } catch {}
}

$registry[$ProjectName] = @{
    source_path = $ProjectPath
    text_dir = $TextWorkspace
    code_dir = $CodeWorkspace
    indexed_at = (Get-Date).ToString("o")
    text_size_kb = $textSizeKB
    code_size_kb = $codeSizeKB
    file_count = $fileCount
}

$registry | ConvertTo-Json -Depth 5 | Set-Content -Path $RegistryPath -Encoding utf8
Write-Host "`n[SUCCESS] Project '$ProjectName' registered in workspaces\registry.json." -ForegroundColor Green
Write-Host "You can now search with: python hybrid_search.py '<query>' --project $ProjectName" -ForegroundColor Cyan
