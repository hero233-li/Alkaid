$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$DefaultBase = Resolve-Path (Join-Path $ProjectRoot "..")

$DevBackendPort = if ($env:DEV_BACKEND_PORT) { $env:DEV_BACKEND_PORT } else { "8000" }
$DevFrontendPort = if ($env:DEV_FRONTEND_PORT) { $env:DEV_FRONTEND_PORT } else { "5174" }
$RuntimeDir = if ($env:ALKAID_RUNTIME_DIR) { $env:ALKAID_RUNTIME_DIR } else { Join-Path $DefaultBase "Alkaid-runtime" }
$MysqlHost = if ($env:MYSQL_HOST) { $env:MYSQL_HOST } else { "127.0.0.1" }
$MysqlPort = if ($env:MYSQL_PORT) { $env:MYSQL_PORT } else { "3306" }
$MysqlDatabase = if ($env:MYSQL_DATABASE) { $env:MYSQL_DATABASE } else { "alkaid_dev" }
$MysqlUser = if ($env:MYSQL_USER) { $env:MYSQL_USER } else { "workflow" }
$MysqlPassword = if ($env:MYSQL_PASSWORD) { $env:MYSQL_PASSWORD } else { "workflow" }
$MysqlSslDisabled = if ($env:MYSQL_SSL_DISABLED) { $env:MYSQL_SSL_DISABLED } else { "true" }

$BackendDir = Join-Path $ProjectRoot "Alkaid-python"
$FrontendDir = Join-Path $ProjectRoot "Alkaid-react"
$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendLog = Join-Path $RuntimeDir "dev-backend.log"
$BackendErrLog = Join-Path $RuntimeDir "dev-backend.err.log"

if (!(Test-Path $BackendPython)) {
    throw "Backend Python does not exist: $BackendPython"
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
Remove-Item -ErrorAction SilentlyContinue $BackendLog, $BackendErrLog

$env:DJANGO_SETTINGS_MODULE = "config.settings.local"
$env:DB_ENGINE = "mysql"
$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = $MysqlPort
$env:MYSQL_DATABASE = $MysqlDatabase
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
$env:MYSQL_SSL_DISABLED = $MysqlSslDisabled
$env:CELERY_TASK_ALWAYS_EAGER = "true"

Write-Host "Migrating backend database..."
Push-Location $BackendDir
& $BackendPython manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    exit $LASTEXITCODE
}
Pop-Location

Write-Host "Starting backend on http://127.0.0.1:$DevBackendPort"
Write-Host "Backend logs:"
Write-Host "  $BackendLog"
Write-Host "  $BackendErrLog"

$backendArgs = @(
    "-m", "uvicorn",
    "config.asgi:application",
    "--host", "127.0.0.1",
    "--port", $DevBackendPort,
    "--reload"
)

$backend = Start-Process `
    -FilePath $BackendPython `
    -ArgumentList $backendArgs `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendErrLog `
    -PassThru

try {
    $env:ALIOTH_API_TARGET = "http://127.0.0.1:$DevBackendPort"
    Write-Host "Starting frontend on http://127.0.0.1:$DevFrontendPort"
    Push-Location $FrontendDir
    & npm run dev -- --port $DevFrontendPort
    $code = $LASTEXITCODE
    Pop-Location
    exit $code
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Write-Host "Stopping backend..."
        Stop-Process -Id $backend.Id -Force
    }
}
