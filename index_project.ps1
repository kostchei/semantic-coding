<#
.SYNOPSIS
    Automated Multi-Project Hybrid Indexer for grepai (Python backend)
.DESCRIPTION
    Mirrors source code from target project honoring .gitignore and mandatory excludes,
    provisions dual vector store configurations, executes indexing via semcode.indexer,
    and updates the central registry atomically.
#>

param (
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [string]$ProjectName,
    [string]$Endpoint = "http://127.0.0.1:1234/v1",
    [int]$TimeoutSec = 600
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

if (-not (Test-Path $ProjectPath)) {
    Write-Error "Target project path does not exist: $ProjectPath"
    exit 1
}

$cmdArgs = @("-m", "semcode.indexer", $ProjectPath, "--timeout", $TimeoutSec, "--endpoint", $Endpoint)
if ($ProjectName) {
    $cmdArgs += @("--name", $ProjectName)
}

& python $cmdArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Indexing failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
