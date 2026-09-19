@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
if exist "config\local.json" goto local

echo Local config not found. Starting labeled demo mode instead.
echo Copy config\local.example.json to config\local.json to use a real local model.
".venv\Scripts\python.exe" -m helix --config "config\demo.json"
goto completed

:local
call START_HELIX_AUTO.cmd
goto completed

:completed
set "HELIX_EXIT=%ERRORLEVEL%"
if "%HELIX_EXIT%"=="0" exit /b 0
echo HELIX stopped with an error. Review the message above.
if not defined HELIX_NO_PAUSE pause
exit /b %HELIX_EXIT%

:missing_python
echo Run SETUP_WINDOWS.cmd first.
if not defined HELIX_NO_PAUSE pause
exit /b 1
