@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined ALKAID_RUNTIME_DIR set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
if not defined VERIFY_PORT set "VERIFY_PORT=19000"
if not defined MYSQL_HOST set "MYSQL_HOST=127.0.0.1"
if not defined MYSQL_PORT set "MYSQL_PORT=3306"
if not defined VERIFY_MYSQL_DATABASE set "VERIFY_MYSQL_DATABASE=alkaid_verify"
if not defined MYSQL_USER set "MYSQL_USER=workflow"
if not defined MYSQL_PASSWORD set "MYSQL_PASSWORD=workflow"
if not defined MYSQL_SSL_DISABLED set "MYSQL_SSL_DISABLED=true"

if "%~1"=="" (
  set "LAST_BUILT_FILE=%ALKAID_RUNTIME_DIR%\last-built-release.txt"
  if not exist "%LAST_BUILT_FILE%" (
    echo Missing last-built-release.txt. Pass a release directory explicitly.
    exit /b 1
  )
  set /p RELEASE_DIR=<"%LAST_BUILT_FILE%"
) else (
  set "RELEASE_DIR=%~1"
)

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

if not exist "%ALKAID_RUNTIME_DIR%" mkdir "%ALKAID_RUNTIME_DIR%"

set "VERIFY_RUNNER=%ALKAID_RUNTIME_DIR%\verify-%RELEASE_NAME%.bat"
>"%VERIFY_RUNNER%" echo @echo off
>>"%VERIFY_RUNNER%" echo set "DJANGO_SETTINGS_MODULE=config.settings.local"
>>"%VERIFY_RUNNER%" echo set "DB_ENGINE=mysql"
>>"%VERIFY_RUNNER%" echo set "MYSQL_HOST=%MYSQL_HOST%"
>>"%VERIFY_RUNNER%" echo set "MYSQL_PORT=%MYSQL_PORT%"
>>"%VERIFY_RUNNER%" echo set "MYSQL_DATABASE=%VERIFY_MYSQL_DATABASE%"
>>"%VERIFY_RUNNER%" echo set "MYSQL_USER=%MYSQL_USER%"
>>"%VERIFY_RUNNER%" echo set "MYSQL_PASSWORD=%MYSQL_PASSWORD%"
>>"%VERIFY_RUNNER%" echo set "MYSQL_SSL_DISABLED=%MYSQL_SSL_DISABLED%"
>>"%VERIFY_RUNNER%" echo set "CELERY_TASK_ALWAYS_EAGER=true"
>>"%VERIFY_RUNNER%" echo set "APP_VERSION=verify-%RELEASE_NAME%"
>>"%VERIFY_RUNNER%" echo set "FRONTEND_DIST_DIR=%FRONTEND_DIST_DIR%"
>>"%VERIFY_RUNNER%" echo pushd "%RELEASE_DIR%\Alkaid-python"
>>"%VERIFY_RUNNER%" echo "%PYTHON_EXE%" manage.py migrate --noinput
>>"%VERIFY_RUNNER%" echo if errorlevel 1 exit /b 1
>>"%VERIFY_RUNNER%" echo "%PYTHON_EXE%" -m uvicorn config.asgi:application --host 127.0.0.1 --port %VERIFY_PORT%
>>"%VERIFY_RUNNER%" echo popd

echo Starting verification server:
echo   %RELEASE_DIR%
echo URL:
echo   http://127.0.0.1:%VERIFY_PORT%
echo MySQL:
echo   %MYSQL_USER%@%MYSQL_HOST%:%MYSQL_PORT%/%VERIFY_MYSQL_DATABASE%

start "Alkaid verify %RELEASE_NAME%" "%VERIFY_RUNNER%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:%VERIFY_PORT%/health/'; for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { }; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
  echo Verification server did not become healthy in time.
  echo Check the Alkaid verify window for errors.
  exit /b 1
)

echo Verification server is healthy.
echo Open:
echo   http://127.0.0.1:%VERIFY_PORT%
echo After manual verification:
echo   scripts\windows\release-promote.bat "%RELEASE_DIR%"
