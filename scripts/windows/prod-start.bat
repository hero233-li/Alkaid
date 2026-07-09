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
if not defined MYSQL_HOST set "MYSQL_HOST=127.0.0.1"
if not defined MYSQL_PORT set "MYSQL_PORT=3306"
if not defined MYSQL_DATABASE set "MYSQL_DATABASE=alkaid_prod"
if not defined MYSQL_USER set "MYSQL_USER=workflow"
if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=workflow"
if not defined MYSQL_SSL_DISABLED set "MYSQL_SSL_DISABLED=true"

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

set "DJANGO_SETTINGS_MODULE=config.settings.local"
set "DB_ENGINE=mysql"
set "MYSQL_HOST=%MYSQL_HOST%"
set "MYSQL_PORT=%MYSQL_PORT%"
set "MYSQL_DATABASE=%MYSQL_DATABASE%"
set "MYSQL_USER=%MYSQL_USER%"
set "MYSQL_PASSWORD=%MYSQL_PASSWORD%"
set "MYSQL_SSL_DISABLED=%MYSQL_SSL_DISABLED%"
set "CELERY_TASK_ALWAYS_EAGER=true"
set "APP_VERSION=%RELEASE_NAME%"
set "FRONTEND_DIST_DIR=%FRONTEND_DIST_DIR%"

echo Starting Alkaid release:
echo   %RELEASE_DIR%
echo MySQL:
echo   %MYSQL_USER%@%MYSQL_HOST%:%MYSQL_PORT%/%MYSQL_DATABASE%
echo URL:
echo   http://127.0.0.1:%ALKAID_PORT%

pushd "%RELEASE_DIR%\Alkaid-python"
"%PYTHON_EXE%" manage.py migrate --noinput
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m uvicorn config.asgi:application --host 127.0.0.1 --port %ALKAID_PORT%
popd
