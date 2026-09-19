@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo HELIX update and validation
set "HELIX_STAGE=Python environment"
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run SETUP_WINDOWS.cmd first.
    goto failed
)
set "HELIX_STAGE=Git availability"
git --version
if errorlevel 1 goto failed
set "HELIX_STAGE=Uncommitted tracked changes - preserve your work before updating"
git diff --quiet
if errorlevel 1 goto failed
git diff --cached --quiet
if errorlevel 1 goto failed

set "HELIX_STAGE=Fetch origin"
echo [1/7] Fetching updates...
git fetch origin
if errorlevel 1 goto failed
set "HELIX_STAGE=Switch to the development branch"
git switch feat/codex-inspired-ui-v02
if errorlevel 1 goto failed
set "HELIX_STAGE=Fast-forward the explicit remote branch"
git pull --ff-only origin feat/codex-inspired-ui-v02
if errorlevel 1 goto failed

set "HELIX_STAGE=Offline startup preflight"
echo [2/7] Checking files, imports and local configuration...
".venv\Scripts\python.exe" -m tools.check_startup --offline --tracked-private
if errorlevel 1 goto failed
set "HELIX_STAGE=Dependency consistency"
echo [3/7] Checking installed dependencies...
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
set "HELIX_STAGE=Full regression tests"
echo [4/7] Running the complete test suite...
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed
set "HELIX_STAGE=Python compilation"
echo [5/7] Compiling Python sources...
".venv\Scripts\python.exe" -m compileall -q helix tests tools
if errorlevel 1 goto failed
set "HELIX_STAGE=Offline intelligence evaluation"
echo [6/7] Running routing and reasoning checks...
".venv\Scripts\python.exe" -m tools.intelligence_eval
if errorlevel 1 goto failed

set "HELIX_STAGE=Local model and app port readiness"
echo [7/7] Checking the configured local model servers and app port...
".venv\Scripts\python.exe" -m tools.check_startup
if errorlevel 1 goto failed

echo.
echo Local validation passed. This does not merge or deploy a GitHub pull request.
echo Starting normal HELIX chat. Agent command access stays disabled.
call START_HELIX.cmd
set "HELIX_EXIT=%ERRORLEVEL%"
exit /b %HELIX_EXIT%

:failed
set "HELIX_EXIT=%ERRORLEVEL%"
if "%HELIX_EXIT%"=="0" set "HELIX_EXIT=1"
echo.
echo FAILED STAGE: %HELIX_STAGE%
echo Exit code: %HELIX_EXIT%
echo HELIX was not started by this failed validation run.
echo No reset, stash, force-push or PR merge was performed.
echo Review the first error above. Do not share access keys or config/local.json.
if not defined HELIX_NO_PAUSE pause
exit /b %HELIX_EXIT%
