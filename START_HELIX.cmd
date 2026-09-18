@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.cmd first.
    pause
    exit /b 1
)
echo Starting the local demo. Leave this window open while using Helix.
echo Open http://127.0.0.1:8765 and paste the access key printed below.
echo Do not share the key or expose this prototype to the internet.
echo Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" -m helix --config config/demo.json
set "HELIX_EXIT=%ERRORLEVEL%"
if not "%HELIX_EXIT%"=="0" (
    echo.
    echo Helix stopped with an error. Review the message above.
    pause
)
exit /b %HELIX_EXIT%
