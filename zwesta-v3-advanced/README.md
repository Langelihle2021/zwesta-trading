# Zwesta Trading System v3 - Advanced

**Complete Enterprise Trading Platform with Bot Interface, Crypto Monitoring, Payments, and WhatsApp Alerts**

## 🎯 Features

### ✅ Authentication & Security
- User registration & login with JWT tokens
- Secure password hashing with bcrypt
- Refresh token support
- Session management

### ✅ Account Management
- Multiple trading accounts support
- Account balances & equity tracking
- Margin level monitoring
- Demo & Live account types

### ✅ Trading Bots
- Create automated trading strategies
- Scalping, Swing Trading, Trend Following, Mean Reversion strategies
- Risk management (stop loss, take profit)
- Start/stop bot controls
- Real-time bot status monitoring

### ✅ Crypto & Forex Monitoring
- Real-time price feeds (BTC, ETH, BNB, EURUSD, GBPUSD, etc.)
- 24h change tracking
- Live market dashboard
- Price alerts

### ✅ Trading Management
- Trade history with P&L tracking
- Open positions monitoring
- Trading statistics (win rate, profit factor)
- Performance analytics

### ✅ Financial Operations
- Deposit functionality with Stripe integration
- Withdrawal requests with bank account management
- Balance tracking
- Transaction history

### ✅ Alerts & Notifications
- Price alerts
- P&L alerts
- Margin alerts
- **WhatsApp notifications via Twilio**

### ✅ Reports & Analytics
- PDF report generation (ReportLab)
- Performance analysis
- Trade history reports
- Custom date ranges
- Downloadable monthly reports

### ✅ User Experience
- Modern responsive UI (React + Vite)
- Real-time charts with Recharts
- Dark gradient theme
- Mobile-friendly design
- Smooth animations

## 📁 Project Structure

```
zwesta-v3-advanced/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration & settings
│   ├── database.py             # SQLAlchemy models & DB setup
│   ├── security.py             # JWT & password utilities
│   ├── services.py             # Business logic (crypto, alerts, payments, reports)
│   ├── requirements.txt         # Python dependencies
│   └── .env.example            # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main app component
│   │   ├── main.tsx            # Entry point
│   │   ├── App.css             # Global styles
│   │   ├── api/
│   │   │   └── client.ts       # API client (Axios)
│   │   ├── store/
│   │   │   └── store.ts        # State management (Zustand)
│   │   └── pages/
│   │       ├── LoginPage.tsx           # Login form
│   │       ├── DashboardPage.tsx       # Main dashboard with charts
│   │       ├── BotManagementPage.tsx   # Bot creation & management
│   │       ├── AccountManagementPage.tsx  # Account management
│   │       ├── MarketMonitorPage.tsx   # Real-time market prices
│   │       ├── DepositPage.tsx         # Deposit functionality
│   │       ├── WithdrawalPage.tsx      # Withdrawal form
│   │       ├── ReportsPage.tsx         # Report generation
│   │       └── ProfilePage.tsx         # User profile
│   ├── vite.config.ts          # Vite configuration
│   ├── tsconfig.json           # TypeScript config
│   ├── package.json            # Node dependencies
│   └── index.html              # HTML entry point
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- npm or yarn

### Installation & Startup

#### Option 1: Automatic (Windows)
```bash
cd C:\zwesta-trader\zwesta-v3-advanced
start.bat
```

#### Option 2: Automatic (Linux/Mac)
```bash
cd ~/zwesta-v3-advanced
chmod +x start.sh
./start.sh
```

#### Option 3: Manual Startup

**Terminal 1 - Backend:**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Access the Application
- **Web Dashboard:** http://localhost:3001
- **API Docs:** http://localhost:8000/docs
- **API Base:** http://localhost:8000/api

### Demo Login
```
Username: demo
Password: demo123
```

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user

### Accounts
- `POST /api/accounts` - Create account
- `GET /api/accounts` - List accounts
- `GET /api/accounts/{id}` - Get account details

### Trading Bots
- `POST /api/bots?account_id=X` - Create bot
- `GET /api/bots/{account_id}` - List bots
- `POST /api/bots/{bot_id}/start` - Start bot
- `POST /api/bots/{bot_id}/stop` - Stop bot

### Trading Data
- `GET /api/positions/{account_id}` - Open positions
- `GET /api/trades/{account_id}` - Trade history
- `GET /api/statistics/{account_id}` - Trading stats

### Market Data
- `GET /api/market/price/{symbol}` - Get single price
- `GET /api/market/prices?symbols=BTC,ETH,EURUSD` - Get multiple prices

### Financial Operations
- `POST /api/deposits?account_id=X` - Create deposit
- `POST /api/withdrawals?account_id=X` - Create withdrawal

### Alerts & Reports
- `GET /api/alerts/{account_id}` - Get alerts
- `GET /api/reports/{account_id}` - Download PDF report

## 🛠️ Configuration

### Backend (.env)
```env
# Database
DATABASE_URL=sqlite:///./zwesta.db

# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=+14155238886

# Stripe (Payments)
STRIPE_API_KEY=your_stripe_key

# Binance (Crypto)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# CORS
CORS_ORIGINS=["http://localhost:3001", "http://localhost:8081"]
```

### Frontend (vite.config.ts)
```typescript
// API URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
```

## 📚 Technology Stack

### Backend
- **Framework:** FastAPI
- **Server:** Uvicorn
- **Database:** SQLAlchemy (SQLite/PostgreSQL)
- **Auth:** JWT + Bcrypt
- **Crypto:** Binance API, CoinGecko API
- **Payments:** Stripe
- **SMS/WhatsApp:** Twilio
- **PDF Reports:** ReportLab
- **Task Scheduler:** APScheduler

### Frontend
- **Framework:** React 18
- **Build Tool:** Vite
- **State:** Zustand
- **HTTP:** Axios
- **Charts:** Recharts
- **Icons:** Lucide React
- **Styling:** CSS3 with Gradients

### Mobile
- **Framework:** Flutter (ready to build)
- **Backend Integration:** REST APIs

## 🚀 Deployment

### Docker
```bash
docker-compose up -d
```

### VPS (AWS, DigitalOcean, Linode)
```bash
# Install dependencies
sudo apt update && sudo apt install python3-pip nodejs npm -y

# Clone/upload project
git clone <repo-url>
cd zwesta-v3-advanced

# Setup backend
cd backend
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:8000 main:app &

# Setup frontend
cd ../frontend
npm install
npm run build
serve -s dist -l 3001 &
```

### Heroku
```bash
heroku create zwesta-trading-v3
git push heroku main
heroku config:set ENVIRONMENT=production
```

## 🔐 Security Features

✅ JWT Authentication
✅ Password Hashing (bcrypt)
✅ CORS Enabled
✅ SQL Injection Protection (SQLAlchemy ORM)
✅ XSS Protection (React)
✅ Secure Headers
✅ HTTPS Ready
✅ Rate Limiting Ready

## 📱 Mobile App

Flutter mobile app is ready to build:
```bash
cd mobile
flutter pub get
flutter build apk --release
```

Features:
- Same authentication as web
- Real-time price feeds
- Trading bot management
- Account monitoring
- Deposit/withdrawal
- Push notifications

## 📊 Demo Data

The system comes with realistic demo data:
- **Trading Statistics:** Win rate 72%, Profit factor 2.41
- **Sample Trades:** GBPUSD, EURUSD with actual P&L
- **Account Balance:** $10,000 starting balance
- **Real Prices:** Live crypto & forex feeds

## 🐛 Troubleshooting

### Backend won't start
```bash
# Clear database
rm -f zwesta.db
# Reinstall dependencies
pip install --upgrade -r requirements.txt
# Check port 8000 is free
lsof -i :8000
```

### Frontend won't load
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### CORS errors
- Ensure `CORS_ORIGINS` in `.env` includes your frontend URL
- Check API response headers

### WhatsApp alerts not working
- Configure Twilio credentials in `.env`
- Verify phone numbers in E.164 format

## 📈 Growth Roadmap

- [ ] Live broker integration (XM, FXCM)
- [ ] Advanced charting (TradingView)
- [ ] WebSocket real-time updates
- [ ] Mobile app (Flutter build)
- [ ] Social trading features
- [ ] Copy trading
- [ ] Risk analytics dashboard
- [ ] Machine learning strategies
- [ ] Multi-language support

## 📞 Support

For issues or feature requests, please contact the development team.

## 📄 License

Proprietary - Zwesta Trading System v3

---

**Version:** 3.0.0  
**Last Updated:** March 2, 2026  
**Status:** ✅ Production Ready
