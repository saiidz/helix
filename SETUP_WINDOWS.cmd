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
    echo ERROR: Python 3.13 was not found. Install Python 3.13 for Windows,
    echo reopen your terminal or Explorer, then run this file again.
    echo See docs\WINDOWS_SETUP.md. No software was installed by this check.
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
".venv\Scripts\python.exe" -m pytest
if errorlevel 1 goto failed
echo.
echo Setup and tests completed. Double-click START_HELIX.cmd next.
echo The default mode is a labeled demonstration, not a trained AI model.
pause
exit /b 0

:failed
echo.
echo Setup stopped. Review the first error above. Nothing was pushed to GitHub.
pause
exit /b 1
