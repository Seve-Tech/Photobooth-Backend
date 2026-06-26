@echo off
setlocal

:: Photobooth one-click installer — requests Administrator, then runs setup_tasks.ps1

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  Photobooth Setup requires Administrator privileges.
    echo  Approve the UAC prompt to continue...
    echo.
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

if not exist "%~dp0setup_tasks.ps1" (
    echo.
    echo  ERROR: setup_tasks.ps1 not found in this folder.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_tasks.ps1"
exit /b %errorLevel%
