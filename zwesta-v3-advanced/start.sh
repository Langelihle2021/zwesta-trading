#!/bin/bash

# Zwesta Trading System v3 - Complete Startup Script

echo "🚀 Zwesta Trading System v3 - Startup"
echo "========================================"

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
pip install -q -r requirements.txt
cd ..

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --q 2>/dev/null
cd ..

# Start backend in background
echo "🔧 Starting FastAPI backend..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

sleep 3

# Start frontend
echo "🎨 Starting React frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo ""
echo "✅ Zwesta Trading System v3 is running!"
echo "========================================"
echo "📊 Dashboard: http://localhost:3001"
echo "🔌 API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Login with:"
echo "  Username: demo"
echo "  Password: demo123"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

wait $BACKEND_PID $FRONTEND_PID
