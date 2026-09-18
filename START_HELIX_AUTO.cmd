@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.cmd first.
    pause
    exit /b 1
)

if not exist "config\local.json" (
    echo Missing config\local.json
    pause
    exit /b 1
)

for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; $r=New-Object Security.Cryptography.RNGCryptoServiceProvider; $r.GetBytes($b); $r.Dispose(); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')"`) do set "HELIX_API_KEY=%%K"

echo.
echo Starting Helix with a fresh rotated local access key...
echo The browser will receive it automatically.
echo Keep this window open.
echo Press Ctrl+C to stop Helix.
echo.

start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/#key=%HELIX_API_KEY%'"

".venv\Scripts\python.exe" -m helix --config "config\local.json"

endlocal