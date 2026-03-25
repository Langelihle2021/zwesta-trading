@echo off
REM Zwesta Trader Dashboard Startup Script
REM This script ensures Flask runs persistently on Windows

setlocal enabledelayedexpansion

set PYTHON_PATH=C:\Python313\python.exe
set APP_PATH=C:\zwesta-trader\xm_trading_system\dashboard_enhanced.py
set LOG_FILE=C:\zwesta-trader\flask.log
set ERROR_LOG=C:\zwesta-trader\flask_err.log

echo [%date% %time%] Starting Zwesta Trader Dashboard...

REM Kill any existing Python process on port 5000
taskkill /F /IM python.exe >nul 2>&1

REM Small delay to ensure port is released
timeout /t 2 /nobreak

REM Start Flask in background using PowerShell (more reliable than direct execution)
powershell -NoProfile -Command "Start-Process -FilePath '%PYTHON_PATH%' -ArgumentList '-B','%APP_PATH%' -NoNewWindow -RedirectStandardOutput '%LOG_FILE%' -RedirectStandardError '%ERROR_LOG%'" 

REM Wait for Flask to initialize
timeout /t 3 /nobreak

REM Verify Flask is running
tasklist | findstr "python" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Flask failed to start!
    type %ERROR_LOG%
    pause
    exit /b 1
) else (
    echo [SUCCESS] Flask started successfully!
    echo Dashboard available at:
    echo   - http://127.0.0.1:5000
    echo   - http://192.168.0.137:5000
    echo   - http://38.247.146.198:5000
    echo.
    echo Logs: %LOG_FILE%
    echo.
)

REM Keep log window open and show last 20 lines
echo Monitoring Flask logs (CTRL+C to exit)...
:monitor
timeout /t 5 /nobreak
cls
echo [%date% %time%] Flask Status:
tasklist | findstr "python"
echo.
echo Recent logs:
type %LOG_FILE% | more
goto monitor
