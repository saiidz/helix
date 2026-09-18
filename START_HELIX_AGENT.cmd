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
echo HELIX reviewed Engineer Agent - workspace is this HELIX repository.
echo Stop the old HELIX web server first. Keep llama-server running.
echo Run HELIX as a standard Windows user, not Administrator.
echo Commands are NOT sandboxed and require individual approval.
echo Open http://127.0.0.1:8765/agent after startup.
echo.
".venv\Scripts\python.exe" -m helix --config config/local.json --workspace "%CD%"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
