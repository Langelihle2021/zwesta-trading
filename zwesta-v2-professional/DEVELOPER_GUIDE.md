# Zwesta v2 - Developer Quick Reference

## 🚀 Quick Start (5 minutes)

```bash
# Terminal 1: Start Backend
cd C:\zwesta-trader\zwesta-v2-professional\backend
pip install -r requirements-minimal.txt
python app_simple.py

# Terminal 2: Start Frontend
cd C:\zwesta-trader\zwesta-v2-professional\frontend
npm install
npm run dev
```

**Access Points:**
- API Docs: http://localhost:8000/docs
- Backend Health: http://localhost:8000/api/health
- Frontend: http://localhost:3000
- Demo: username `demo` password `demo`

---

## 📁 File Locations

### Backend
- **Main App**: `backend/app/main.py`
- **Config**: `backend/app/config.py`
- **Models**: `backend/app/models.py`
- **Routes**: `backend/app/api/*.py` (6 modules)
- **Integrations**: `backend/app/integrations/*.py` (4 modules)
- **Bot**: `backend/app/bot/engine.py`
- **Auth Service**: `backend/app/services/auth.py`
- **Environment**: `backend/.env` (copy from `.env.example`)

### Frontend
- **Login**: `frontend/src/pages/LoginPage.tsx`
- **Dashboard**: `frontend/src/pages/DashboardPage.tsx`
- **API Client**: `frontend/src/api/client.ts`
- **State**: `frontend/src/store/store.ts`
- **Root**: `frontend/src/App.tsx`
- **Styles**: `frontend/src/index.css` + Tailwind config

---

## 🔗 API Endpoints

### Authentication
```
POST   /api/auth/login          - Login (returns token)
POST   /api/auth/signup         - Create user
POST   /api/auth/refresh        - Refresh token
GET    /api/auth/me             - Current user
POST   /api/auth/logout         - Logout
```

### Trading
```
GET    /api/trading/trades      - Get trades
GET    /api/trading/positions   - Get open positions
GET    /api/trading/symbols     - List symbols
GET    /api/trading/market-data/{symbol} - Market data
GET    /api/trading/statistics  - Trading stats
POST   /api/trading/trades      - Place order
POST   /api/trading/{id}/close  - Close position
```

### Accounts
```
GET    /api/accounts/           - List accounts
GET    /api/accounts/{id}       - Get account
POST   /api/accounts/{id}/deposits    - Deposit
POST   /api/accounts/{id}/withdrawals - Withdraw
GET    /api/accounts/{id}/deposits    - Deposit history
GET    /api/accounts/{id}/withdrawals - Withdrawal history
```

### Alerts
```
GET    /api/alerts/             - Get alerts
POST   /api/alerts/             - Create alert
PUT    /api/alerts/{id}         - Update alert
DELETE /api/alerts/{id}         - Delete alert
POST   /api/alerts/{id}/enable  - Enable
POST   /api/alerts/{id}/disable - Disable
```

### Reports
```
GET    /api/reports/            - Get reports
POST   /api/reports/generate    - Generate new
GET    /api/reports/{id}        - Get report
DELETE /api/reports/{id}        - Delete
```

### Admin
```
GET    /api/admin/users         - List users
GET    /api/admin/system-status - System status
POST   /api/admin/users/{id}/activate
POST   /api/admin/users/{id}/deactivate
POST   /api/admin/users/{id}/promote-admin
POST   /api/admin/users/{id}/demote-admin
```

### Health
```
GET    /api/health              - Health check
```

---

## 🔐 Authentication

### Login Flow
```typescript
// Frontend
const response = await authAPI.login({
  username: "trader1",
  password: "password123"
})
// Returns: { access_token: "jwt...", user: {...} }

// Store token
localStorage.setItem('access_token', response.access_token)

// API client automatically adds to headers:
// Authorization: Bearer {token}
```

### Protected Routes
```typescript
// Automatically redirects to /login if no token
<ProtectedRoute>
  <DashboardPage />
</ProtectedRoute>
```

---

## 💾 Database Models

### User
```python
id: int (PK)
username: str (unique)
email: str (unique)
password_hash: str
full_name: str
phone: str
whatsapp_number: str
is_active: bool
is_admin: bool
created_at: datetime
updated_at: datetime
```

### TradingAccount
```python
id: int (PK)
user_id: int (FK)
account_type: str (demo|live)
balance: Decimal(15,2)
equity: Decimal(15,2)
profit: Decimal(15,2)
margin_used: Decimal(15,2)
margin_free: Decimal(15,2)
margin_level: float
is_active: bool
created_at: datetime
updated_at: datetime
```

### Trade
```python
id: int (PK)
account_id: int (FK)
symbol: str
trade_type: str (BUY|SELL)
entry_price: Decimal(15,6)
exit_price: Decimal(15,6)
quantity: float
profit_loss: Decimal(15,2)
profit_loss_percent: float
commission: Decimal(15,4)
status: str (open|closed|pending)
opened_at: datetime
closed_at: datetime
```

### Position
```python
id: int (PK)
account_id: int (FK)
symbol: str
position_type: str (BUY|SELL)
entry_price: Decimal(15,6)
current_price: Decimal(15,6)
quantity: float
unrealized_profit: Decimal(15,2)
unrealized_profit_percent: float
stop_loss: Decimal(15,6)
take_profit: Decimal(15,6)
created_at: datetime
updated_at: datetime
```

---

## 🔧 Adding New Endpoints

### 1. Create Route Handler
```python
# File: backend/app/api/new_module.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db

router = APIRouter(prefix="/api/new", tags=["new"])

@router.get("/")
async def get_data(db: Session = Depends(get_db)):
    return {"data": "example"}
```

