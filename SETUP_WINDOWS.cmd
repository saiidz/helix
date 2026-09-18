@echo off
setlocal
cd /d "%~dp0"

echo Helix - Windows setup, Python 3.13
echo This installs Python dependencies, then runs local tests.
echo It does NOT download AI models, call paid APIs, or upload code.
echo.

if exist ".venv\Scripts\python.exe" goto check_venv

if exist ".venv" (
    echo ERROR: .venv already exists without a Windows Python executable.
    echo Move this project to a clean folder, or review the existing environment.
    goto failed
)

py -3.13 -c "import sys; assert sys.version_info[:2] == (3,13)" >nul 2>&1
if errorlevel 1 goto try_python

py -3.13 -m venv .venv
if errorlevel 1 goto failed
goto check_venv

:try_python
python -c "import sys; assert sys.version_info[:2] == (3,13)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.13 was not found.
    echo Install Python 3.13 for Windows and run this file again.
    goto failed
)

python -m venv .venv
if errorlevel 1 goto failed

:check_venv
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,13), 'This launcher expects Python 3.13'"
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed

".venv\Scripts\python.exe" -m compileall -q helix tests tools
if errorlevel 1 goto failed

echo.
echo Setup and tests completed.
echo.
if exist "config\local.json" (
    echo A local model configuration already exists.
    echo Double-click START_HELIX.cmd to launch Helix.
) else (
    echo No local model configuration exists yet.
    echo Copy config\local.example.json to config\local.json after starting your local model server.
)
echo.
pause
exit /b 0

:failed
echo.
echo Setup stopped. Review the first error above.
echo Nothing was pushed to GitHub and no paid API was called.
pause
exit /b 1
