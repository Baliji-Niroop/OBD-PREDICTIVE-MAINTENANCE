@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
title OBD-II Dashboard

if not exist ".venv\Scripts\python.exe" (
    echo The project environment is not set up yet.
    echo Starting the setup, dependency update, and dashboard launcher...
    call "%~dp0Setup_Update_And_Run.bat"
    exit /b %errorlevel%
)

call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Could not activate the project environment. Run scripts\windows\Setup_Update_And_Run.bat.
    pause
    exit /b 1
)

python -m streamlit run "%PROJECT_ROOT%\app.py"
if errorlevel 1 (
    echo The dashboard stopped with an error. Run scripts\windows\Setup_Update_And_Run.bat to repair or update it.
    pause
    exit /b 1
)
endlocal
