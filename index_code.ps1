$ErrorActionPreference = "Continue"
$bin = "e:\Semantic_Coding\bin\grepai.exe"
$dir = "e:\Semantic_Coding\repo-code"
$stdoutLog = Join-Path $dir "watch_stdout.log"
$stderrLog = Join-Path $dir "watch_stderr.log"

Remove-Item (Join-Path $dir ".grepai\*.lock") -Force -ErrorAction SilentlyContinue
Remove-Item $stdoutLog -Force -ErrorAction SilentlyContinue
Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue

Write-Host "Starting grepai watch --no-ui in $dir..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $bin `
    -ArgumentList "watch --no-ui" `
    -WorkingDirectory $dir `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$startTime = Get-Date

while (-not $proc.HasExited) {
    $indexPath = Join-Path $dir ".grepai\index.gob"
    $symbolsPath = Join-Path $dir ".grepai\symbols.gob"
    $elapsed = ((Get-Date) - $startTime).TotalSeconds

    # Check stdout log for progress
    if (Test-Path $stdoutLog) {
        $lastLine = Get-Content $stdoutLog -Tail 1 -ErrorAction SilentlyContinue
        if ($lastLine) {
            Write-Host "[$([math]::Round($elapsed, 0))s] $lastLine"
        }
    }

    if ((Test-Path $indexPath) -and (Test-Path $symbolsPath)) {
        $idxItem = Get-Item $indexPath
        $symItem = Get-Item $symbolsPath
        if ($idxItem.Length -gt 1000000 -and $symItem.Length -gt 10000) {
            Write-Host "`n[SUCCESS] Index committed! index.gob: $($idxItem.Length) bytes, symbols.gob: $($symItem.Length) bytes in $([math]::Round($elapsed, 1))s" -ForegroundColor Green
            Start-Sleep -Seconds 3
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            break
        }
    }

    Start-Sleep -Seconds 5

    if ($elapsed -gt 400) {
        Write-Warning "Timeout after 400s"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        break
    }
}

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $dir ".grepai\*.lock") -Force -ErrorAction SilentlyContinue

Push-Location $dir
try {
    & $bin status --no-ui
} finally {
    Pop-Location
}
