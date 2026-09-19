@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo HELIX virtual environment is missing. Run SETUP_WINDOWS.cmd first.
    goto failed
)
if not exist "config\local.json" (
    echo config\local.json is missing. Configure the local Engineer model first.
    goto failed
)
".venv\Scripts\python.exe" -m tools.check_startup
if errorlevel 1 goto failed
echo HELIX reviewed Engineer Agent - workspace is this HELIX repository.
echo Run HELIX as a standard Windows user, not Administrator.
echo Commands are NOT sandboxed and require individual approval.
echo Open http://127.0.0.1:8765/agent after startup.
".venv\Scripts\python.exe" -m helix --config config/local.json --workspace "%CD%"
set "HELIX_EXIT=%ERRORLEVEL%"
if not defined HELIX_NO_PAUSE pause
exit /b %HELIX_EXIT%

:failed
echo Agent was not started. Review the first error above.
if not defined HELIX_NO_PAUSE pause
exit /b 1
