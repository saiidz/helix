@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.cmd first.
    pause
    exit /b 1
)

if exist "config\local.json" (
    echo Starting Helix with the local model configuration...
    call START_HELIX_AUTO.cmd
    exit /b %ERRORLEVEL%
)

echo Local config not found. Starting labeled demo mode instead.
echo Copy config\local.example.json to config\local.json to use a real local model.
echo.
".venv\Scripts\python.exe" -m helix --config "config\demo.json"
set "HELIX_EXIT=%ERRORLEVEL%"

if not "%HELIX_EXIT%"=="0" (
    echo.
    echo Helix stopped with an error. Review the message above.
    pause
)

exit /b %HELIX_EXIT%
