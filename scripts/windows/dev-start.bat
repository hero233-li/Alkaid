@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined DEV_BACKEND_PORT set "DEV_BACKEND_PORT=8000"
if not defined DEV_FRONTEND_PORT set "DEV_FRONTEND_PORT=5174"
if not defined ALKAID_RUNTIME_DIR set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
if not defined PYTHON_BOOTSTRAP set "PYTHON_BOOTSTRAP=py -3.10"
if not defined NPM_INSTALL_CMD set "NPM_INSTALL_CMD=npm ci"
if not defined UPGRADE_PIP set "UPGRADE_PIP=false"
if not defined MYSQL_HOST set "MYSQL_HOST=127.0.0.1"
if not defined MYSQL_PORT set "MYSQL_PORT=3306"
if not defined MYSQL_DATABASE set "MYSQL_DATABASE=alkaid_dev"
if not defined MYSQL_USER set "MYSQL_USER=workflow"
if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=workflow"
if not defined MYSQL_SSL_DISABLED set "MYSQL_SSL_DISABLED=true"

set "BACKEND_PYTHON=%PROJECT_ROOT%\Alkaid-python\.venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
  echo Preparing backend virtual environment...
  pushd "%PROJECT_ROOT%\Alkaid-python"
  %PYTHON_BOOTSTRAP% -m venv .venv
  if errorlevel 1 exit /b 1
  .venv\Scripts\python.exe -m ensurepip --upgrade
  if errorlevel 1 exit /b 1
  if /I "%UPGRADE_PIP%"=="true" (
    .venv\Scripts\python.exe -m pip install %PIP_INSTALL_ARGS% --upgrade pip
    if errorlevel 1 exit /b 1
  )
  .venv\Scripts\python.exe -m pip install %PIP_INSTALL_ARGS% -r requirements-dev.lock
  if errorlevel 1 exit /b 1
  .venv\Scripts\python.exe -m pip install -e . --no-deps
  if errorlevel 1 exit /b 1
  popd
)

if not exist "%PROJECT_ROOT%\Alkaid-react\node_modules" (
  echo Preparing frontend dependencies...
  pushd "%PROJECT_ROOT%\Alkaid-react"
  %NPM_INSTALL_CMD%
  if errorlevel 1 exit /b 1
  popd
)

if not exist "%ALKAID_RUNTIME_DIR%" mkdir "%ALKAID_RUNTIME_DIR%"

if /I "%DEV_SPLIT_WINDOWS%"=="true" (
  set "BACKEND_RUNNER=%ALKAID_RUNTIME_DIR%\dev-backend.bat"
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
  >>"%BACKEND_RUNNER%" echo set "CELERY_TASK_ALWAYS_EAGER=true"
  >>"%BACKEND_RUNNER%" echo pushd "%PROJECT_ROOT%\Alkaid-python"
  >>"%BACKEND_RUNNER%" echo "%BACKEND_PYTHON%" manage.py migrate
  >>"%BACKEND_RUNNER%" echo if errorlevel 1 exit /b 1
  >>"%BACKEND_RUNNER%" echo "%BACKEND_PYTHON%" -m uvicorn config.asgi:application --host 127.0.0.1 --port %DEV_BACKEND_PORT% --reload
  >>"%BACKEND_RUNNER%" echo popd

  >"%FRONTEND_RUNNER%" echo @echo off
  >>"%FRONTEND_RUNNER%" echo set "ALIOTH_API_TARGET=http://127.0.0.1:%DEV_BACKEND_PORT%"
  >>"%FRONTEND_RUNNER%" echo pushd "%PROJECT_ROOT%\Alkaid-react"
  >>"%FRONTEND_RUNNER%" echo npm run dev -- --port %DEV_FRONTEND_PORT%
  >>"%FRONTEND_RUNNER%" echo popd

  echo Starting dev backend on http://127.0.0.1:%DEV_BACKEND_PORT%
  start "Alkaid dev backend" "%BACKEND_RUNNER%"

  echo Starting dev frontend on http://127.0.0.1:%DEV_FRONTEND_PORT%
  start "Alkaid dev frontend" "%FRONTEND_RUNNER%"

  echo Dev services are starting in separate windows.
  exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%dev-runner.ps1"