### 2. Mount in Main App
```python
# File: backend/app/main.py
from app.api import new_module

app.include_router(new_module.router)
```

### 3. Add to Frontend
```typescript
// File: frontend/src/api/client.ts
export const newAPI = {
  getData: () => apiClient.get('/new/'),
  // ... more methods
}

// Use in component
const data = await newAPI.getData()
```

---

## 📝 Adding New Database Models

### 1. Define Model
```python
# File: backend/app/models.py
from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.orm import relationship
from .database import Base

class MyModel(Base):
    __tablename__ = "my_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    value = Column(Float)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    user = relationship("User", back_populates="my_models")
```

### 2. Initialize Database
```python
# Runs automatically on app startup
from app.database import init_db
init_db()  # Creates all tables
```

---

## 🤖 Bot Integration

### How to Use MT5
```python
from app.integrations import MT5Provider

mt5 = MT5Provider(
    account_number="123456",
    password="password",
    server="XMGlobal-MT5"
)

# Connect
await mt5.connect()

# Get account info
info = await mt5.get_account_info()
print(info['balance'], info['equity'])

# Place order
result = await mt5.place_order(
    symbol="EURUSD",
    order_type="MARKET",
    trade_type="BUY",
    volume=1.0,
    entry_price=1.0850,
    stop_loss=1.0820,
    take_profit=1.0880
)

# Close position
await mt5.close_position(result['ticket'])
```

### How to Use Binance
```python
from app.integrations import BinanceProvider

binance = BinanceProvider(
    api_key="your-key",
    api_secret="your-secret",
    testnet=True
)

# Connect & verify
await binance.connect()

# Get market data
data = await binance.get_market_data("BTCUSDT")
print(data['price'], data['volume'])

# Place order
order = await binance.place_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    quantity=0.01,
    price=42000
)

# Get open orders
orders = await binance.get_open_orders("BTCUSDT")
```

### How to Send WhatsApp Alerts
```python
from app.integrations import WhatsAppAlertService

alerts = WhatsAppAlertService(
    account_sid="your-sid",
    auth_token="your-token",
    from_number="whatsapp:+1234567890"
)

# Send alert
await alerts.send_profit_alert(
    to_number="+1987654321",
    symbol="EURUSD",
    profit=100.50,
    profit_percent=2.5,
    trade_type="BUY",
    entry_price=1.0850,
    exit_price=1.0900
)

# Send daily report
await alerts.send_daily_report(
    to_number="+1987654321",
    trades_total=10,
    trades_winning=7,
    total_profit=500.25,
    win_rate=0.70,
    account_balance=10500
)
```

---

## 🎨 Frontend Components

### Login Page
```typescript
<LoginPage />
// Shows login form
// POST /api/auth/login
// Stores token in localStorage
// Redirects to /dashboard
```

### Dashboard Page
```typescript
<DashboardPage />
// Shows user greeting
// 4 stat cards (P&L, Win Rate, Trades, Positions)
// Profit/loss chart
// Win/loss pie chart
// Recent trades table
```

### How to Add New Page
```typescript
// 1. Create component
// frontend/src/pages/MyPage.tsx
export default function MyPage() {
  return <div>My Page</div>
}

// 2. Add route
// frontend/src/App.tsx
<Route path="/mypage" element={<MyPage />} />

// 3. Add login requirement (if needed)
<Route path="/mypage" element={
  <ProtectedRoute>
    <MyPage />
  </ProtectedRoute>
} />
```

---

## 📊 State Management (Zustand)

### Using Auth State
```typescript
import { useAuthStore } from '../store/store'

function MyComponent() {
  const { user, token, login, logout } = useAuthStore()
  
  // Login
  login(token, userData)
  
  // Logout
  logout()
  
  // Check if logged in
  if (user) {
    console.log(user.username)
  }
}
```

### Using Trading State
```typescript
import { useTradingStore } from '../store/store'

function TradesComponent() {
  const { trades, setTrades, statistics } = useTradingStore()
  
  // Update trades
  setTrades(newTradesArray)
  
  // Access stats
  console.log(statistics.win_rate)
}
```

---

## 🐛 Debugging

### Backend Logs
```bash
# Check for errors in terminal
# Look for: ERROR: ... lines

# Use print for debugging
print(f"Debug: {variable}")

# Check database
# File: test.db (SQLite)
```

### Frontend Logs
```bash
# Open browser console (F12)
# Chrome DevTools Network tab
# Check API responses

# Check API calls in Network tab:
# POST /api/auth/login
# GET /api/accounts/
# etc.
```

### Test API Endpoints
```bash
# Use Swagger UI at: http://localhost:8000/docs
# Or use curl:
curl -X GET http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo"}'
```

---

## 📦 Deployment

### Local Development
```bash
# Backend
cd backend
python app_simple.py

# Frontend
cd frontend
npm run dev
```

### Docker
```bash
# From root directory
docker-compose up --build

# Services:
# - API: http://localhost:8000
# - Frontend: http://localhost:3000
# - PostgreSQL: localhost:5432
```

### Production Build
```bash
# Frontend
cd frontend
npm run build
# Deploy dist/ to web server

# Backend
# Use docker-compose with PostgreSQL
# Configure .env with production values
```

---

## 🔗 Useful Links

- **API Docs**: http://localhost:8000/docs
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **GitHub**: (Your repo URL)
- **Issues**: (Your issues URL)

---

## 💡 Tips & Tricks

- **Auto-reload**: Both backend (Uvicorn) and frontend (Vite) have hot reload
- **Database**: SQLite for dev, switch to PostgreSQL in production
- **Tokens**: JWT tokens expire in 30 minutes, use refresh endpoint
- **CORS**: Already configured for localhost:3000
- **Errors**: Check browser console + terminal for full error messages

---

**Happy Coding! 🚀**
