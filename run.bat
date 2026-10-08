@echo off
setlocal enabledelayedexpansion

title AgentGuard Suite Launcher

if exist "%~dp0agentguard-suite\run.bat" (
    cd /d "%~dp0agentguard-suite"
    call run.bat
) else (
    echo [ERROR] agentguard-suite\run.bat not found.
    pause
)
