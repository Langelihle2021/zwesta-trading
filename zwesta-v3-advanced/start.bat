@echo off
REM Zwesta Trading System v3 - Windows Startup Script

echo.
echo Creating Python virtual environment...
cd backend
python -m venv venv
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
cd..

echo.
echo 🚀 Zwesta Trading System v3 - Startup
echo ========================================

REM Start backend
echo.
echo 🔧 Starting FastAPI backend on localhost:8000...
start cmd /k "cd backend && python main.py"

timeout /t 3 /nobreak

REM Start frontend
echo 🎨 Starting React frontend on localhost:3001...
start cmd /k "cd frontend && npm install && npm run dev"

timeout /t 3 /nobreak

echo.
echo ✅ Zwesta Trading System v3 is starting!
echo ========================================
echo 📊 Dashboard: http://localhost:3001
echo 🔌 API: http://localhost:8000
echo 📚 API Docs: http://localhost:8000/docs
echo.
echo Login with:
echo   Username: demo
echo   Password: demo123
echo.
pause
