@echo off
setlocal EnableExtensions

pushd "%~dp0"
npm run dev
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
