# INSTALLATION GUIDE - Zwesta Trading System v3

## ✅ System Requirements

- **Windows 10/11**, **macOS**, or **Linux**
- **Python 3.9+**
- **Node.js 16+**
- **npm 8+**
- **Git** (optional)

## 🚀 Installation Steps

### Step 1: Navigate to Project Directory

```bash
cd C:\zwesta-trader\zwesta-v3-advanced
```

### Step 2: Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
cd ..
```

### Step 3: Configure Backend (.env)

```bash
# Copy example config
copy backend\.env.example backend\.env

# Edit .env with your settings (optional for demo)
# Default demo mode works without changes
```

### Step 4: Initialize Database

```bash
cd backend
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ Database initialized')"
cd ..
```

### Step 5: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 6: Start Backend

```bash
cd backend
python main.py
```

Backend will start on: **http://localhost:8000**
API Docs on: **http://localhost:8000/docs**

### Step 7: Start Frontend (New Terminal)

```bash
cd frontend
npm run dev
```

Frontend will start on: **http://localhost:3001**

## 🎯 Quick Start

### One-Command Start (Windows)

```bash
start.bat
```

### One-Command Start (Linux/Mac)

```bash
bash start.sh
```

## 🔑 Default Credentials

```
Username: demo
Password: demo123
Email: demo@trading.com
```

## ✅ Verify Installation

1. **Backend Health Check:**
   ```
   GET http://localhost:8000/api/health
   ```
   Should return: `{"status": "ok", "timestamp": "..."}`

2. **Frontend Access:**
   - Open http://localhost:3001
   - Login with demo/demo123
   - Should see dashboard with charts

3. **API Documentation:**
   - Visit http://localhost:8000/docs
   - Should show Swagger UI with all endpoints

## 🔧 Configuration Options

### Backend Configuration (.env)

```ini
# Database
DATABASE_URL=sqlite:///./zwesta.db

# JWT Settings
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Twilio (WhatsApp Alerts)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=+14155238886

# Stripe (Payments)
STRIPE_API_KEY=your_stripe_key

# CORS Origins
CORS_ORIGINS=["http://localhost:3001", "http://localhost:8081"]

# Server Config
API_HOST=0.0.0.0
API_PORT=8000
```

### Frontend Configuration (src/api/client.ts)

Default: `http://localhost:8000/api`

## 🐛 Troubleshooting

### Python Module Not Found
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Port Already in Use
```bash
# Find and kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Or change backend port in config
```

### npm Dependencies Issue
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Database Lock Error
```bash
# Remove old database
cd backend
rm zwesta.db
python main.py
```

## 📊 Project Structure Verification

```
zwesta-v3-advanced/
✅ backend/
   ✅ main.py (FastAPI app with 30+ endpoints)
   ✅ config.py (Settings)
   ✅ database.py (Models & ORM)
   ✅ security.py (JWT & Auth)
   ✅ services.py (Business logic)
   ✅ requirements.txt
   ✅ .env.example
✅ frontend/
   ✅ src/
      ✅ pages/ (7 full pages)
      ✅ api/ (Axios client)
      ✅ store/ (State management)
   ✅ package.json
   ✅ vite.config.ts
   ✅ index.html
✅ README.md
✅ start.bat / start.sh
✅ docker-compose.yml
```

## 🚀 Next Steps

1. **Explore Dashboard:** Navigate through all pages
2. **Create Trading Account:** Test account management
3. **Create Trading Bot:** Set up automated trading strategy
4. **Monitor Market:** Check real-time crypto/forex prices
5. **View Reports:** Generate PDF reports
6. **Configure Integrations:**
   - Set up Stripe for real deposits
   - Configure Twilio for WhatsApp alerts
   - Connect Binance API for real trading

## 📱 Mobile App

Flutter mobile app is located in `mobile/` folder:

```bash
cd mobile
flutter pub get
flutter run  # For testing
flutter build apk --release  # For APK
```

## 🐳 Docker Deployment

```bash
docker-compose up -d
```

Runs on:
- Frontend: http://localhost:3001
- Backend: http://localhost:8000

## 📞 Support

- Check API docs: http://localhost:8000/docs
- Review README.md for detailed information
- Check terminal output for error messages

## ✅ Installation Complete!

Your Zwesta Trading System v3 is ready!

```
🚀 Dashboard: http://localhost:3001
🔌 API: http://localhost:8000
📚 Docs: http://localhost:8000/docs
👤 Demo: demo / demo123
```

Ready for:
✅ Trading
✅ Bot Management
✅ Crypto Monitoring
✅ Deposits/Withdrawals
✅ PDF Reports
✅ WhatsApp Alerts
