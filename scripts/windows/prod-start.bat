@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined ALKAID_RUNTIME_DIR (
  if exist "%SCRIPT_DIR%current-release.txt" (
    for %%I in ("%SCRIPT_DIR%.") do set "ALKAID_RUNTIME_DIR=%%~fI"
  ) else (
    set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
  )
)
if not defined ALKAID_PORT set "ALKAID_PORT=9000"
if not defined WEB_BIND_ADDRESS set "WEB_BIND_ADDRESS=0.0.0.0"
if not defined ALKAID_LAN_IP (
  for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$c = Get-NetIPConfiguration ^| Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } ^| Select-Object -First 1; if ($c) { $c.IPv4Address.IPAddress }"`) do set "ALKAID_LAN_IP=%%I"
)
if not defined ALKAID_LAN_IP set "ALKAID_LAN_IP=127.0.0.1"
if not defined DJANGO_ALLOWED_HOSTS set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,%ALKAID_LAN_IP%"
if not defined CELERY_QUEUE set "CELERY_QUEUE=alkaid-prod"
if not defined MYSQL_HOST set "MYSQL_HOST=127.0.0.1"
if not defined MYSQL_PORT set "MYSQL_PORT=3306"
if not defined MYSQL_DATABASE set "MYSQL_DATABASE=alkaid_prod"
if not defined MYSQL_USER set "MYSQL_USER=workflow"
if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=workflow"
if not defined MYSQL_SSL_DISABLED set "MYSQL_SSL_DISABLED=true"

if not defined DJANGO_SECRET_KEY (
  echo DJANGO_SECRET_KEY is required for production.
  exit /b 1
)
if not defined CELERY_BROKER_URL (
  echo CELERY_BROKER_URL is required for production.
  exit /b 1
)
if not defined MOCK_PRODUCT_BASE_URL (
  echo MOCK_PRODUCT_BASE_URL is required for production.
  exit /b 1
)
if not defined APPLICATION_LINK_BASE_URL (
  echo APPLICATION_LINK_BASE_URL is required for production.
  exit /b 1
)
if not defined APPLICATION_LINK_API_TOKEN (
  echo APPLICATION_LINK_API_TOKEN is required for production.
  exit /b 1
)
if not defined BUSINESS_ACCESS_BASE_URL (
  echo BUSINESS_ACCESS_BASE_URL is required for production.
  exit /b 1
)
if not defined BUSINESS_ACCESS_API_TOKEN (
  echo BUSINESS_ACCESS_API_TOKEN is required for production.
  exit /b 1
)
if not defined VERIFICATION_APPROVAL_BASE_URL (
  echo VERIFICATION_APPROVAL_BASE_URL is required for production.
  exit /b 1
)
if not defined VERIFICATION_APPROVAL_API_TOKEN (
  echo VERIFICATION_APPROVAL_API_TOKEN is required for production.
  exit /b 1
)
if not defined MOCK_FIXED_SYSTEM_TOKEN (
  echo MOCK_FIXED_SYSTEM_TOKEN is required for production.
  exit /b 1
)

set "CURRENT_FILE=%ALKAID_RUNTIME_DIR%\current-release.txt"
if not exist "%CURRENT_FILE%" (
  echo Current release file does not exist:
  echo   "%CURRENT_FILE%"
  echo Run release-build.bat, release-verify.bat, and release-promote.bat first.
  exit /b 1
)

set /p RELEASE_DIR=<"%CURRENT_FILE%"
for %%I in ("%RELEASE_DIR%") do set "RELEASE_DIR=%%~fI"
for %%I in ("%RELEASE_DIR%") do set "RELEASE_NAME=%%~nxI"

set "PYTHON_EXE=%RELEASE_DIR%\Alkaid-python\.venv\Scripts\python.exe"
set "FRONTEND_DIST_DIR=%RELEASE_DIR%\Alkaid-react\dist\web"

if not exist "%PYTHON_EXE%" (
  echo Release Python does not exist:
  echo   "%PYTHON_EXE%"
  exit /b 1
)

if not exist "%FRONTEND_DIST_DIR%\index.html" (
  echo Frontend build does not exist:
  echo   "%FRONTEND_DIST_DIR%\index.html"
  exit /b 1
)

set "DJANGO_SETTINGS_MODULE=config.settings.server"
set "EXTERNAL_SYSTEM_MODE=real"
set "DB_ENGINE=mysql"
set "MYSQL_HOST=%MYSQL_HOST%"
set "MYSQL_PORT=%MYSQL_PORT%"
set "MYSQL_DATABASE=%MYSQL_DATABASE%"
set "MYSQL_USER=%MYSQL_USER%"
set "MYSQL_PASSWORD=%MYSQL_PASSWORD%"
set "MYSQL_SSL_DISABLED=%MYSQL_SSL_DISABLED%"
set "CELERY_TASK_ALWAYS_EAGER=false"
set "CELERY_QUEUE=%CELERY_QUEUE%"
set "APP_VERSION=%RELEASE_NAME%"
set "FRONTEND_DIST_DIR=%FRONTEND_DIST_DIR%"

echo Starting Alkaid release:
echo   %RELEASE_DIR%
echo MySQL:
echo   %MYSQL_USER%@%MYSQL_HOST%:%MYSQL_PORT%/%MYSQL_DATABASE%
echo URL:
echo   Local: http://127.0.0.1:%ALKAID_PORT%
echo   LAN:   http://%ALKAID_LAN_IP%:%ALKAID_PORT%

pushd "%RELEASE_DIR%\Alkaid-python"
"%PYTHON_EXE%" manage.py migrate --noinput
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" scripts\run_server.py --host %WEB_BIND_ADDRESS% --port %ALKAID_PORT% --queue %CELERY_QUEUE%
popd
