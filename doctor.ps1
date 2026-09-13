<#
.SYNOPSIS
    End-to-end health verification for grepai-hybrid and agent integrations
#>

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

& python -m semcode.doctor
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
