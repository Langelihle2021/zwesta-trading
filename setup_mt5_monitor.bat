@echo off
REM MT5 Health Monitor - Windows Service Installer
REM This script installs MT5 Health Monitor as a Windows Service that auto-starts
REM Run as Administrator

setlocal enabledelayedexpansion

cls
echo.
echo ================================
echo MT5 HEALTH MONITOR SETUP
echo ================================
echo.

REM Check if running as Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] This script MUST be run as Administrator!
    echo Right-click Command Prompt and select "Run as Administrator"
    pause
    exit /b 1
)

echo [OK] Running as Administrator
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ first
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

REM Install required Python packages
echo Installing required Python packages...
pip install psutil MetaTrader5 --quiet
if %errorlevel% equ 0 (
    echo [OK] Python packages installed
) else (
    echo [WARNING] Some packages failed to install, but continuing...
)
echo.

REM Create directory for scripts
set SCRIPT_DIR=C:\backend\mt5_monitor
if not exist "%SCRIPT_DIR%" (
    mkdir "%SCRIPT_DIR%"
    echo [OK] Created directory: %SCRIPT_DIR%
)
echo.

REM Copy monitor script
echo Copying MT5 health monitor script...
copy mt5_health_monitor.py "%SCRIPT_DIR%\mt5_health_monitor.py" >nul
if %errorlevel% equ 0 (
    echo [OK] Monitor script copied to %SCRIPT_DIR%
) else (
    echo [ERROR] Failed to copy script
    pause
    exit /b 1
)
echo.

REM Check if NSSM is installed (for service management)
where nssm >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] NSSM not found - creating alternative startup method
    
    REM Create a scheduled task instead
    echo Creating Windows Scheduled Task...
    
    REM Create a batch file that the task will run
    (
        echo @echo off
        echo cd /d "%SCRIPT_DIR%"
        echo python mt5_health_monitor.py
    ) > "%SCRIPT_DIR%\start_monitor.bat"
    
    REM Create scheduled task that runs at startup
    schtasks /create /tn "MT5 Health Monitor" /tr "%SCRIPT_DIR%\start_monitor.bat" /sc onstart /ru SYSTEM /f >nul 2>&1
    
    if %errorlevel% equ 0 (
        echo [OK] Scheduled Task created: "MT5 Health Monitor"
        echo     Will start automatically on system boot
    ) else (
        echo [WARNING] Failed to create scheduled task
        echo Try running manually: python "%SCRIPT_DIR%\mt5_health_monitor.py"
    )
    
) else (
    echo [OK] NSSM found - creating Windows Service...
    
    REM Remove existing service if it exists
    nssm remove "MT5HealthMonitor" confirm >nul 2>&1
    
    REM Create new service
    nssm install "MT5HealthMonitor" python "%SCRIPT_DIR%\mt5_health_monitor.py"
    
    REM Configure service to auto-restart on failure
    nssm set "MT5HealthMonitor" AppRestartDelay 5000
    nssm set "MT5HealthMonitor" Start SERVICE_AUTO_START
    
    REM Start the service
    net start "MT5HealthMonitor" >nul 2>&1
    
    echo [OK] Windows Service created and started
    echo     Service Name: MT5HealthMonitor
    echo     Start Type: Automatic
)
echo.

REM Show status
echo ================================
echo SETUP COMPLETE
echo ================================
echo.
echo The MT5 Health Monitor is now configured to:
echo  ✓ Monitor MT5 connection every 30 seconds
echo  ✓ Automatically restart MT5 if disconnected
echo  ✓ Run automatically on system startup
echo.
echo Log file: %SCRIPT_DIR%\mt5_health_monitor.log
echo.
echo To view monitor status, check the log file:
echo   type "%SCRIPT_DIR%\mt5_health_monitor.log"
echo.
echo To manually start monitoring:
echo   python "%SCRIPT_DIR%\mt5_health_monitor.py"
echo.
pause
