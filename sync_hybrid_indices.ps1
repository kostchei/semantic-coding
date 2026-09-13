<#
.SYNOPSIS
    Dual-Index Synchronizer for grepai Hybrid Pipeline
.DESCRIPTION
    Monitors a source directory for code changes, mirrors modified files to both
    the text-embedder and code-embedder workspaces, and updates both vector indices.
#>

param (
    [string]$Project,
    [string]$SourceDir = "$PSScriptRoot\grepai",
    [string]$TextRepo = "$PSScriptRoot\repo-text",
    [string]$CodeRepo = "$PSScriptRoot\repo-code",
    [int]$IntervalSec = 10,
    [switch]$Once = $false
)

$ErrorActionPreference = "Continue"
$BinPath = "$PSScriptRoot\bin\grepai.exe"

if (-not (Test-Path $BinPath)) {
    Write-Error "grepai.exe not found at $BinPath"
    exit 1
}

# Resolve project from registry if specified
if ($Project) {
    $regPath = Join-Path $PSScriptRoot "workspaces\registry.json"
    if (Test-Path $regPath) {
        try {
            $reg = Get-Content -Path $regPath -Raw -Encoding utf8 | ConvertFrom-Json
            if ($reg.PSObject.Properties[$Project]) {
                $pinfo = $reg.PSObject.Properties[$Project].Value
                $SourceDir = $pinfo.source_path
                $TextRepo = $pinfo.text_dir
                $CodeRepo = $pinfo.code_dir
                Write-Host "Resolved project '$Project' from registry." -ForegroundColor Cyan
            } else {
                Write-Warning "Project '$Project' not found in registry. Using default paths."
            }
        } catch {
            Write-Warning "Could not parse registry.json: $_"
        }
    }
}

function Sync-Workspace([string]$workspaceDir, [string]$label) {
    Write-Host "`n--> Updating $label index ($workspaceDir)..." -ForegroundColor Cyan
    $stdoutLog = Join-Path $workspaceDir "watch_stdout.log"
    $stderrLog = Join-Path $workspaceDir "watch_stderr.log"

    Remove-Item (Join-Path $workspaceDir ".grepai\*.lock") -Force -ErrorAction SilentlyContinue
    Remove-Item $stdoutLog -Force -ErrorAction SilentlyContinue
    Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue

    $proc = Start-Process -FilePath $BinPath `
        -ArgumentList "watch --no-ui" `
        -WorkingDirectory $workspaceDir `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru

    $startTime = Get-Date
    $committed = $false

    while (-not $proc.HasExited) {
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        $indexPath = Join-Path $workspaceDir ".grepai\index.gob"

        if (Test-Path $indexPath) {
            $idxItem = Get-Item $indexPath
            if ($idxItem.Length -gt 1000000) {
                # Verify stability over 3 seconds
                $prevLen = $idxItem.Length
                Start-Sleep -Seconds 3
                $currLen = (Get-Item $indexPath).Length
                if ($currLen -eq $prevLen) {
                    $committed = $true
                    break
                }
            }
        }

        if ($elapsed -gt 180) {
            Write-Warning "Timeout waiting for index sync in $workspaceDir"
            break
        }
        Start-Sleep -Seconds 3
    }

    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $workspaceDir ".grepai\*.lock") -Force -ErrorAction SilentlyContinue

    if ($committed) {
        Write-Host "[OK] $label index successfully updated." -ForegroundColor Green
    } else {
        Write-Warning "$label index may not have completed all files."
    }
}

function Get-SourceSnapshot([string]$path) {
    $snapshot = @{}
    Get-ChildItem -Path $path -Recurse -File | ForEach-Object {
        if ($_.FullName -notmatch "(\.git|\.grepai|vendor|node_modules)") {
            $snapshot[$_.FullName] = $_.LastWriteTimeUtc.Ticks
        }
    }
    return $snapshot
}

Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "         grepai Hybrid Dual-Index Synchronizer              " -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "Source Directory: $SourceDir"
Write-Host "Text Index:       $TextRepo"
Write-Host "Code Index:       $CodeRepo"

if ($Once) {
    Sync-Workspace -workspaceDir $TextRepo -label "137M Text Model"
    Sync-Workspace -workspaceDir $CodeRepo -label "7B Code Model"
    Write-Host "`n[DONE] Single reconciliation pass complete." -ForegroundColor Green
    exit 0
}

Write-Host "`nStarting continuous file watch (poll interval: ${IntervalSec}s)... Press Ctrl+C to stop." -ForegroundColor White
$lastSnapshot = Get-SourceSnapshot -path $SourceDir

while ($true) {
    Start-Sleep -Seconds $IntervalSec
    $currentSnapshot = Get-SourceSnapshot -path $SourceDir
    $changed = $false

    foreach ($file in $currentSnapshot.Keys) {
        if (-not $lastSnapshot.ContainsKey($file) -or $lastSnapshot[$file] -ne $currentSnapshot[$file]) {
            Write-Host "[CHANGE DETECTED] $file" -ForegroundColor Yellow
            $changed = $true
            break
        }
    }

    if ($changed) {
        # Mirror files to both workspaces
        robocopy $SourceDir $TextRepo /MIR /XD .git .grepai /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null
        robocopy $SourceDir $CodeRepo /MIR /XD .git .grepai /R:1 /W:1 /NFL /NDL /NJH /NJS | Out-Null

        Sync-Workspace -workspaceDir $TextRepo -label "137M Text Model"
        Sync-Workspace -workspaceDir $CodeRepo -label "7B Code Model"

        $lastSnapshot = Get-SourceSnapshot -path $SourceDir
    }
}
