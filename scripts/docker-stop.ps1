$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    & docker compose -f docker-compose.yml -f docker-compose.cuda.yml down
} finally {
    Pop-Location
}
