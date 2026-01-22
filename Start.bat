@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    echo [INFO] Using virtual environment...
    ".venv\Scripts\python.exe" main_gui.py
) else (
    echo [ERROR] Virtual environment not found! 
    echo Please run: pip install -r requirements.txt
    pause
    exit /b
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with error code %errorlevel%
    pause
)
