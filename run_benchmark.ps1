<#
.SYNOPSIS
    Orchestration script for grepai embedding model benchmark (137M Text vs 7B Code).
.DESCRIPTION
    Verifies LM Studio connectivity, sets up dual test repositories, configures
    grepai for each embedding model, indexes both, and executes the evaluation suite.
    Automatically retrieves the API token from Windows Credential Store (PraetorSilica/LMStudioDev)
    if not explicitly passed.
#>

param (
    [string]$LMStudioUrl = "http://127.0.0.1:1234",
    [string]$TextModel = "text-embedding-nomic-embed-text-v1.5@f32",
    [string]$CodeModel = "text-embedding-nomic-embed-code",
    [int]$TextDimensions = 768,
    [int]$CodeDimensions = 4096,
    [string]$ApiToken = "",
    [switch]$SkipIndex = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinPath = Join-Path $ScriptDir "bin\grepai.exe"
$GrepaiSource = Join-Path $ScriptDir "grepai"
$TextRepo = Join-Path $ScriptDir "repo-text"
$CodeRepo = Join-Path $ScriptDir "repo-code"

function Get-WindowsStoredCredential([string]$target) {
    try {
        if (-not ([System.Management.Automation.PSTypeName]'CredHelper').Type) {
            Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class CredHelper {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public int Flags;
        public int Type;
        public string TargetName;
        public string Comment;
        public long LastWritten;
        public int CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int Persist;
        public int AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);

    [DllImport("Advapi32.dll", EntryPoint = "CredFree", SetLastError = true)]
    public static extern void CredFree(IntPtr credentialPtr);

    public static string ReadGenericCredential(string target) {
        IntPtr credPtr;
        if (CredRead(target, 1, 0, out credPtr)) {
            try {
                CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(credPtr, typeof(CREDENTIAL));
                if (cred.CredentialBlobSize > 0) {
                    return Marshal.PtrToStringUni(cred.CredentialBlob, cred.CredentialBlobSize / 2);
                }
            } finally {
                CredFree(credPtr);
            }
        }
        return null;
    }
}
"@
        }
        return [CredHelper]::ReadGenericCredential($target)
    } catch {
        return $null
    }
}

