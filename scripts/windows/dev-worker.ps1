$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$BackendDir = Join-Path $ProjectRoot "Alkaid-python"
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Get-EnvOrDefault($Name, $Default) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Protect-UrlSecret($Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }
    return $Value -replace "://([^:/@]+):([^@]+)@", '://$1:********@'
}

if (!(Test-Path $BackendPython)) {
    throw "Backend Python does not exist: $BackendPython"
}

$env:DJANGO_SETTINGS_MODULE = Get-EnvOrDefault "DJANGO_SETTINGS_MODULE" "config.settings.local"
$env:DB_ENGINE = "mysql"
$env:MYSQL_HOST = Get-EnvOrDefault "MYSQL_HOST" "127.0.0.1"
$env:MYSQL_PORT = Get-EnvOrDefault "MYSQL_PORT" "3306"
$env:MYSQL_DATABASE = Get-EnvOrDefault "MYSQL_DATABASE" "alkaid_dev"
$env:MYSQL_USER = Get-EnvOrDefault "MYSQL_USER" "workflow"
$env:MYSQL_PASSWORD = Get-EnvOrDefault "MYSQL_PASSWORD" "workflow"
$env:MYSQL_SSL_DISABLED = Get-EnvOrDefault "MYSQL_SSL_DISABLED" "true"
$env:CELERY_BROKER_URL = Get-EnvOrDefault "CELERY_BROKER_URL" "amqp://workflow:workflow@127.0.0.1:5672//"
$env:CELERY_QUEUE = Get-EnvOrDefault "CELERY_QUEUE" "alkaid-local"
$env:CELERY_TASK_ALWAYS_EAGER = Get-EnvOrDefault "CELERY_TASK_ALWAYS_EAGER" "false"

Write-Host "Starting standalone Celery worker"
Write-Host "  Python: $BackendPython"
Write-Host "  Django settings: $env:DJANGO_SETTINGS_MODULE"
Write-Host "  Broker: $(Protect-UrlSecret $env:CELERY_BROKER_URL)"
Write-Host "  Queue: $env:CELERY_QUEUE"

Push-Location $BackendDir
& $BackendPython -m celery -A config worker -l info -P solo -Q $env:CELERY_QUEUE
$code = $LASTEXITCODE
Pop-Location
exit $code
