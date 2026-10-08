@echo off
setlocal enabledelayedexpansion

title Stop AgentGuard Suite

echo ===============================================================================
echo                           Stopping AgentGuard Suite
echo ===============================================================================
echo.

set PORTS=9000 8001 8002 8003

for %%P in (%PORTS%) do (
    echo [INFO] Checking for processes listening on port %%P...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%%P " ^| findstr "LISTENING"') do (
        echo [INFO] Terminating PID %%a on port %%P...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [INFO] AgentGuard Suite services stopped successfully.
echo.
ping 127.0.0.1 -n 2 >nul
