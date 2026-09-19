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

set "HELIX_WORKSPACE=%~1"
if not defined HELIX_WORKSPACE set "HELIX_WORKSPACE=%CD%"
if not exist "%HELIX_WORKSPACE%\." (
    echo Workspace does not exist: %HELIX_WORKSPACE%
    echo Usage: START_HELIX_AGENT.cmd "C:\path\to\repository"
    goto failed
)

".venv\Scripts\python.exe" -m tools.check_startup
if errorlevel 1 goto failed

rem Never reuse an inherited key if fresh key generation fails.
set "HELIX_API_KEY="
for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; $r=New-Object Security.Cryptography.RNGCryptoServiceProvider; $r.GetBytes($b); $r.Dispose(); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')"`) do set "HELIX_API_KEY=%%K"
if not defined HELIX_API_KEY goto key_failed

echo HELIX Engineer workspace: %HELIX_WORKSPACE%
echo Run HELIX as a standard Windows user, not Administrator.
echo Commands are NOT sandboxed and require individual approval.
echo Opening the normal HELIX command center with Engineer Jobs enabled.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/#key=%HELIX_API_KEY%'"
".venv\Scripts\python.exe" -m helix --config "config\local.json" --workspace "%HELIX_WORKSPACE%"
set "HELIX_EXIT=%ERRORLEVEL%"
if "%HELIX_EXIT%"=="0" exit /b 0
echo HELIX Engineer workspace stopped with an error. Review the message above.
if not defined HELIX_NO_PAUSE pause
exit /b %HELIX_EXIT%

:key_failed
echo Local access-key generation failed. Engineer workspace was not started.
goto failed

:failed
echo Engineer workspace was not started. Review the first error above.
if not defined HELIX_NO_PAUSE pause
exit /b 1
