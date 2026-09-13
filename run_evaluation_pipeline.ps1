<#
.SYNOPSIS
    Continuous Evaluation and Fine-Tuning Pipeline Runner for grepai Hybrid Engine
.DESCRIPTION
    Automates the 4-phase evaluation and optimization flywheel:
    1. Synthetic test case generation via AST inspection
    2. Hyperparameter grid search optimization (k, w_text, w_code)
    3. Regression benchmarking across 137M, 7B, and Hybrid engines
    4. Telemetry and hard-negative triplet status reporting
#>

param (
    [string]$TextDir = "$PSScriptRoot\repo-text",
    [string]$CodeDir = "$PSScriptRoot\repo-code",
    [string]$SourceDir = "$PSScriptRoot\grepai",
    [switch]$SkipSynthetic = $false,
    [switch]$SkipTune = $false
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "       grepai Continuous Evaluation & Fine-Tuning Flywheel Runner           " -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan

$casesFile = "$PSScriptRoot\benchmarks\cases.json"

# Phase 1: Synthetic Benchmark Expansion
if (-not $SkipSynthetic) {
    Write-Host "`n[PHASE 1] Expanding Synthetic Benchmark Ground Truth..." -ForegroundColor Yellow
    $synthOut = "$PSScriptRoot\benchmarks\synthetic_cases.json"
    & python "$PSScriptRoot\benchmarks\generate_synthetic_cases.py" `
        --code-dir $SourceDir `
        --max-files 10 `
        --output-cases $synthOut
    if ($LASTEXITCODE -ne 0) { throw "Phase 1 failed with exit code $LASTEXITCODE" }
    if (Test-Path $synthOut) {
        $casesFile = $synthOut
    }
}

# Phase 2: Hyperparameter Optimization
if (-not $SkipTune) {
    Write-Host "`n[PHASE 2] Optimizing Hybrid Retrieval Hyperparameters (k, w_text, w_code)..." -ForegroundColor Yellow
    & python "$PSScriptRoot\benchmarks\tune_hyperparameters.py" `
        --cases $casesFile `
        --text-dir $TextDir `
        --code-dir $CodeDir `
        --output "$PSScriptRoot\benchmarks\optimal_params.json"
    if ($LASTEXITCODE -ne 0) { throw "Phase 2 failed with exit code $LASTEXITCODE" }
}

# Phase 3: Regression Benchmark
Write-Host "`n[PHASE 3] Running 3-Way Comparative Regression Benchmark..." -ForegroundColor Yellow
& python "$PSScriptRoot\benchmarks\benchmark.py" `
    --cases $casesFile `
    --text-dir $TextDir `
    --code-dir $CodeDir `
    --hybrid
if ($LASTEXITCODE -ne 0) { throw "Phase 3 failed with exit code $LASTEXITCODE" }

# Phase 4: Telemetry & Training Triplet Status
Write-Host "`n[PHASE 4] Inspecting Telemetry & Training Triplets..." -ForegroundColor Yellow
& python "$PSScriptRoot\telemetry\collector.py" --status
if ($LASTEXITCODE -ne 0) { throw "Phase 4 failed with exit code $LASTEXITCODE" }

Write-Host "`n============================================================================" -ForegroundColor Green
Write-Host "                  Evaluation Flywheel Complete                              " -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
