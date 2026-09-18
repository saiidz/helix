@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo HELIX virtual environment is missing. Run SETUP_WINDOWS.cmd first.
  pause
  exit /b 1
)
if not exist "config\local.json" (
  echo config\local.json is missing. Configure the local Engineer model first.
  pause
  exit /b 1
)
echo HELIX Engineer Agent - operator-reviewed local coding.
echo Keep the local llama-server running. Run HELIX as a standard user.
echo This is NOT a Windows sandbox. Commands require individual approval.
echo.
".venv\Scripts\python.exe" -m helix.engineer_agent --config config/local.json --workspace "%CD%"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
