@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 patch_draw.py
) else (
  python patch_draw.py
)
if errorlevel 1 (
 echo [AVENA] Patch failed. Verify the source folder.
 pause
 exit /b 1
)
echo [AVENA] Close and restart Avena Electrical from RUN.bat
pause
