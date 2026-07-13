$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")

function Get-EnvOrDefault($Name, $Default) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Test-Truthy($Value) {
    return @("1", "true", "yes", "on") -contains ([string]$Value).ToLowerInvariant()
}

function Protect-UrlSecret($Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }
    return $Value -replace "://([^:/@]+):([^@]+)@", '://$1:********@'
}

function Assert-PortFree($Port, $Name) {
    $connections = Get-NetTCPConnection -LocalPort ([int]$Port) -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        throw "$Name port $Port is already in use. Stop the old service or set DEV_${Name}_PORT."
    }
}

function Stop-ProcessTree($Process, $Name) {
    if ($Process -and -not $Process.HasExited) {
        Write-Host "Stopping $Name..."
        & taskkill.exe /PID $Process.Id /T /F | Out-Null
    }
}

$DevBackendPort = Get-EnvOrDefault "DEV_BACKEND_PORT" "8000"
$DevFrontendPort = Get-EnvOrDefault "DEV_FRONTEND_PORT" "5174"
$MysqlHost = Get-EnvOrDefault "MYSQL_HOST" "127.0.0.1"
$MysqlPort = Get-EnvOrDefault "MYSQL_PORT" "3306"
$MysqlDatabase = Get-EnvOrDefault "MYSQL_DATABASE" "alkaid_dev"
$MysqlUser = Get-EnvOrDefault "MYSQL_USER" "workflow"
$MysqlPassword = Get-EnvOrDefault "MYSQL_PASSWORD" "workflow"
$MysqlSslDisabled = Get-EnvOrDefault "MYSQL_SSL_DISABLED" "true"
$CeleryBrokerUrl = Get-EnvOrDefault "CELERY_BROKER_URL" "amqp://workflow:workflow@127.0.0.1:5672//"
$CeleryQueue = Get-EnvOrDefault "CELERY_QUEUE" "alkaid-local"
$CeleryAlwaysEager = Get-EnvOrDefault "CELERY_TASK_ALWAYS_EAGER" "false"
$StartWorkerDefault = if (Test-Truthy $CeleryAlwaysEager) { "false" } else { "true" }
$DevStartWorker = Get-EnvOrDefault "DEV_START_WORKER" $StartWorkerDefault

$BackendDir = Join-Path $ProjectRoot "Alkaid-python"
$FrontendDir = Join-Path $ProjectRoot "Alkaid-react"
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (!(Test-Path $BackendPython)) {
    throw "Backend Python does not exist: $BackendPython"
}

Assert-PortFree $DevBackendPort "BACKEND"
Assert-PortFree $DevFrontendPort "FRONTEND"

$env:DJANGO_SETTINGS_MODULE = Get-EnvOrDefault "DJANGO_SETTINGS_MODULE" "config.settings.local"
$env:DB_ENGINE = "mysql"
$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = $MysqlPort
$env:MYSQL_DATABASE = $MysqlDatabase
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
$env:MYSQL_SSL_DISABLED = $MysqlSslDisabled
$env:CELERY_BROKER_URL = $CeleryBrokerUrl
$env:CELERY_QUEUE = $CeleryQueue
$env:CELERY_TASK_ALWAYS_EAGER = $CeleryAlwaysEager

Write-Host "Runtime config:"
Write-Host "  Python: $BackendPython"
Write-Host "  Django settings: $env:DJANGO_SETTINGS_MODULE"
Write-Host "  Backend: http://127.0.0.1:$DevBackendPort"
Write-Host "  Frontend: http://127.0.0.1:$DevFrontendPort"
Write-Host "  Celery broker: $(Protect-UrlSecret $CeleryBrokerUrl)"
Write-Host "  Celery queue: $CeleryQueue"
Write-Host "  Celery eager: $CeleryAlwaysEager"
Write-Host "  Start worker: $DevStartWorker"

Write-Host "Migrating backend database..."
Push-Location $BackendDir
& $BackendPython manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    exit $LASTEXITCODE
}
Pop-Location

$worker = $null
if ((Test-Truthy $DevStartWorker) -and -not (Test-Truthy $CeleryAlwaysEager)) {
    Write-Host "Starting Celery worker for queue $CeleryQueue"
    $workerArgs = @(
        "-m", "celery",
        "-A", "config",
        "worker",
        "-l", "info",
        "-P", "solo",
        "-Q", $CeleryQueue
    )
    $worker = Start-Process `
        -FilePath $BackendPython `
        -ArgumentList $workerArgs `
        -WorkingDirectory $BackendDir `
        -NoNewWindow `
        -PassThru
}

Write-Host "Starting backend on http://127.0.0.1:$DevBackendPort"

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
    -NoNewWindow `
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
    if ((Get-Location).Path -eq $FrontendDir) {
        Pop-Location
    }
    Stop-ProcessTree $backend "backend"
    Stop-ProcessTree $worker "worker"
}
