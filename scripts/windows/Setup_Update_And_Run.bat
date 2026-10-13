@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\.."
cd /d "%PROJECT_ROOT%"
title OBD-II Dashboard - Setup and Update

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_COMMAND=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python was not found on PATH. Install Python 3.10 or newer and try again.
        echo Download Python from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PYTHON_COMMAND=python"
)

%PYTHON_COMMAND% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo Python 3.10 or newer is required. Update Python and try again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project virtual environment...
    %PYTHON_COMMAND% -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Could not activate the project virtual environment.
    pause
    exit /b 1
)

echo Updating pip and project dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Could not update pip. Check your internet connection and try again.
    pause
    exit /b 1
)
python -m pip install --upgrade -e .
if errorlevel 1 (
    echo Project setup failed. Check your internet connection and Python version.
    pause
    exit /b 1
)

if not exist "data\sample\session_1.csv" (
    echo Creating the labeled synthetic demo logs...
    obd-make-samples
    if errorlevel 1 (
        echo Could not create the sample logs.
        pause
        exit /b 1
    )
)

echo Opening the OBD-II dashboard in your browser...
python -m streamlit run "%PROJECT_ROOT%\app.py"
if errorlevel 1 (
    echo The dashboard stopped with an error.
    pause
    exit /b 1
)
endlocal
