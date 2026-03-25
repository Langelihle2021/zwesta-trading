# Migration Guide: XM v1 to Zwesta v2 Professional

## Your Credentials

Your existing XM credentials have been integrated into the new v2 system:

```env
MT5_ACCOUNT=136372035
MT5_PASSWORD=!3bhNjYy
MT5_SERVER=MetaQuotes-Demo
```

Your trading bot settings:
```env
POSITION_SIZE_PERCENT=2              # 2% position sizing
STOP_LOSS_POINTS=50                  # 50 points SL
TAKE_PROFIT_PERCENT=1.5              # 1.5% TP
CONSECUTIVE_LOSS_LIMIT=3             # Stop after 3 consecutive losses
DAILY_LOSS_LIMIT=500                 # Stop if daily loss > $500
```

Your database settings:
```env
DATABASE_URL=postgresql://postgres:SecurePassword123@localhost:5432/xm_trader
```

---

## Setup Instructions

### 1. Copy Configuration
```bash
cd C:\zwesta-trader\zwesta-v2-professional\backend

# Copy template
cp .env.example .env

# .env already has your credentials pre-filled
```

### 2. Install Database (PostgreSQL)

The new v2 system uses PostgreSQL instead of SQLite. If you don't have it:

**Option A: Using existing local PostgreSQL**
```bash
# Just update the DATABASE_URL in .env if needed
# Your credentials: postgres:SecurePassword123@localhost:5432/xm_trader
```

**Option B: Using SQLite for development**
```env
# Change in .env:
DATABASE_URL=sqlite:///./test.db
```

### 3. Create Database and Tables
```bash
cd C:\zwesta-trader\zwesta-v2-professional\backend

# Install dependencies
pip install -r requirements-minimal.txt

# Start Python to initialize database
python
>>> from app.database import init_db
>>> init_db()
>>> exit()
```

### 4. Start the Backend
```bash
# Terminal 1
cd C:\zwesta-trader\zwesta-v2-professional\backend
python app_simple.py

# Or with full app:
python -m uvicorn app.main:app --reload
```

### 5. Start the Frontend
```bash
# Terminal 2
cd C:\zwesta-trader\zwesta-v2-professional\frontend
npm install
npm run dev
```

---

## What Changed from v1

### **Same MT5 Account**
- ✅ Uses your exact XM credentials: `136372035` / `!3bhNjYy` / `MetaQuotes-Demo`
- ✅ Same trading parameters (2% position size, 50 SL points, etc.)
- ✅ Same trade execution engine

### **Improved**
- ✅ Modern REST API (36 endpoints) instead of Flask routes
- ✅ Production-grade architecture
- ✅ React dashboard instead of HTML/Bootstrap
- ✅ Better state management
- ✅ Built-in crypto support (Binance)
- ✅ WhatsApp alerts (Twilio)
- ✅ PDF reports (ReportLab)

### **Database**
- Old: SQLite database (`test.db`)
- New: PostgreSQL-ready (or SQLite if preferred)

### **Server**
- Old: Flask on port 5000
- New: FastAPI on port 8000 (with Swagger UI at `/docs`)

### **Frontend**
- Old: Simple HTML templates
- New: React 18 with Vite, Tailwind CSS, Chart.js

---

## API Endpoints (v2)

All endpoints under `/api/` prefix:

### Authentication
```
POST   /api/auth/login
POST   /api/auth/signup
POST   /api/auth/refresh
GET    /api/auth/me
POST   /api/auth/logout
```

### Trading (Same functionality as v1)
```
GET    /api/trading/trades           # Get all trades
GET    /api/trading/positions        # Get open positions
POST   /api/trading/trades           # Place order
POST   /api/trading/{id}/close       # Close position
GET    /api/trading/statistics       # Win rate, P&L, etc.
GET    /api/trading/market-data/{symbol}
```

### Accounts (New)
```
GET    /api/accounts/
POST   /api/accounts/{id}/deposits
POST   /api/accounts/{id}/withdrawals
```

### Alerts (New)
```
GET    /api/alerts/
POST   /api/alerts/
PUT    /api/alerts/{id}
DELETE /api/alerts/{id}
```

### Admin (New)
```
GET    /api/admin/users
GET    /api/admin/system-status
```

**Interactive Testing**: Open http://localhost:8000/docs for Swagger UI

