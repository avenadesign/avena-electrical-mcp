@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0connect_cloud.ps1"
set RC=%ERRORLEVEL%
if not "%RC%"=="0" echo [AVENA] Bridge failed with code %RC%
pause
exit /b %RC%
