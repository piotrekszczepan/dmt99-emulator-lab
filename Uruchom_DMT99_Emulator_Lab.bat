@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Najpierw uruchom setup.bat
  pause
  exit /b 1
)
start "DMT-99 Emulator Lab" ".venv\Scripts\pythonw.exe" "%~dp0dmt99_emulator_lab.py"
