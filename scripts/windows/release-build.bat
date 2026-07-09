@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%\..") do set "DEFAULT_BASE=%%~fI"

if not defined ALKAID_RELEASES_DIR set "ALKAID_RELEASES_DIR=%DEFAULT_BASE%\Alkaid-releases"
if not defined ALKAID_RUNTIME_DIR set "ALKAID_RUNTIME_DIR=%DEFAULT_BASE%\Alkaid-runtime"
if not defined PYTHON_BOOTSTRAP set "PYTHON_BOOTSTRAP=py -3.10"
if not defined NPM_INSTALL_CMD set "NPM_INSTALL_CMD=npm ci"
if not defined UPGRADE_PIP set "UPGRADE_PIP=false"

if "%~1"=="" (
  for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "RELEASE_ID=%%I"
) else (
  set "RELEASE_ID=%~1"
)

set "RELEASE_DIR=%ALKAID_RELEASES_DIR%\%RELEASE_ID%"

if exist "%RELEASE_DIR%" (
  echo Release directory already exists:
  echo   "%RELEASE_DIR%"
  exit /b 1
)

if not exist "%ALKAID_RELEASES_DIR%" mkdir "%ALKAID_RELEASES_DIR%"
if not exist "%ALKAID_RUNTIME_DIR%" mkdir "%ALKAID_RUNTIME_DIR%"

echo Copying source to:
echo   %RELEASE_DIR%
robocopy "%PROJECT_ROOT%" "%RELEASE_DIR%" /MIR ^
  /XD .git .idea node_modules dist .venv __pycache__ .pytest_cache ^
  /XF db.sqlite3 *.pyc *.pyo tsconfig.tsbuildinfo .DS_Store
set "ROBOCOPY_EXIT=!ERRORLEVEL!"
if !ROBOCOPY_EXIT! GEQ 8 (
  echo Robocopy failed with exit code !ROBOCOPY_EXIT!.
  exit /b !ROBOCOPY_EXIT!
)

echo Installing backend dependencies...
pushd "%RELEASE_DIR%\Alkaid-python"
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

echo Building frontend...
pushd "%RELEASE_DIR%\Alkaid-react"
%NPM_INSTALL_CMD%
if errorlevel 1 exit /b 1
npm run build
if errorlevel 1 exit /b 1
popd

>"%RELEASE_DIR%\release-info.txt" echo %RELEASE_ID%
>"%ALKAID_RUNTIME_DIR%\last-built-release.txt" echo %RELEASE_DIR%

echo Release candidate created:
echo   %RELEASE_DIR%
echo Next:
echo   scripts\windows\release-verify.bat "%RELEASE_DIR%"
