@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo HELIX virtual environment is missing. Run SETUP_WINDOWS.cmd first.
    exit /b 1
)
echo Activating persistent HELIX Emergency Lockdown...
".venv\Scripts\python.exe" -m helix.safety lock --reason "Owner emergency switch"
if errorlevel 1 (
    echo Lockdown command reported an error. Engineer actions should fail closed; inspect the message above.
    exit /b 1
)
echo HELIX Engineer actions are LOCKED across app restarts.
echo Already-completed changes are not undone.
exit /b 0
