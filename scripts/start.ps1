param(
    [ValidateSet("cpu", "cuda")]
    [string]$Device = "cpu",
    [string]$Model = "",
    [int]$IOPaintPort = 28680,
    [int]$MCPPort = 28681,
    [int]$IOPaintStartupTimeoutSec = 900,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Runtime = Join-Path $Root "runtime"
$Models = Join-Path $Root "models"
New-Item -ItemType Directory -Force -Path $Runtime, $Models, (Join-Path $Runtime "output") | Out-Null

function Select-IOPaintModel {
    param(
        [string]$RequestedModel,
        [switch]$NonInteractiveMode
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedModel)) {
        return $RequestedModel.Trim()
    }
    if (-not [string]::IsNullOrWhiteSpace($env:IOPAINT_MODEL)) {
        return $env:IOPAINT_MODEL.Trim()
    }
    if ($NonInteractiveMode) {
        return "lama"
    }

    $choices = @(
        @{ Name = "lama"; Description = "Recommended general inpainting model" },
        @{ Name = "cv2"; Description = "Fast OpenCV mode for simple regions" }
    )

    Write-Host ""
    Write-Host "Select an IOPaint model:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $choices.Count; $i++) {
        Write-Host ("  {0}. {1} - {2}" -f ($i + 1), $choices[$i].Name, $choices[$i].Description)
    }
    Write-Host "  c. Custom model name, HuggingFace model, or local path"

    while ($true) {
        $selection = Read-Host "Select an option (default: 1)"
        if ([string]::IsNullOrWhiteSpace($selection)) {
            return "lama"
        }
        if ($selection -eq "c") {
            $customModel = Read-Host "Enter model name or path"
            if (-not [string]::IsNullOrWhiteSpace($customModel)) {
                return $customModel.Trim()
            }
        } else {
            $index = 0
            if ([int]::TryParse($selection, [ref]$index) -and $index -ge 1 -and $index -le $choices.Count) {
                return $choices[$index - 1].Name
            }
        }
        Write-Host "Invalid selection. Please try again." -ForegroundColor Yellow
    }
}

$Model = Select-IOPaintModel -RequestedModel $Model -NonInteractiveMode:$NonInteractive

if (-not (Test-Path $VenvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.10 -m venv $Venv
    } elseif (Get-Command python3.10 -ErrorAction SilentlyContinue) {
        & python3.10 -m venv $Venv
    } else {
        throw "Python 3.10 was not found. Install Python 3.10 and run this script again."
    }
}

& $VenvPython -m pip install --upgrade pip
if ($Device -eq "cpu") {
    & $VenvPython -m pip install torch==2.1.2+cpu torchvision==0.16.2+cpu --index-url https://download.pytorch.org/whl/cpu
} else {
    & $VenvPython -m pip install torch==2.1.2+cu121 torchvision==0.16.2+cu121 --index-url https://download.pytorch.org/whl/cu121
}
& $VenvPython -m pip install -e $Root
& $VenvPython -m pip install iopaint

$IopaintExe = Join-Path $Venv "Scripts\iopaint.exe"
$IopaintLog = Join-Path $Runtime "iopaint.log"
$IopaintErrorLog = Join-Path $Runtime "iopaint.error.log"
$McpLog = Join-Path $Runtime "mcp.log"
$McpErrorLog = Join-Path $Runtime "mcp.error.log"
$IopaintArgs = @("start", "--model=$Model", "--device=$Device", "--host=127.0.0.1", "--port=$IOPaintPort", "--model-dir=$Models")
$McpArgs = @("-m", "iopaint_mcp", "--transport", "streamable-http", "--host", "127.0.0.1", "--port", "$MCPPort")

if (Test-Path (Join-Path $Runtime "iopaint.pid")) { & (Join-Path $Root "scripts\stop.ps1") }
$env:IOPAINT_URL = "http://127.0.0.1:$IOPaintPort"
$iopaintProcess = Start-Process -FilePath $IopaintExe -ArgumentList $IopaintArgs -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $IopaintLog -RedirectStandardError $IopaintErrorLog -PassThru
$iopaintProcess.Id | Set-Content (Join-Path $Runtime "iopaint.pid")

Write-Host "Waiting for IOPaint to become healthy (model download may take a while)..."
$healthUrl = "http://127.0.0.1:$IOPaintPort/api/v1/server-config"
$deadline = (Get-Date).AddSeconds($IOPaintStartupTimeoutSec)
$iopaintReady = $false
while ((Get-Date) -lt $deadline) {
    if ($iopaintProcess.HasExited) {
        throw "IOPaint exited before becoming healthy. Check $IopaintErrorLog"
    }
    try {
        $null = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing
        $iopaintReady = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $iopaintReady) {
    Stop-Process -Id $iopaintProcess.Id -Force -ErrorAction SilentlyContinue
    throw "IOPaint did not become healthy within $IOPaintStartupTimeoutSec seconds. Check $IopaintErrorLog"
}

$mcpProcess = Start-Process -FilePath $VenvPython -ArgumentList $McpArgs -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $McpLog -RedirectStandardError $McpErrorLog -PassThru
$mcpProcess.Id | Set-Content (Join-Path $Runtime "mcp.pid")

Write-Host "IOPaint started: http://127.0.0.1:$IOPaintPort"
Write-Host "MCP started:     http://127.0.0.1:$MCPPort/mcp"
Write-Host "Model:           $Model"
Write-Host "Logs:            $Runtime"
