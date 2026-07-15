@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined ALKAID_RUNTIME_DIR set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
if not defined VERIFY_PORT set "VERIFY_PORT=19000"

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

if not exist "%RELEASE_DIR%\Alkaid-python\.venv\Scripts\python.exe" (
  echo Invalid release directory. Missing backend virtual environment:
  echo   "%RELEASE_DIR%"
  exit /b 1
)

if not exist "%RELEASE_DIR%\Alkaid-react\dist\web\index.html" (
  echo Invalid release directory. Missing frontend build:
  echo   "%RELEASE_DIR%\Alkaid-react\dist\web\index.html"
  exit /b 1
)

if /I not "%SKIP_HEALTH_CHECK%"=="true" (
  echo Checking verification server on http://127.0.0.1:%VERIFY_PORT%/health/ready/
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%VERIFY_PORT%/health/ready/' -TimeoutSec 3; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
  if errorlevel 1 (
    echo Verification server is not healthy.
    echo Keep release-verify.bat running, or set SKIP_HEALTH_CHECK=true if you already verified manually.
    exit /b 1
  )
)

if not exist "%ALKAID_RUNTIME_DIR%" mkdir "%ALKAID_RUNTIME_DIR%"
if exist "%ALKAID_RUNTIME_DIR%\current-release.txt" (
  copy /Y "%ALKAID_RUNTIME_DIR%\current-release.txt" "%ALKAID_RUNTIME_DIR%\previous-release.txt" >nul
)

>"%ALKAID_RUNTIME_DIR%\current-release.next" echo %RELEASE_DIR%
move /Y "%ALKAID_RUNTIME_DIR%\current-release.next" "%ALKAID_RUNTIME_DIR%\current-release.txt" >nul
copy /Y "%SCRIPT_DIR%prod-start.bat" "%ALKAID_RUNTIME_DIR%\prod-start.bat" >nul
copy /Y "%SCRIPT_DIR%release-rollback.bat" "%ALKAID_RUNTIME_DIR%\release-rollback.bat" >nul

echo Current release updated:
echo   %RELEASE_DIR%
echo Production startup script installed:
echo   %ALKAID_RUNTIME_DIR%\prod-start.bat
echo Restart that runtime prod-start.bat to run this release on the production port.
