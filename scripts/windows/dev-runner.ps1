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

function Wait-PortReleased($Port, $TimeoutSeconds = 10) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $connections = Get-NetTCPConnection -LocalPort ([int]$Port) -State Listen -ErrorAction SilentlyContinue
        if (!$connections) { return }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw "Port $Port was not released within $TimeoutSeconds seconds. Try an elevated terminal."
}

function Clear-ListeningPort($Port, $Name) {
    $connections = Get-NetTCPConnection -LocalPort ([int]$Port) -State Listen -ErrorAction SilentlyContinue
    if (!$connections) { return }
    $processIds = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        $processName = if ($process) { $process.ProcessName } else { "unknown" }
        Write-Host "Cleaning stale $Name listener: port=$Port pid=$processId process=$processName"
        try {
            & taskkill.exe /PID $processId /T /F | Out-Null
            if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
                throw "taskkill exited with code $LASTEXITCODE"
            }
        }
        catch {
            throw "Cannot stop pid $processId on $Name port $Port. Run this terminal as Administrator or stop it manually."
        }
    }
    Wait-PortReleased $Port
}

function Stop-ProcessTree($Process, $Name) {
    if ($Process -and -not $Process.HasExited) {
        Write-Host "Stopping $Name (pid=$($Process.Id))..."
        try {
            & taskkill.exe /PID $Process.Id /T /F | Out-Null
            if ($LASTEXITCODE -ne 0 -and -not $Process.HasExited) {
                throw "taskkill exited with code $LASTEXITCODE"
            }
        }
        catch {
            Write-Warning "Failed to stop $Name pid=$($Process.Id): $($_.Exception.Message)"
        }
    }
}

$DevBackendPort = Get-EnvOrDefault "DEV_BACKEND_PORT" "8000"
$DevFrontendPort = Get-EnvOrDefault "DEV_FRONTEND_PORT" "5174"
$DevBindAddress = Get-EnvOrDefault "DEV_BIND_ADDRESS" "0.0.0.0"
$DevLanIp = Get-EnvOrDefault "DEV_LAN_IP" ""
if ([string]::IsNullOrWhiteSpace($DevLanIp)) {
    try {
        $network = Get-NetIPConfiguration | Where-Object {
            $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up"
        } | Select-Object -First 1
        if ($network) {
            $DevLanIp = $network.IPv4Address.IPAddress
        }
    }
    catch {
        $DevLanIp = ""
    }
}
if ([string]::IsNullOrWhiteSpace($DevLanIp)) {
    $DevLanIp = "127.0.0.1"
}
$DjangoAllowedHosts = Get-EnvOrDefault "DJANGO_ALLOWED_HOSTS" "localhost,127.0.0.1,$DevLanIp"
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
$DevCleanStalePorts = Get-EnvOrDefault "DEV_CLEAN_STALE_PORTS" "true"

$BackendDir = Join-Path $ProjectRoot "Alkaid-python"
$FrontendDir = Join-Path $ProjectRoot "Alkaid-react"
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (!(Test-Path $BackendPython)) {
    throw "Backend Python does not exist: $BackendPython"
}

if (Test-Truthy $DevCleanStalePorts) {
    Clear-ListeningPort $DevBackendPort "BACKEND"
    Clear-ListeningPort $DevFrontendPort "FRONTEND"
}
else {
    if (Get-NetTCPConnection -LocalPort ([int]$DevBackendPort) -State Listen -ErrorAction SilentlyContinue) {
        throw "BACKEND port $DevBackendPort is already in use."
    }
    if (Get-NetTCPConnection -LocalPort ([int]$DevFrontendPort) -State Listen -ErrorAction SilentlyContinue) {
        throw "FRONTEND port $DevFrontendPort is already in use."
    }
}

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
$env:DJANGO_ALLOWED_HOSTS = $DjangoAllowedHosts

Write-Host "Runtime config:"
Write-Host "  Python: $BackendPython"
Write-Host "  Django settings: $env:DJANGO_SETTINGS_MODULE"
Write-Host "  Bind address: $DevBindAddress"
Write-Host "  Local backend: http://127.0.0.1:$DevBackendPort"
Write-Host "  Local frontend: http://127.0.0.1:$DevFrontendPort"
Write-Host "  LAN backend: http://$($DevLanIp):$DevBackendPort"
Write-Host "  LAN frontend: http://$($DevLanIp):$DevFrontendPort"
Write-Host "  Celery broker: $(Protect-UrlSecret $CeleryBrokerUrl)"
Write-Host "  Celery queue: $CeleryQueue"
Write-Host "  Celery eager: $CeleryAlwaysEager"
Write-Host "  Start worker: $DevStartWorker"
Write-Host "  Clean stale ports: $DevCleanStalePorts"

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
    Write-Host "Celery worker started: pid=$($worker.Id)"
}

Write-Host "Starting backend on http://$($DevLanIp):$DevBackendPort"

$backendArgs = @(
    "scripts\run_dev_server.py",
    "--host", $DevBindAddress,
    "--port", $DevBackendPort
)

$backend = Start-Process `
    -FilePath $BackendPython `
    -ArgumentList $backendArgs `
    -WorkingDirectory $BackendDir `
    -NoNewWindow `
    -PassThru
Write-Host "Backend started: pid=$($backend.Id)"

try {
    $env:ALIOTH_API_TARGET = "http://127.0.0.1:$DevBackendPort"
    Write-Host "Starting frontend on http://$($DevLanIp):$DevFrontendPort"
    Push-Location $FrontendDir
    & npm run dev -- --host $DevBindAddress --port $DevFrontendPort
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
    Wait-PortReleased $DevBackendPort
    Wait-PortReleased $DevFrontendPort
}
