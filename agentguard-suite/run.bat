@echo off
setlocal enabledelayedexpansion

title AgentGuard Suite Launcher

echo ===============================================================================
echo                      Starting Unified AgentGuard Suite
echo ===============================================================================
echo.

set "SUITE_ROOT=%~dp0"
if "%SUITE_ROOT:~-1%"=="\" set "SUITE_ROOT=%SUITE_ROOT:~0,-1%"
cd /d "%SUITE_ROOT%"

:: 1. Find Python interpreter
set "PY_CMD="
if exist "%SUITE_ROOT%\.venv\Scripts\python.exe" (
    set "PY_CMD=%SUITE_ROOT%\.venv\Scripts\python.exe"
) else (
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

:: 2. Setup virtual environments if needed
:: Project 1 venv
set "P1_DIR=%SUITE_ROOT%\projects\project1"
set "P1_PY=!PY_CMD!"
if exist "%P1_DIR%\.venv\Scripts\python.exe" (
    set "P1_PY=%P1_DIR%\.venv\Scripts\python.exe"
)

:: Project 2 venv
set "P2_DIR=%SUITE_ROOT%\projects\project2"
set "P2_PY=!PY_CMD!"
if exist "%P2_DIR%\.venv\Scripts\python.exe" (
    set "P2_PY=%P2_DIR%\.venv\Scripts\python.exe"
)

:: Project 3 venv
set "P3_DIR=%SUITE_ROOT%\projects\project3"
set "P3_PY=!PY_CMD!"
if exist "%P3_DIR%\.venv\Scripts\python.exe" (
    set "P3_PY=%P3_DIR%\.venv\Scripts\python.exe"
)

:: Gateway venv
set "GW_DIR=%SUITE_ROOT%\gateway"
set "GW_PY=!PY_CMD!"

:: 3. Configure environment
set AG_DEV=1
set AG_SUITE_SECRET=agentguard-suite-dev-secret-key-2026

:: 4. Stop any existing processes on ports 9000, 8001, 8002, 8003
echo [INFO] Checking for existing instances on ports 9000, 8001, 8002, 8003...
call "%SUITE_ROOT%\stop.bat" >nul 2>&1

:: 5. Launch Project 1 Backend (Port 8001)
echo [INFO] Starting Project 1 (6-Agent Core Engine) on port 8001...
start "AgentGuard - Project 1 (:8001)" /MIN cmd /c "cd /d "%P1_DIR%" && !P1_PY! -m uvicorn backend.main:app --host 127.0.0.1 --port 8001"

:: 6. Launch Project 2 Backend (Port 8002)
echo [INFO] Starting Project 2 (Money Map ^& Policy Console) on port 8002...
start "AgentGuard - Project 2 (:8002)" /MIN cmd /c "cd /d "%P2_DIR%\backend" && !P2_PY! -m uvicorn main:app --host 127.0.0.1 --port 8002"

:: 7. Launch Project 3 Backend (Port 8003)
echo [INFO] Starting Project 3 (Model Analytics ^& Decision Intelligence) on port 8003...
start "AgentGuard - Project 3 (:8003)" /MIN cmd /c "cd /d "%P3_DIR%\backend" && !P3_PY! -m uvicorn main:app --host 127.0.0.1 --port 8003"

:: 8. Launch Gateway (Port 9000)
echo [INFO] Starting Gateway ^& Portal on port 9000...
start "AgentGuard - Gateway (:9000)" /MIN cmd /c "cd /d "%GW_DIR%" && !GW_PY! -m uvicorn main:app --host 0.0.0.0 --port 9000"

:: 9. Wait for Gateway & Backends Health Check
echo [INFO] Waiting for services to become healthy...
set /a attempts=0
:health_loop
set /a attempts+=1
if !attempts! geq 25 (
    echo [WARNING] Health check timed out after 25 attempts. Services may still be starting.
    goto open_browser
)
ping 127.0.0.1 -n 2 >nul
powershell -Command "try { $res = Invoke-RestMethod -Uri 'http://127.0.0.1:9000/health' -TimeoutSec 1; if ($res.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    goto health_loop
)

echo [INFO] All services healthy!

:open_browser
echo.
echo ===============================================================================
echo   AgentGuard Suite running at: http://localhost:9000
echo   - Portal / Login:  http://localhost:9000
echo   - Project 1 UI:    http://localhost:9000/p1/
echo   - Project 2 UI:    http://localhost:9000/p2/
echo   - Project 3 UI:    http://localhost:9000/p3/
echo   - Demo Logins:     admin / admin123 (all projects)
echo                      analyst1 / analyst123 (project 1 only)
echo                      analyst2 / analyst234 (project 2 only)
echo                      analyst3 / analyst345 (project 3 only)
echo ===============================================================================
echo.

start "" http://localhost:9000

echo [INFO] Press any key to stop all services...
pause >nul

echo [INFO] Stopping all services...
call "%SUITE_ROOT%\stop.bat"
echo [INFO] Done.
