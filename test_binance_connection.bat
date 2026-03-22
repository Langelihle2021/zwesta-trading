@echo off
REM Quick Binance Connection Test & Bot Creation Script (Windows)
REM This script tests your Binance API and creates a demo trading bot

setlocal enabledelayedexpansion

set BACKEND_URL=http://localhost:9000
set SESSION_TOKEN=debug_token_49b6b05ad32648759f26f6ac37eebcef

REM Your Binance API credentials (from HMAC dashboard)
set API_KEY=JBPMO44roltRZjQhxM0YqZLCgpYd7dHiddZru8GHJzJI6AveL3yv3M95imfFZT3b
set API_SECRET=your_api_secret_here

echo.
echo ================================================================
echo ^^ ZWESTA TRADER - BINANCE BOT TEST FLOW ^^
echo ================================================================
echo.

REM Check if backend is running
echo ^[1^] Checking if backend is running...
timeout /t 1 /nobreak >nul
curl -s %BACKEND_URL%/health >nul 2>&1
if !errorlevel! equ 0 (
    echo ^✓ Backend is running
) else (
    echo ^✗ ERROR: Backend not running at %BACKEND_URL%
    echo   Make sure your backend is running on port 9000
    pause
    exit /b 1
)

echo.
echo ^[2^] Testing Binance Connection...
echo.

REM Test connection
curl -X POST %BACKEND_URL%/api/broker/test-connection ^
  -H "Content-Type: application/json" ^
  -H "X-Session-Token: %SESSION_TOKEN%" ^
  -d { ^
    "broker": "Binance", ^
    "api_key": "%API_KEY%", ^
    "api_secret": "%API_SECRET%", ^
    "is_live": false, ^
    "market": "spot" ^
  }

echo.
echo.
echo ^[3^] Copy the credential_id from the response above
echo.
echo ^[4^] Create bot by replacing CREDENTIAL_ID and running:
echo.
echo curl -X POST %BACKEND_URL%/api/bot/create ^
  -H "Content-Type: application/json" ^
  -H "X-Session-Token: %SESSION_TOKEN%" ^
  -d { ^
    "credentialId": "CREDENTIAL_ID", ^
    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"], ^
    "strategy": "Momentum Trading", ^
    "riskPerTrade": 15, ^
    "maxDailyLoss": 50, ^
    "enabled": true ^
  }
echo.

pause
