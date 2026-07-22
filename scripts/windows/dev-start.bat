@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined DEV_BACKEND_PORT set "DEV_BACKEND_PORT=8000"
if not defined DEV_FRONTEND_PORT set "DEV_FRONTEND_PORT=5174"
if not defined DEV_BIND_ADDRESS set "DEV_BIND_ADDRESS=0.0.0.0"
if not defined DEV_LAN_IP (
  for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$c = Get-NetIPConfiguration ^| Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } ^| Select-Object -First 1; if ($c) { $c.IPv4Address.IPAddress }"`) do set "DEV_LAN_IP=%%I"
)
if not defined DEV_LAN_IP set "DEV_LAN_IP=127.0.0.1"
if not defined DJANGO_ALLOWED_HOSTS (
  if defined DEV_LAN_IP (
    set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,%DEV_LAN_IP%"
  ) else (
    set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1"
  )
)
if not defined ALKAID_RUNTIME_DIR set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
if not defined PYTHON_BOOTSTRAP set "PYTHON_BOOTSTRAP=py -3.10"
if not defined NPM_INSTALL_CMD set "NPM_INSTALL_CMD=npm ci --include=optional"
if not defined UPGRADE_PIP set "UPGRADE_PIP=false"
if not defined MYSQL_HOST set "MYSQL_HOST=127.0.0.1"
if not defined MYSQL_PORT set "MYSQL_PORT=3306"
if not defined MYSQL_DATABASE set "MYSQL_DATABASE=alkaid_dev"
if not defined MYSQL_USER set "MYSQL_USER=workflow"
if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=workflow"
if not defined MYSQL_SSL_DISABLED set "MYSQL_SSL_DISABLED=true"
if not defined CELERY_BROKER_URL set "CELERY_BROKER_URL=amqp://workflow:workflow@127.0.0.1:5672//"
if not defined CELERY_QUEUE set "CELERY_QUEUE=alkaid-local"
if not defined CELERY_TASK_ALWAYS_EAGER set "CELERY_TASK_ALWAYS_EAGER=false"
if not defined DEV_START_WORKER (
  if /I "%CELERY_TASK_ALWAYS_EAGER%"=="true" (
    set "DEV_START_WORKER=false"
  ) else (
    set "DEV_START_WORKER=true"
  )
)

set "BACKEND_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "NEED_BACKEND_DEPS=false"
if not exist "%BACKEND_PYTHON%" set "NEED_BACKEND_DEPS=true"
if exist "%BACKEND_PYTHON%" (
  "%BACKEND_PYTHON%" -c "import django, uvicorn, pymysql, celery" >nul 2>nul
  if errorlevel 1 set "NEED_BACKEND_DEPS=true"
)

if /I "%NEED_BACKEND_DEPS%"=="true" (
  echo Preparing backend virtual environment...
  pushd "%PROJECT_ROOT%"
  if not exist "%BACKEND_PYTHON%" (
    %PYTHON_BOOTSTRAP% -m venv .venv
    if errorlevel 1 exit /b 1
  )
  "%BACKEND_PYTHON%" -m ensurepip --upgrade
  if errorlevel 1 exit /b 1
  if /I "%UPGRADE_PIP%"=="true" (
    "%BACKEND_PYTHON%" -m pip install %PIP_INSTALL_ARGS% --upgrade pip
    if errorlevel 1 exit /b 1
  )
  "%BACKEND_PYTHON%" -m pip install %PIP_INSTALL_ARGS% -r "%PROJECT_ROOT%\Alkaid-python\requirements-dev.lock"
  if errorlevel 1 exit /b 1
  "%BACKEND_PYTHON%" -m pip install -e "%PROJECT_ROOT%\Alkaid-python" --no-deps
  if errorlevel 1 exit /b 1
  popd
)

set "NEED_FRONTEND_DEPS=false"
if not exist "%PROJECT_ROOT%\Alkaid-react\node_modules" set "NEED_FRONTEND_DEPS=true"
if not exist "%PROJECT_ROOT%\Alkaid-react\node_modules\.bin\vite.cmd" set "NEED_FRONTEND_DEPS=true"

if /I "%NEED_FRONTEND_DEPS%"=="true" (
  echo Preparing frontend dependencies...
  pushd "%PROJECT_ROOT%\Alkaid-react"
  %NPM_INSTALL_CMD%
  if errorlevel 1 exit /b 1
  popd
)

if not exist "%ALKAID_RUNTIME_DIR%" mkdir "%ALKAID_RUNTIME_DIR%"

