@echo off
setlocal
cd /d "%~dp0"

echo Helix local engineering loop
echo ============================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run SETUP_WINDOWS.cmd first.
    pause
    exit /b 1
)

echo [1/5] Fetching the latest feature branch...
git fetch origin
if errorlevel 1 goto failed

git switch feat/codex-inspired-ui-v02
if errorlevel 1 goto failed

git pull --ff-only
if errorlevel 1 goto failed

echo.
echo [2/5] Running tests...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed

echo.
echo [3/5] Compiling Python sources...
".venv\Scripts\python.exe" -m compileall -q helix tests tools
if errorlevel 1 goto failed

echo.
echo [4/5] Checking for accidentally staged local/private files...
git status --short
echo.
echo Review the status above. .helix, config\local.json, .venv and model weights must stay untracked.

echo.
echo [5/5] Checking the local model server...
powershell -NoProfile -Command "try { $m=Invoke-RestMethod 'http://127.0.0.1:8080/v1/models' -TimeoutSec 2; Write-Host 'Local model server: READY'; exit 0 } catch { Write-Host 'Local model server: NOT RUNNING on port 8080'; exit 2 }"
if errorlevel 2 (
    echo.
    echo Start llama.cpp in a separate window, for example:
    echo   llama-server -hf ggml-org/Qwen3-4B-GGUF:Q4_K_M
    echo.
    echo Then run START_HELIX.cmd.
    pause
    exit /b 0
)

echo.
echo All local checks passed.
echo Starting Helix...
call START_HELIX.cmd
exit /b %ERRORLEVEL%

:failed
echo.
echo The engineering loop stopped on the first failed check.
echo Nothing was merged automatically.
pause
exit /b 1
