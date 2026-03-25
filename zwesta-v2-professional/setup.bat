@echo off
REM Zwesta v2 - Quick Setup Script for Windows
REM This script sets up your environment with your XM credentials

echo.
echo ======================================
echo Zwesta Trading System v2 - Setup
echo ======================================
echo.

REM Check if backend exists
if not exist "backend" (
    echo Error: backend directory not found
    echo Please run this from: C:\zwesta-trader\zwesta-v2-professional\
    pause
    exit /b 1
)

echo [1/5] Creating .env file with your XM credentials...
if exist "backend\.env" (
    echo WARNING: .env file already exists
    echo Skipping to avoid overwriting your settings
) else (
    copy backend\.env.example backend\.env >nul
    echo Created backend\.env
)

echo.
echo [2/5] Your MT5 credentials are configured:
echo   Account: 136372035
echo   Server: MetaQuotes-Demo
echo   Password: (hidden)
echo.

echo [3/5] Installing Python dependencies...
cd backend
pip install -q -r requirements-minimal.txt
if errorlevel 1 (
    echo Error installing dependencies
    pause
    exit /b 1
)
cd ..

echo [4/5] Installing Node.js dependencies...
if not exist "frontend\node_modules" (
    cd frontend
    call npm install
    cd ..
) else (
    echo Node dependencies already installed
)

echo.
echo [5/5] Setup complete!
echo.
echo ======================================
echo Next Steps:
echo ======================================
echo.
echo Terminal 1 - Start Backend:
echo   cd backend
echo   python app_simple.py
echo.
echo Terminal 2 - Start Frontend:
echo   cd frontend
echo   npm run dev
echo.
echo Then open your browser:
echo   http://localhost:3000 (Web Dashboard)
echo   http://localhost:8000/docs (API Docs)
echo.
echo Demo Credentials: demo / demo
echo.
echo ======================================
echo.
pause
