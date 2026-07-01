@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   What model does my API key support (wmd-my-API-ks)
echo ===================================================
echo.

REM Verify python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.8+ and ensure it is added to your environment variables.
    pause
    exit /b 1
)

REM Verify virtual environment folder exists
if not exist ".venv" (
    echo [INFO] Virtual environment .venv not found. Creating it...
    python -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Virtual environment created successfully.
)

REM Setup python dependencies
echo [INFO] Activating virtual environment and updating dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [INFO] Launching TUI Application...
echo.
python app.py
echo.
echo [INFO] Application exited.
pause
