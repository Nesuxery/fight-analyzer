@echo off
rem Tum kontrolleri calistir (testler, sema, tipler, lint, derleme).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check.ps1" %*
