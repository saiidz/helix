@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
if not exist "config\local.json" goto missing_config

".venv\Scripts\python.exe" -m tools.check_startup
if errorlevel 1 goto failed

rem Never reuse an inherited key if fresh key generation fails.
set "HELIX_API_KEY="
for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "$b=New-Object byte[] 32; $r=New-Object Security.Cryptography.RNGCryptoServiceProvider; $r.GetBytes($b); $r.Dispose(); [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')"`) do set "HELIX_API_KEY=%%K"
if not defined HELIX_API_KEY goto key_failed

echo Starting HELIX with a fresh local access key.
echo Keep this window open. Press Ctrl+C to stop HELIX.
rem Preserve existing browser auto-connect. Preflight rejects an occupied app port.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/#key=%HELIX_API_KEY%'"
".venv\Scripts\python.exe" -m helix --config "config\local.json"
set "HELIX_EXIT=%ERRORLEVEL%"
exit /b %HELIX_EXIT%

:missing_python
echo Run SETUP_WINDOWS.cmd first.
exit /b 1
:missing_config
echo Missing config\local.json. Review the local model configuration.
exit /b 1
:key_failed
echo Local access-key generation failed. HELIX was not started.
exit /b 1
:failed
echo Startup preflight failed. HELIX was not started.
exit /b 1
