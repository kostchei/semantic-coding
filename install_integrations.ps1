<#
.SYNOPSIS
    Idempotent installer for grepai-hybrid AI agent integrations
.DESCRIPTION
    Configures Claude Code, OpenAI Codex CLI, and Google Antigravity to seamlessly
    use grepai-hybrid. Deduplicates MCP registrations, installs global instructions,
    hooks, and skills, backing up all modified configuration files.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

& python (Join-Path $ScriptDir "integrations\install.py")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Integration install failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
