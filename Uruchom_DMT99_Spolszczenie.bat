@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Nie znaleziono Python. Zainstaluj Python 3.11 lub nowszy.
  pause
  exit /b 1
)

python dmt99_polonizer.py
if errorlevel 1 pause
