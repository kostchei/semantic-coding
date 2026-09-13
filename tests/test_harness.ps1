$ErrorActionPreference = 'Stop'
$harness = Get-Content (Join-Path $PSScriptRoot '..\run_agent_harness.ps1') -Raw
$parseTokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseInput($harness, [ref]$parseTokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Exercise the actual event-validation block without launching billable agents.
$validation = [scriptblock]::Create($harness.Substring($harness.IndexOf('$usedHybrid = $false')))
$eventsPath = [System.IO.Path]::GetTempFileName()
$errorsPath = 'fixture-only'
$agentExit = 0
$cases = @(
    @{Agent='codex'; Pass=$true; Events=@(
        '{"type":"item.completed","item":{"type":"mcp_tool_call","server":"grepai_hybrid","tool":"search_codebase","status":"completed","result":{}}}',
        '{"type":"turn.completed"}')},
    @{Agent='codex'; Pass=$false; Events=@('{"type":"turn.completed"}')},
    @{Agent='codex'; Pass=$false; Events=@(
        '{"type":"item.completed","item":{"type":"mcp_tool_call","server":"grepai_hybrid","tool":"search_codebase","status":"failed","error":"offline"}}',
        '{"type":"turn.completed"}')},
    @{Agent='claude'; Pass=$true; Events=@(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"mcp__grepai_hybrid__search_codebase"}]}}',
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"results"}]}}',
        '{"type":"result","subtype":"success","is_error":false}')},
    @{Agent='claude'; Pass=$false; Events=@(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"mcp__grepai_hybrid__search_codebase"}]}}',
        '{"type":"result","subtype":"success","is_error":false}')},
    @{Agent='claude'; Pass=$false; Events=@(
        '{"type":"result","subtype":"error_during_execution","is_error":true}')}
)
try {
    foreach ($case in $cases) {
        $Agent = $case.Agent
        $case.Events | Set-Content -LiteralPath $eventsPath -Encoding utf8
        $passed = $true
        try { & $validation } catch { $passed = $false }
        if ($passed -ne $case.Pass) { throw "Unexpected validation outcome for $($case | ConvertTo-Json -Compress)" }
    }
    Write-Host "All $($cases.Count) harness event checks passed."
} finally { Remove-Item -LiteralPath $eventsPath -Force }
