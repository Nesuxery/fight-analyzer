@echo off
rem Kurulumu (yeniden) calistir. Ornek: setup.cmd -Torch cpu
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