# Auto-resolve API Token if not provided
if (-not $ApiToken) {
    if ($env:LM_API_TOKEN) {
        $ApiToken = $env:LM_API_TOKEN
    } else {
        # Check known target in Windows Credential Store
        $stored = Get-WindowsStoredCredential "PraetorSilica/LMStudioDev"
        if ($stored) {
            $ApiToken = $stored
            Write-Host "[OK] Retrieved API token from Windows Credential Store (target: PraetorSilica/LMStudioDev)." -ForegroundColor Green
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       grepai Embedding Model Benchmark Runner            " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check grepai executable
if (-not (Test-Path $BinPath)) {
    Write-Error "grepai.exe not found at $BinPath. Run download step first."
    exit 1
}
Write-Host "[OK] grepai binary verified: $(& $BinPath version)" -ForegroundColor Green

# 2. Check LM Studio Server
Write-Host "`nChecking LM Studio server at $LMStudioUrl/v1/models..." -ForegroundColor Yellow
$headers = @{}
if ($ApiToken) {
    $headers["Authorization"] = "Bearer $ApiToken"
}

try {
    $modelsResp = Invoke-RestMethod -Uri "$LMStudioUrl/v1/models" -Method Get -Headers $headers -TimeoutSec 5
    Write-Host "[OK] LM Studio server is online and authenticated." -ForegroundColor Green
    if ($modelsResp.data) {
        Write-Host "Available/Loaded Models in LM Studio:" -ForegroundColor Gray
        foreach ($m in $modelsResp.data) {
            Write-Host "  - $($m.id)" -ForegroundColor Gray
        }
    }
} catch {
    $errBody = $_.ErrorDetails.Message
    if ($errBody -like "*API token is required*") {
        Write-Warning "LM Studio requires an API Token for requests."
        Write-Host "`nYou have two options to proceed:" -ForegroundColor Yellow
        Write-Host "  Option A (Recommended): In LM Studio -> Developer / Local Server tab, toggle OFF 'Require Authentication'." -ForegroundColor White
        Write-Host "  Option B: Pass your token: .\run_benchmark.ps1 -ApiToken 'your-token-here'`n" -ForegroundColor White
    } else {
        Write-Warning "Could not reach LM Studio at $LMStudioUrl."
        Write-Host "Please ensure LM Studio is running and the Local Server is started on port 1234." -ForegroundColor Yellow
    }
    exit 1
}

# 3. Setup Test Workspaces
function Prepare-TestRepo([string]$targetDir, [string]$modelName, [int]$dims, [string]$token) {
    if (-not (Test-Path $targetDir)) {
        Write-Host "`nCreating workspace: $targetDir..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        Copy-Item -Path "$GrepaiSource\*" -Destination $targetDir -Recurse -Force
    }

    $dotGrepai = Join-Path $targetDir ".grepai"
    New-Item -ItemType Directory -Force -Path $dotGrepai | Out-Null

    # If an API token is present, we configure using the 'openai' provider which passes the Bearer token
    if ($token) {
        $configContent = @"
version: 1
embedder:
  provider: openai
  model: $modelName
  endpoint: $LMStudioUrl/v1
  api_key: $token
  dimensions: $dims
  parallelism: 2
  request_timeout_seconds: 120
store:
  backend: gob
chunking:
  size: 300
  overlap: 50
search:
  dedup:
    enabled: false
  hybrid:
    enabled: false
"@
    } else {
        $configContent = @"
version: 1
embedder:
  provider: lmstudio
  model: $modelName
  endpoint: $LMStudioUrl
  dimensions: $dims
  parallelism: 2
  request_timeout_seconds: 120
store:
  backend: gob
chunking:
  size: 300
  overlap: 50
search:
  dedup:
    enabled: false
  hybrid:
    enabled: false
"@
    }

    Set-Content -Path (Join-Path $dotGrepai "config.yaml") -Value $configContent -Encoding utf8
    Write-Host "[OK] Configured $targetDir for model '$modelName' (dim: $dims)" -ForegroundColor Green
}

Prepare-TestRepo -targetDir $TextRepo -modelName $TextModel -dims $TextDimensions -token $ApiToken
Prepare-TestRepo -targetDir $CodeRepo -modelName $CodeModel -dims $CodeDimensions -token $ApiToken

# 4. Index Workspaces
if (-not $SkipIndex) {
    Write-Host "`n----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Step 1/2: Indexing Text Model ($TextModel)" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
    
    if (Get-Command lms -ErrorAction SilentlyContinue) {
        Write-Host "Loading $TextModel via lms CLI..." -ForegroundColor Gray
        & lms load $TextModel -y
    } else {
        Write-Host "NOTE: Load '$TextModel' in LM Studio." -ForegroundColor Yellow
    }

    $idxStart = Get-Date
    Push-Location $TextRepo
    try {
        & $BinPath watch --once
    } finally {
        Pop-Location
    }
    $idxDuration = (Get-Date) - $idxStart
    Write-Host "[OK] Text index complete in $($idxDuration.TotalSeconds.ToString("F1")) seconds." -ForegroundColor Green

    Write-Host "`n----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Step 2/2: Indexing Code Model ($CodeModel)" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
    
    if (Get-Command lms -ErrorAction SilentlyContinue) {
        Write-Host "Loading $CodeModel via lms CLI..." -ForegroundColor Gray
        & lms load $CodeModel -y
    } else {
        Read-Host "Press Enter once '$CodeModel' is loaded in LM Studio"
    }

    $idxStart = Get-Date
    Push-Location $CodeRepo
    try {
        & $BinPath watch --once
    } finally {
        Pop-Location
    }
    $idxDuration = (Get-Date) - $idxStart
    Write-Host "[OK] Code index complete in $($idxDuration.TotalSeconds.ToString("F1")) seconds." -ForegroundColor Green
}

# 5. Run Benchmark
Write-Host "`n----------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Running Benchmark Evaluation" -ForegroundColor Cyan
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan

python "$ScriptDir\benchmarks\benchmark.py" `
    --text-dir $TextRepo `
    --code-dir $CodeRepo `
    --grepai-bin $BinPath `
    --cases "$ScriptDir\benchmarks\cases.json" `
    --output-json "$ScriptDir\benchmark_results.json"
