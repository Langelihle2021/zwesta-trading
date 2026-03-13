# MT5 Health Monitor - PowerShell Setup Script
# Run as Administrator: powershell -ExecutionPolicy Bypass -File setup_mt5_monitor.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Continue"

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "MT5 HEALTH MONITOR SETUP" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python found: $pythonCheck" -ForegroundColor Green
} else {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ first" -ForegroundColor Red
    exit 1
}

# Install packages
Write-Host "`nInstalling required Python packages..." -ForegroundColor Yellow
pip install -q psutil MetaTrader5
Write-Host "✅ Python packages installed" -ForegroundColor Green

# Create directory
$scriptDir = "C:\backend\mt5_monitor"
if (-not (Test-Path $scriptDir)) {
    New-Item -ItemType Directory -Path $scriptDir | Out-Null
    Write-Host "✅ Created directory: $scriptDir" -ForegroundColor Green
}

# Copy monitor script
Write-Host "`nCopying monitor script..." -ForegroundColor Yellow
Copy-Item -Path "mt5_health_monitor.py" -Destination "$scriptDir\mt5_health_monitor.py" -Force
Write-Host "✅ Monitor script copied" -ForegroundColor Green

# Create startup wrapper
Write-Host "`nCreating startup script..." -ForegroundColor Yellow
$startBatch = @"
@echo off
cd /d "$scriptDir"
python mt5_health_monitor.py
"@

$startBatch | Out-File -FilePath "$scriptDir\start_monitor.bat" -Encoding ASCII -Force
Write-Host "✅ Startup script created" -ForegroundColor Green

# Create scheduled task
Write-Host "`nCreating Windows Scheduled Task..." -ForegroundColor Yellow

# Remove old task if exists
$taskExists = Get-ScheduledTask -TaskName "MT5 Health Monitor" -ErrorAction SilentlyContinue
if ($taskExists) {
    Unregister-ScheduledTask -TaskName "MT5 Health Monitor" -Confirm:$false
}

# Create trigger (at startup and daily)
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger += New-ScheduledTaskTrigger -Daily -At 12:00AM

# Create action
$action = New-ScheduledTaskAction -Execute "$scriptDir\start_monitor.bat"

# Create task settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false

# Register task
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

Register-ScheduledTask -TaskName "MT5 Health Monitor" `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Description "Automatically monitors and restarts MT5 on disconnection" `
    -Force | Out-Null

Write-Host "✅ Scheduled Task created: 'MT5 Health Monitor'" -ForegroundColor Green

# Start the task
Write-Host "`nStarting monitor..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName "MT5 Health Monitor" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE ✅" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

Write-Host "The MT5 Health Monitor is now configured to:" -ForegroundColor White
Write-Host "  ✓ Monitor MT5 connection every 30 seconds" -ForegroundColor Green
Write-Host "  ✓ Automatically restart MT5 if disconnected" -ForegroundColor Green
Write-Host "  ✓ Run automatically on system startup" -ForegroundColor Green
Write-Host "`nLog file: $scriptDir\mt5_health_monitor.log" -ForegroundColor Cyan

Write-Host "`nStatus:" -ForegroundColor Yellow
$task = Get-ScheduledTask -TaskName "MT5 Health Monitor"
Write-Host "  State: $($task.State)" -ForegroundColor White

Write-Host "`nTo view the log:" -ForegroundColor Yellow
Write-Host "  Get-Content '$scriptDir\mt5_health_monitor.log' -Wait`n" -ForegroundColor Gray

Write-Host "To stop monitoring:" -ForegroundColor Yellow
Write-Host "  Stop-ScheduledTask -TaskName 'MT5 Health Monitor'`n" -ForegroundColor Gray

Write-Host "To restart monitoring:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'MT5 Health Monitor'`n" -ForegroundColor Gray

Read-Host "Press Enter to exit"
