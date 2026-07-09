@echo off
setlocal EnableExtensions

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

set "CURRENT_FILE=%ALKAID_RUNTIME_DIR%\current-release.txt"
set "PREVIOUS_FILE=%ALKAID_RUNTIME_DIR%\previous-release.txt"

if not exist "%PREVIOUS_FILE%" (
  echo Previous release file does not exist:
  echo   "%PREVIOUS_FILE%"
  exit /b 1
)

set /p PREVIOUS_RELEASE=<"%PREVIOUS_FILE%"
for %%I in ("%PREVIOUS_RELEASE%") do set "PREVIOUS_RELEASE=%%~fI"

if not exist "%PREVIOUS_RELEASE%" (
  echo Previous release directory does not exist:
  echo   "%PREVIOUS_RELEASE%"
  exit /b 1
)

if exist "%CURRENT_FILE%" (
  copy /Y "%CURRENT_FILE%" "%ALKAID_RUNTIME_DIR%\rollback-from-release.txt" >nul
)

>"%ALKAID_RUNTIME_DIR%\current-release.next" echo %PREVIOUS_RELEASE%
move /Y "%ALKAID_RUNTIME_DIR%\current-release.next" "%CURRENT_FILE%" >nul

echo Rolled back current release to:
echo   %PREVIOUS_RELEASE%
echo Restart prod-start.bat to run the rollback release.
