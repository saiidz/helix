@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.cmd first.
    exit /b 1
)
rem Read-only diagnostics: no Git changes, downloads, inference or process termination.
".venv\Scripts\python.exe" -m tools.check_startup
set "HELIX_EXIT=%ERRORLEVEL%"
if not defined HELIX_NO_PAUSE pause
exit /b %HELIX_EXIT%
