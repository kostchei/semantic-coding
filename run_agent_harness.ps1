<# Repeatable MCP-first exploration. Credentials are inherited, never saved here. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('claude', 'codex')][string]$Agent,
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [Parameter(Mandatory = $true)][string]$Prompt,
    [ValidateSet('Instructed', 'Unprompted')][string]$Mode = 'Instructed',
    [string]$OutputDir = "$PSScriptRoot\harness-results"
)
$ErrorActionPreference = 'Stop'
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) { throw 'ProjectPath must be a directory.' }
$cli = (Get-Command $Agent -ErrorAction Stop).Source
$python = (Get-Command python -ErrorAction Stop).Source
$server = Join-Path $PSScriptRoot 'mcp_server.py'
$credentialHelper = Join-Path $PSScriptRoot 'secure_credentials.py'
$storedClaudeCredential = $false
if ($Agent -eq 'claude') {
    & $python $credentialHelper status
    $storedClaudeCredential = $LASTEXITCODE -eq 0
}

# In Instructed mode, verify project lookup before spending an agent turn.
if ($Mode -eq 'Instructed') {
    & $python -c 'import sys; sys.path.insert(0, sys.argv[1]); import hybrid_search; hybrid_search.resolve_project_dirs(project_path=sys.argv[2])' $PSScriptRoot $ProjectPath
    if ($LASTEXITCODE -ne 0) { throw 'Project lookup failed. Index the project with index_project.ps1 first.' }
}
& $python -c 'import mcp.server.fastmcp'
if ($LASTEXITCODE -ne 0) { throw 'Install the MCP dependency: python -m pip install -r requirements.txt' }

if ($Agent -eq 'claude' -and -not $storedClaudeCredential -and -not ($env:ANTHROPIC_API_KEY -or $env:ANTHROPIC_AUTH_TOKEN -or $env:CLAUDE_CODE_OAUTH_TOKEN -or $env:CLAUDE_CODE_USE_BEDROCK -or $env:CLAUDE_CODE_USE_VERTEX -or $env:CLAUDE_CODE_USE_FOUNDRY)) {
    $authText = & $cli auth status
    $authExit = $LASTEXITCODE
    $auth = $null
    try { $auth = ($authText -join "`n") | ConvertFrom-Json } catch {}
    if ($authExit -ne 0 -or -not $auth.loggedIn) {
        throw 'Claude is not authenticated. Run claude auth login for a local session, or claude setup-token and set CLAUDE_CODE_OAUTH_TOKEN for unattended runs. ANTHROPIC_API_KEY is also supported. Never commit credentials.'
    }
}

if ($Mode -eq 'Instructed') {
    $request = @"
Perform read-only exploration of the project at $ProjectPath.
Before exploratory shell searches, call the semcode MCP tool search_codebase
with project set to the absolute path above and a semantic query relevant to the request.
If the tool fails or is unavailable, report the failure explicitly; do not claim hybrid retrieval succeeded.
After successful retrieval, use file reads or shell commands to verify the returned source evidence.
Do not edit files or delegate to other agents.

Request:
$Prompt
"@
} else {
    # Unprompted mode: natural user prompt with no mention of semcode or search tools
    $request = $Prompt
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$runId = "$Agent-$Mode-$([guid]::NewGuid().ToString('N'))"
$eventsPath = Join-Path $OutputDir "$runId.jsonl"
$errorsPath = Join-Path $OutputDir "$runId.stderr.log"
$mcpConfig = @{mcpServers = @{semcode = @{command = $python; args = @($server)}}} | ConvertTo-Json -Depth 5 -Compress

Push-Location -LiteralPath $ProjectPath
try {
    if ($Agent -eq 'codex') {
        # JSON string quoting is also valid for these TOML string/array values.
        $commandValue = ConvertTo-Json -InputObject $python -Compress
        $argsValue = ConvertTo-Json -InputObject @($server) -Compress
        $codexArgs = @(
            "exec", "--sandbox", "read-only", "--json",
            "-c", "mcp_servers.semcode.command=$commandValue",
            "-c", "mcp_servers.semcode.args=$argsValue",
            "-c", "mcp_servers.semcode.enabled=true",
            "-c", 'mcp_servers.semcode.tools.search_codebase.approval_mode="approve"'
        )
        if ($Mode -eq 'Instructed') {
            $codexArgs += @("-c", 'mcp_servers.semcode.required=true')
        }
        $codexArgs += @("-")

        $request | & $cli $codexArgs 2> $errorsPath | Set-Content -LiteralPath $eventsPath -Encoding utf8
    } else {
        $claudeExtraArgs = @()
        if ($Mode -eq 'Instructed') {
            $claudeExtraArgs = @(
                "--mcp-config", $mcpConfig, "--strict-mcp-config",
                "--tools", "Read", "--allowedTools", "Read,mcp__semcode__search_codebase"
            )
        }
        $request | & $python $credentialHelper run --cli $cli -- -p --output-format stream-json --verbose `
            @claudeExtraArgs --permission-mode dontAsk 2> $errorsPath |
            Set-Content -LiteralPath $eventsPath -Encoding utf8
    }
    $agentExit = $LASTEXITCODE
} finally { Pop-Location }

$usedHybrid = $false
$agentFailed = $false
$completed = $false
$hybridCalls = @{}
foreach ($line in (Get-Content -LiteralPath $eventsPath)) {
    try { $event = $line | ConvertFrom-Json } catch { continue }
    if ($Agent -eq 'codex') {
        if ($event.type -eq 'turn.completed') { $completed = $true }
        if ($event.type -eq 'item.completed' -and $event.item.type -eq 'mcp_tool_call' -and
            $event.item.server -eq 'semcode' -and $event.item.tool -eq 'search_codebase' -and
            $event.item.status -eq 'completed' -and -not $event.item.error -and -not $event.item.result.isError) { $usedHybrid = $true }
        if ($event.type -eq 'turn.failed' -or $event.type -eq 'error') { $agentFailed = $true }
    } else {
        foreach ($block in $event.message.content) {
            if ($block.type -eq 'tool_use' -and $block.name -eq 'mcp__semcode__search_codebase') { $hybridCalls[$block.id] = $true }
            if ($block.type -eq 'tool_result' -and $hybridCalls.ContainsKey([string]$block.tool_use_id) -and -not $block.is_error) { $usedHybrid = $true }
            if ($block.type -eq 'tool_result' -and $block.is_error) { $agentFailed = $true }
        }
        if ($event.type -eq 'result' -and $event.is_error) { $agentFailed = $true }
        if ($event.type -eq 'result' -and $event.subtype -eq 'success' -and -not $event.is_error) { $completed = $true }
    }
}
Write-Host "Events: $eventsPath"
Write-Host "Diagnostics: $errorsPath"
if ($agentExit -ne 0 -or $agentFailed -or -not $completed) { throw "$Agent CLI failed or did not finish. Inspect the event and diagnostic files above for the specific error." }
if (-not $usedHybrid -and $Mode -ne 'Unprompted') { throw 'Harness failed: no successful hybrid MCP usage was observed. Registration alone does not enforce tool selection.' }
if ($usedHybrid) {
    Write-Host "Harness passed: hybrid MCP usage observed."
} else {
    Write-Host "Unprompted harness completed: tool-first hybrid usage was not triggered."
}