if /I "%DEV_SPLIT_WINDOWS%"=="true" (
  set "BACKEND_RUNNER=%ALKAID_RUNTIME_DIR%\dev-backend.bat"
  set "WORKER_RUNNER=%ALKAID_RUNTIME_DIR%\dev-worker.bat"
  set "FRONTEND_RUNNER=%ALKAID_RUNTIME_DIR%\dev-frontend.bat"

  >"%BACKEND_RUNNER%" echo @echo off
  >>"%BACKEND_RUNNER%" echo set "DJANGO_SETTINGS_MODULE=config.settings.local"
  >>"%BACKEND_RUNNER%" echo set "DB_ENGINE=mysql"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_HOST=%MYSQL_HOST%"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_PORT=%MYSQL_PORT%"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_DATABASE=%MYSQL_DATABASE%"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_USER=%MYSQL_USER%"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_PASSWORD=%MYSQL_PASSWORD%"
  >>"%BACKEND_RUNNER%" echo set "MYSQL_SSL_DISABLED=%MYSQL_SSL_DISABLED%"
  >>"%BACKEND_RUNNER%" echo set "CELERY_BROKER_URL=%CELERY_BROKER_URL%"
  >>"%BACKEND_RUNNER%" echo set "CELERY_QUEUE=%CELERY_QUEUE%"
  >>"%BACKEND_RUNNER%" echo set "CELERY_TASK_ALWAYS_EAGER=%CELERY_TASK_ALWAYS_EAGER%"
  >>"%BACKEND_RUNNER%" echo set "DJANGO_ALLOWED_HOSTS=%DJANGO_ALLOWED_HOSTS%"
  >>"%BACKEND_RUNNER%" echo pushd "%PROJECT_ROOT%\Alkaid-python"
  >>"%BACKEND_RUNNER%" echo "%BACKEND_PYTHON%" manage.py migrate
  >>"%BACKEND_RUNNER%" echo if errorlevel 1 exit /b 1
  >>"%BACKEND_RUNNER%" echo "%BACKEND_PYTHON%" -m uvicorn config.asgi:application --host %DEV_BIND_ADDRESS% --port %DEV_BACKEND_PORT% --reload
  >>"%BACKEND_RUNNER%" echo popd

  >"%WORKER_RUNNER%" echo @echo off
  >>"%WORKER_RUNNER%" echo set "DJANGO_SETTINGS_MODULE=config.settings.local"
  >>"%WORKER_RUNNER%" echo set "DB_ENGINE=mysql"
  >>"%WORKER_RUNNER%" echo set "MYSQL_HOST=%MYSQL_HOST%"
  >>"%WORKER_RUNNER%" echo set "MYSQL_PORT=%MYSQL_PORT%"
  >>"%WORKER_RUNNER%" echo set "MYSQL_DATABASE=%MYSQL_DATABASE%"
  >>"%WORKER_RUNNER%" echo set "MYSQL_USER=%MYSQL_USER%"
  >>"%WORKER_RUNNER%" echo set "MYSQL_PASSWORD=%MYSQL_PASSWORD%"
  >>"%WORKER_RUNNER%" echo set "MYSQL_SSL_DISABLED=%MYSQL_SSL_DISABLED%"
  >>"%WORKER_RUNNER%" echo set "CELERY_BROKER_URL=%CELERY_BROKER_URL%"
  >>"%WORKER_RUNNER%" echo set "CELERY_QUEUE=%CELERY_QUEUE%"
  >>"%WORKER_RUNNER%" echo set "CELERY_TASK_ALWAYS_EAGER=%CELERY_TASK_ALWAYS_EAGER%"
  >>"%WORKER_RUNNER%" echo pushd "%PROJECT_ROOT%\Alkaid-python"
  >>"%WORKER_RUNNER%" echo "%BACKEND_PYTHON%" -m celery -A config worker -l info -P solo -Q %CELERY_QUEUE%
  >>"%WORKER_RUNNER%" echo popd

  >"%FRONTEND_RUNNER%" echo @echo off
  >>"%FRONTEND_RUNNER%" echo set "ALIOTH_API_TARGET=http://127.0.0.1:%DEV_BACKEND_PORT%"
  >>"%FRONTEND_RUNNER%" echo pushd "%PROJECT_ROOT%\Alkaid-react"
  >>"%FRONTEND_RUNNER%" echo npm run dev -- --host %DEV_BIND_ADDRESS% --port %DEV_FRONTEND_PORT%
  >>"%FRONTEND_RUNNER%" echo popd

  echo Starting dev backend on http://%DEV_LAN_IP%:%DEV_BACKEND_PORT%
  start "Alkaid dev backend" "%BACKEND_RUNNER%"

  if /I "%DEV_START_WORKER%"=="true" (
    if /I not "%CELERY_TASK_ALWAYS_EAGER%"=="true" (
      echo Starting Celery worker for queue %CELERY_QUEUE%
      start "Alkaid dev worker" "%WORKER_RUNNER%"
    )
  )

  echo Starting dev frontend on http://%DEV_LAN_IP%:%DEV_FRONTEND_PORT%
  start "Alkaid dev frontend" "%FRONTEND_RUNNER%"

  echo Dev services are starting in separate windows.
  exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%dev-runner.ps1"
