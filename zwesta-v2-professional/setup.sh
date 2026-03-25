#!/bin/bash
# Zwesta v2 - Quick Setup Script for Linux/Mac
# This script sets up your environment with your XM credentials

echo ""
echo "======================================"
echo "Zwesta Trading System v2 - Setup"
echo "======================================"
echo ""

# Check if backend exists
if [ ! -d "backend" ]; then
    echo "Error: backend directory not found"
    echo "Please run this from: /path/to/zwesta-v2-professional/"
    exit 1
fi

echo "[1/5] Creating .env file with your XM credentials..."
if [ -f "backend/.env" ]; then
    echo "WARNING: .env file already exists"
    echo "Skipping to avoid overwriting your settings"
else
    cp backend/.env.example backend/.env
    echo "Created backend/.env"
fi

echo ""
echo "[2/5] Your MT5 credentials are configured:"
echo "   Account: 136372035"
echo "   Server: MetaQuotes-Demo"
echo "   Password: (hidden)"
echo ""

echo "[3/5] Installing Python dependencies..."
cd backend
pip install -q -r requirements-minimal.txt
if [ $? -ne 0 ]; then
    echo "Error installing Python dependencies"
    exit 1
fi
cd ..

echo "[4/5] Installing Node.js dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    cd frontend
    npm install
    cd ..
else
    echo "Node dependencies already installed"
fi

echo ""
echo "[5/5] Setup complete!"
echo ""
echo "======================================"
echo "Next Steps:"
echo "======================================"
echo ""
echo "Terminal 1 - Start Backend:"
echo "   cd backend"
echo "   python app_simple.py"
echo ""
echo "Terminal 2 - Start Frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "Then open your browser:"
echo "   http://localhost:3000 (Web Dashboard)"
echo "   http://localhost:8000/docs (API Docs)"
echo ""
echo "Demo Credentials: demo / demo"
echo ""
echo "======================================"
echo ""
