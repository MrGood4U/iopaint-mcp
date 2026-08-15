$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Runtime = Join-Path $Root "runtime"
foreach ($name in @("iopaint", "mcp")) {
    $pidFile = Join-Path $Runtime "$name.pid"
    if (Test-Path $pidFile) {
        $processId = [int](Get-Content $pidFile | Select-Object -First 1)
        Stop-Process -Id $processId -Force
        Remove-Item -LiteralPath $pidFile -Force
    }
}
Write-Host "IOPaint MCP services stopped."
