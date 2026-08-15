param(
    [ValidateSet("cpu", "cuda")]
    [string]$Device = "cpu",
    [string]$Model = "",
    [switch]$Foreground,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvironmentNames = @("IOPAINT_MODEL", "MCP_HOST_OUTPUT_DIR", "MCP_HOST_TEMP_DIR", "MCP_PATH_MAPPINGS")
$EnvironmentBackup = @{}
foreach ($name in $EnvironmentNames) {
    $EnvironmentBackup[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

function Restore-Environment {
    foreach ($name in $EnvironmentNames) {
        $value = $EnvironmentBackup[$name]
        if ($null -eq $value) {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath "Env:$name" -Value $value
        }
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Install Docker Desktop and try again."
}

if ([string]::IsNullOrWhiteSpace($Model)) {
    $Model = $env:IOPAINT_MODEL
}
if ([string]::IsNullOrWhiteSpace($Model)) {
    Write-Host "Select an IOPaint model for Docker:" -ForegroundColor Cyan
    Write-Host "  1. lama - Recommended general inpainting model"
    Write-Host "  2. cv2  - Fast OpenCV mode"
    Write-Host "  c. Custom model name, HuggingFace model, or local path"
    $selection = Read-Host "Select an option (default: 1)"
    switch ($selection) {
        "" { $Model = "lama" }
        "1" { $Model = "lama" }
        "2" { $Model = "cv2" }
        "c" { $Model = Read-Host "Enter model name or path" }
        "C" { $Model = Read-Host "Enter model name or path" }
        default { throw "Invalid model selection: $selection" }
    }
}
$locationPushed = $false
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "models"), (Join-Path $Root "data\input"), (Join-Path $Root "data\output"), (Join-Path $Root "outputs") | Out-Null
    $env:IOPAINT_MODEL = $Model.Trim()

    if ([string]::IsNullOrWhiteSpace($env:MCP_HOST_OUTPUT_DIR)) {
        $env:MCP_HOST_OUTPUT_DIR = Join-Path $Root "outputs"
    }
    $hostOutputDirectory = $env:MCP_HOST_OUTPUT_DIR

    if ([string]::IsNullOrWhiteSpace($env:MCP_HOST_TEMP_DIR)) {
        $env:MCP_HOST_TEMP_DIR = if (-not [string]::IsNullOrWhiteSpace($env:TEMP)) { $env:TEMP } else { $env:TMP }
    }
    if ([string]::IsNullOrWhiteSpace($env:MCP_PATH_MAPPINGS) -and -not [string]::IsNullOrWhiteSpace($env:MCP_HOST_TEMP_DIR)) {
        $env:MCP_PATH_MAPPINGS = "$($env:MCP_HOST_TEMP_DIR)=>/host-temp;$(Join-Path $Root 'data')=>/data"
    } elseif ($env:MCP_PATH_MAPPINGS -notmatch "=>/data(?:;|$)") {
        $env:MCP_PATH_MAPPINGS = "$($env:MCP_PATH_MAPPINGS);$(Join-Path $Root 'data')=>/data"
    }

    $composeArgs = @("-f", (Join-Path $Root "docker-compose.yml"))
    if ($Device -eq "cuda") {
        $composeArgs += @("-f", (Join-Path $Root "docker-compose.cuda.yml"))
    }
    $composeArgs += "up"
    if (-not $Foreground) { $composeArgs += "-d" }
    if (-not $NoBuild) { $composeArgs += "--build" }

    Push-Location $Root
    $locationPushed = $true
    try {
        & docker compose @composeArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Compose failed with exit code $LASTEXITCODE."
        }
    } finally {
        if ($locationPushed) {
            Pop-Location
            $locationPushed = $false
        }
    }
} finally {
    if ($locationPushed) {
        Pop-Location
    }
    Restore-Environment
}

Write-Host ""
Write-Host "IOPaint model:  $Model"
Write-Host "IOPaint API:    http://127.0.0.1:28680"
Write-Host "MCP endpoint:   http://127.0.0.1:28681/mcp"
Write-Host "Input directory: $Root\data\input"
Write-Host "Output directory: $hostOutputDirectory"
