<#
.SYNOPSIS
    Dual-Index Synchronizer for grepai Hybrid Pipeline (Python backend)
.DESCRIPTION
    Incrementally synchronizes source code changes to hybrid workspaces honoring .gitignore,
    removes deletions, and updates grepai vector stores.
#>

param (
    [string]$Project,
    [switch]$All = $false,
    [switch]$Force = $false,
    [switch]$Watch = $false,
    [int]$IntervalSec = 300
)

$ErrorActionPreference = "Stop"

$cmdArgs = @("-m", "semcode.sync")
if ($Project) {
    $cmdArgs += @("--project", $Project)
} elseif ($All) {
    $cmdArgs += @("--all")
} else {
    # Default to current directory or fail loudly via Python if unregistered
    $cmdArgs += @("--all")
}

if ($Force) {
    $cmdArgs += @("--force")
}
if ($Watch) {
    $cmdArgs += @("--watch", "--interval", $IntervalSec)
}

& python $cmdArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Sync failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
