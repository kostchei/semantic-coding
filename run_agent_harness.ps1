<# Repeatable MCP-first exploration. Credentials are inherited, never saved here. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('claude', 'codex')][string]$Agent,
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$OutputDir = "$PSScriptRoot\harness-results"
)
$ErrorActionPreference = 'Stop'
$ProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) { throw 'ProjectPath must be a directory.' }
$cli = (Get-Command $Agent -ErrorAction Stop).Source
$python = (Get-Command python -ErrorAction Stop).Source
$server = Join-Path $PSScriptRoot 'mcp_server.py'

# Resolve the project before spending an agent turn. A typo must not search another repo.
& $python -c 'import sys; sys.path.insert(0, sys.argv[1]); import hybrid_search; hybrid_search.resolve_project_dirs(project_path=sys.argv[2])' $PSScriptRoot $ProjectPath
if ($LASTEXITCODE -ne 0) { throw 'Project lookup failed. Index the project with index_project.ps1 first.' }
& $python -c 'import mcp.server.fastmcp'
if ($LASTEXITCODE -ne 0) { throw 'Install the MCP dependency: python -m pip install -r requirements.txt' }

if ($Agent -eq 'claude' -and -not ($env:ANTHROPIC_API_KEY -or $env:ANTHROPIC_AUTH_TOKEN -or $env:CLAUDE_CODE_OAUTH_TOKEN -or $env:CLAUDE_CODE_USE_BEDROCK -or $env:CLAUDE_CODE_USE_VERTEX -or $env:CLAUDE_CODE_USE_FOUNDRY)) {
    $authText = & $cli auth status
    $authExit = $LASTEXITCODE
    $auth = $null
    try { $auth = ($authText -join "`n") | ConvertFrom-Json } catch {}
    if ($authExit -ne 0 -or -not $auth.loggedIn) {
        throw 'Claude is not authenticated. Run claude auth login for a local session, or claude setup-token and set CLAUDE_CODE_OAUTH_TOKEN for unattended runs. ANTHROPIC_API_KEY is also supported. Never commit credentials.'
    }
}

$request = @"
Perform read-only exploration of the project at $ProjectPath.
Before exploratory shell searches, call the grepai_hybrid MCP tool search_codebase
with project set to the absolute path above and a semantic query relevant to the request.
If the tool fails or is unavailable, report the failure explicitly; do not claim hybrid retrieval succeeded.
After successful retrieval, use file reads or shell commands to verify the returned source evidence.
Do not edit files or delegate to other agents.

Request:
$Prompt
"@

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$runId = "$Agent-$([guid]::NewGuid().ToString('N'))"
$eventsPath = Join-Path $OutputDir "$runId.jsonl"
$errorsPath = Join-Path $OutputDir "$runId.stderr.log"
$mcpConfig = @{mcpServers = @{grepai_hybrid = @{command = $python; args = @($server)}}} | ConvertTo-Json -Depth 5 -Compress

Push-Location -LiteralPath $ProjectPath
try {
    if ($Agent -eq 'codex') {
        # JSON string quoting is also valid for these TOML string/array values.
        $commandValue = ConvertTo-Json -InputObject $python -Compress
        $argsValue = ConvertTo-Json -InputObject @($server) -Compress
        $request | & $cli exec --sandbox read-only --json `
            -c "mcp_servers.grepai_hybrid.command=$commandValue" `
            -c "mcp_servers.grepai_hybrid.args=$argsValue" `
            -c 'mcp_servers.grepai_hybrid.enabled=true' `
            -c 'mcp_servers.grepai_hybrid.required=true' - 2> $errorsPath |
            Set-Content -LiteralPath $eventsPath -Encoding utf8
    } else {
        $request | & $cli -p --output-format stream-json --verbose `
            --mcp-config $mcpConfig --strict-mcp-config `
            --tools Read --allowedTools 'Read,mcp__grepai_hybrid__search_codebase' `
            --permission-mode dontAsk 2> $errorsPath |
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
            $event.item.server -eq 'grepai_hybrid' -and $event.item.tool -eq 'search_codebase' -and
            $event.item.status -eq 'completed' -and -not $event.item.error -and -not $event.item.result.isError) { $usedHybrid = $true }
        if ($event.type -eq 'turn.failed' -or $event.type -eq 'error') { $agentFailed = $true }
    } else {
        foreach ($block in $event.message.content) {
            if ($block.type -eq 'tool_use' -and $block.name -eq 'mcp__grepai_hybrid__search_codebase') { $hybridCalls[$block.id] = $true }
            if ($block.type -eq 'tool_result' -and $hybridCalls.ContainsKey([string]$block.tool_use_id) -and -not $block.is_error) { $usedHybrid = $true }
            if ($block.type -eq 'tool_result' -and $block.is_error) { $agentFailed = $true }
        }
        if ($event.type -eq 'result' -and $event.is_error) { $agentFailed = $true }
        if ($event.type -eq 'result' -and $event.subtype -eq 'success' -and -not $event.is_error) { $completed = $true }
    }
}
Write-Host "Events: $eventsPath"
Write-Host "Diagnostics: $errorsPath"
if ($agentExit -ne 0 -or $agentFailed -or -not $completed) { throw 'Agent failed or did not finish. Inspect diagnostics; expired Claude credentials require login or a replacement setup-token/API key.' }
if (-not $usedHybrid) { throw 'Harness failed: no successful hybrid MCP usage was observed. Registration alone does not enforce tool selection.' }
Write-Host 'Harness passed: hybrid MCP usage observed.'
