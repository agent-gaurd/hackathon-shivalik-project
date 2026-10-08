@echo off
setlocal enabledelayedexpansion

title AgentGuard Launcher

echo ===============================================================================
echo                           Starting AgentGuard
echo ===============================================================================
echo.

:: 1. Detect project root
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

cd /d "%PROJECT_ROOT%"
echo [INFO] Project root: %PROJECT_ROOT%

:: 2. Find Python interpreter
set "PY_CMD="
where py >nul 2>&1 && (
    py -3 --version >nul 2>&1 && set "PY_CMD=py -3"
)
if "!PY_CMD!"=="" (
    where python >nul 2>&1 && (
        python --version >nul 2>&1 && set "PY_CMD=python"
    )
)
if "!PY_CMD!"=="" (
    where python3 >nul 2>&1 && (
        python3 --version >nul 2>&1 && set "PY_CMD=python3"
    )
)

if "!PY_CMD!"=="" (
    echo [ERROR] Python was not found on your PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check the box "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [INFO] Using Python: !PY_CMD!

:: 3. Setup virtual environment (.venv)
if not exist ".venv" (
    echo [INFO] Creating virtual environment (.venv)...
    !PY_CMD! -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Installing dependencies from backend\requirements.txt...
    if exist "backend\requirements.txt" (
        ".venv\Scripts\python.exe" -m pip install --upgrade pip
        ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
    ) else if exist "requirements.txt" (
        ".venv\Scripts\python.exe" -m pip install --upgrade pip
        ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    )
    if errorlevel 1 (
        echo [WARNING] Dependency installation had warnings/errors. Proceeding...
    )
)

set "VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "!VENV_PY!" (
    set "VENV_PY=!PY_CMD!"
)

:: 4. Configure Port and Environment
if "%PORT%"=="" set PORT=8000
set AG_DEV=1

echo.
echo [INFO] AgentGuard running at: http://localhost:%PORT%
echo [INFO] Press Ctrl+C in this window to stop the server.
echo.

:: 5. Open browser and run server
start "" http://localhost:%PORT%

cd /d "%PROJECT_ROOT%\backend"
"!VENV_PY!" -m uvicorn main:app --host 127.0.0.1 --port %PORT%

if errorlevel 1 (
    echo.
    echo [ERROR] AgentGuard server stopped with error code %errorlevel%.
)
echo.
pause
