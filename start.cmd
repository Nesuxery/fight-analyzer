@echo off
rem MMA Fight Analyzer - tek komutla baslat (API + analiz iscisi + arayuz).
rem Ilk calistirmada kurulum otomatik yapilir. Secenek: start.cmd --no-browser
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup
if not exist "frontend\node_modules\vite\bin\vite.js" goto setup
goto run
:setup
echo [start] Ilk kurulum yapiliyor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" || exit /b 1
:run
".venv\Scripts\python.exe" "scripts\launch.py" %*
