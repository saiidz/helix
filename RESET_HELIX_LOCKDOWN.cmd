@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo HELIX virtual environment is missing. Run SETUP_WINDOWS.cmd first.
    exit /b 1
)
echo Reset is intentionally unavailable through the HELIX web API.
echo This terminal must remain interactive.
".venv\Scripts\python.exe" -m helix.safety unlock
set "HELIX_EXIT=%ERRORLEVEL%"
if not "%HELIX_EXIT%"=="0" (
    echo Lockdown remains active.
    if not defined HELIX_NO_PAUSE pause
    exit /b %HELIX_EXIT%
)
echo HELIX reviewed Engineer actions are enabled again.
if not defined HELIX_NO_PAUSE pause
exit /b 0
