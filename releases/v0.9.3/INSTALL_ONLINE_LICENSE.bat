@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
 py -3 avena_online_license_hotfix.py
) else (
 python avena_online_license_hotfix.py
)
if errorlevel 1 (
 echo [AVENA] Installation failed; check that RUN.bat exists in this folder.
 pause
 exit /b 1
)
echo [AVENA] License is now checked ONLINE every time the main GUI opens.
pause