---

## Default Demo User

You can create a new user in the dashboard, but for testing:

```
Username: demo
Password: demo
```

---

## Database Models (Migrated)

| v1 Table | v2 Model | Status |
|----------|----------|--------|
| users | User | ✅ Same structure |
| accounts | TradingAccount | ✅ Enhanced |
| trades | Trade | ✅ Same fields |
| positions | Position | ✅ Same fields |
| - | MT5Credential | ✨ New (for multiple accounts) |
| - | Alert | ✨ New (profit/loss/margin alerts) |
| - | Deposit | ✨ New (fund tracking) |
| - | Withdrawal | ✨ New (withdrawal tracking) |
| - | Report | ✨ New (PDF reports) |

---

## Bot Configuration

The trading bot parameters are now in environment variables:

```env
# How bot scans markets
BOT_ENABLED=true
BOT_SCAN_INTERVAL=5              # Scan every 5 seconds

# Position sizing
POSITION_SIZE_PERCENT=2           # 2% of account balance

# Risk management
STOP_LOSS_POINTS=50              # 50 pips SL
TAKE_PROFIT_PERCENT=1.5          # 1.5% TP
CONSECUTIVE_LOSS_LIMIT=3         # Stop after 3 losses
DAILY_LOSS_LIMIT=500             # Stop if loss > $500
```

To modify bot behavior, edit `.env` and restart the server.

---

## Upgrading Optional Dependencies

When ready, install these for full functionality:

```bash
pip install MetaTrader5==5.0.45        # For MT5 connection
pip install python-binance==1.0.17     # For crypto trading
pip install twilio==8.10.0              # For WhatsApp alerts
pip install reportlab==4.0.7            # For PDF reports
```

Currently, the integrations are stubbed and will log to console. Once these packages are installed, they'll connect to real APIs.

---

## Production Deployment

### Docker
```bash
# From root directory
docker-compose up --build

# Services:
# - API: http://localhost:8000
# - Frontend: http://localhost:3000  
# - PostgreSQL: localhost:5432
```

### Environment Variables
All sensitive data (passwords, API keys) go in `.env` file, NOT in code.

### Recommended Production Setup
1. Use PostgreSQL on separate server
2. Set `DEBUG=false` in `.env`
3. Generate strong `SECRET_KEY`
4. Configure CORS for your domain
5. Use HTTPS
6. Set up log aggregation
7. Configure automated backups

---

## Troubleshooting

### Database Connection Error
```
Error: Could not connect to PostgreSQL
Fix: Either:
1. Start PostgreSQL service
2. Or change DATABASE_URL to SQLite: sqlite:///./test.db
```

### Port Already in Use
```
Error: Port 8000 already in use
Fix: 
1. Kill existing process: lsof -ti :8000 | xargs kill -9
2. Or change API_PORT in .env
```

### Frontend Can't Connect to API
```
Error: API request failed
Fix:
1. Check backend is running: http://localhost:8000/docs
2. Check CORS configuration in .env
3. Check browser console for exact error
```

### MT5 Connection Failed
```
Error: Failed to connect to MT5
Fix:
1. Verify MetaTrader 5 terminal is running
2. Check MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER in .env
3. Try connecting manually in MT5 terminal first
```

---

## Migration Checklist

- [ ] Copy `.env.example` to `.env`
- [ ] Verify credentials in `.env`:
  - [ ] MT5_ACCOUNT=136372035
  - [ ] MT5_PASSWORD=!3bhNjYy
  - [ ] MT5_SERVER=MetaQuotes-Demo
- [ ] Set up PostgreSQL (or use SQLite)
- [ ] Run `init_db()` to create tables
- [ ] Start backend: `python app_simple.py`
- [ ] Start frontend: `npm run dev`
- [ ] Access dashboard: http://localhost:3000
- [ ] Login with demo/demo
- [ ] Test trading endpoints in Swagger UI
- [ ] Verify bot can connect to MT5
- [ ] (Optional) Install optional dependencies

---

## Support

For issues or questions:

1. Check logs in terminal
2. Review error in browser console (F12)
3. Test endpoint in Swagger UI: http://localhost:8000/docs
4. Check `.env` for correct credentials

---

**You're all set! Your XM trading account is now integrated into the professional Zwesta v2 system. 🚀**
