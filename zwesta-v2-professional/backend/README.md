# Zwesta Trading System v2 - Backend API

FastAPI-based professional trading platform backend with real-time market data, MT5 integration, Binance support, and automated trading bot.

## Architecture

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py              # Configuration management
│   ├── database.py            # SQLAlchemy setup
│   ├── models.py              # Database ORM models
│   │
│   ├── api/                   # API routes
│   │   ├── __init__.py
│   │   ├── auth.py           # Authentication routes (login, signup, token)
│   │   ├── trading.py        # Trading routes (trades, positions, symbols)
│   │   ├── accounts.py       # Account management (deposits, withdrawals)
│   │   ├── alerts.py         # Profit/loss alerts
│   │   ├── reports.py        # Report generation & history
│   │   └── admin.py          # Admin routes
│   │
│   ├── services/             # Business logic services
│   │   ├── __init__.py
│   │   └── auth.py          # JWT, password hashing, user management
│   │
│   ├── bot/                   # Trading bot engine
│   │   ├── __init__.py
│   │   └── engine.py         # Async market scanning & trade execution
│   │
│   └── integrations/          # (To be created) External API integrations
│       ├── mt5.py            # MetaTrader 5 integration
│       ├── binance.py        # Binance API integration
│       ├── whatsapp.py       # Twilio WhatsApp notifications
│       └── pdf_reports.py    # PDF report generation
│
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Quick Start

### 1. Prerequisites
- Python 3.9+
- PostgreSQL database
- pip/poetry for dependency management

### 2. Setup Environment

```bash
# Clone and navigate
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Database

```bash
# Create PostgreSQL database
# psql -U postgres
# CREATE DATABASE zwesta_db;

# Run migrations (Alembic - to be setup)
# alembic upgrade head

# Or auto-create tables from models
python -c "from app.database import init_db; init_db()"
```

### 5. Run Server

```bash
# Development with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Server will be available at: `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Authentication (`/api/auth/`)
- `POST /login` - Login with credentials → JWT tokens
- `POST /signup` - Register new user
- `POST /refresh` - Refresh access token
- `GET /me` - Get current user info
- `POST /logout` - Logout

### Trading (`/api/trading/`)
- `GET /trades` - Get account trades (filters: symbol, status)
- `GET /positions` - Get open positions
- `POST /trades` - Create new trade
- `POST /trades/{id}/close` - Close position
- `GET /symbols` - Get tradeable symbols
- `GET /market-data/{symbol}` - Get current market price
- `GET /statistics` - Get account trading stats

### Accounts (`/api/accounts/`)
- `GET /` - Get user accounts
- `GET /{id}` - Get account details
- `POST /{id}/deposits` - Create deposit request
- `POST /{id}/withdrawals` - Create withdrawal request
- `GET /{id}/deposits` - Deposit history
- `GET /{id}/withdrawals` - Withdrawal history

### Alerts (`/api/alerts/`)
- `GET /` - Get user alerts
- `POST /` - Create alert
- `PUT /{id}` - Update alert
- `DELETE /{id}` - Delete alert
- `POST /{id}/enable` - Enable alert
- `POST /{id}/disable` - Disable alert

### Reports (`/api/reports/`)
- `GET /` - Get account reports
- `POST /generate` - Generate new report
- `GET /{id}` - Get report details
- `GET /{id}/download` - Download PDF report
- `DELETE /{id}` - Delete report

### Admin (`/api/admin/`)
- `GET /users` - List all users
- `GET /system-status` - System health status
- `POST /users/{id}/activate` - Activate user
- `POST /users/{id}/deactivate` - Deactivate user
- `POST /users/{id}/promote-admin` - Make admin
- `POST /users/{id}/demote-admin` - Remove admin

## Database Schema

### Core Models
- **User** - User accounts with authentication
- **TradingAccount** - Trading accounts (demo/live)
- **Trade** - Executed trades (open/closed)
- **Position** - Open trading positions
- **MT5Credential** - MT5 terminal credentials storage
- **ProfitAlert** - Profit/loss alert configurations
- **Deposit/Withdrawal** - Transaction history
- **Report** - Generated trading reports

## Key Features

✅ **JWT Authentication** - Token-based with refresh tokens  
✅ **Real-time Trading Bot** - Async market scanner every 5 seconds  
✅ **MT5 Integration** - Live trading terminal connection  
✅ **Binance Support** - Cryptocurrency trading  
✅ **WhatsApp Alerts** - Profit notifications via Twilio  
✅ **PDF Reports** - Auto-generated trading reports  
✅ **Account Management** - Deposits, withdrawals, multiple accounts  
✅ **Trading Statistics** - Win rate, profit tracking  
✅ **Role-based Admin** - User & system management  

## Configuration

Edit `.env` file to configure:
- Database connection
- JWT secret key
- MT5 credentials
- Binance API keys
- Twilio WhatsApp settings
- Email/SMTP settings
- CORS allowed origins

## Integrations (To Be Implemented)

### `/app/integrations/mt5.py`
- MetaTrader 5 terminal connection
- Account info, positions, order execution
- Historical data retrieval

### `/app/integrations/binance.py`
- Binance REST API client
- Real-time price feeds
- Order placement and management

### `/app/integrations/whatsapp.py`
- Twilio SMS/WhatsApp API
- Profit alert notifications
- Custom alerts and messages

### `/app/integrations/pdf_reports.py`
- ReportLab or WeasyPrint PDF generation
- Trade history, statistics, graphs
- Monthly/quarterly/custom reports

## Development

### Testing
```bash
pytest tests/
# With coverage
pytest --cov=app tests/
```

### Code Quality
```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

### Database Migrations (Alembic)
```bash
# Create migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Deployment

### Docker
```bash
# Build image
docker build -t zwesta-trading-api .

# Run container
docker run -p 8000:8000 --env-file .env zwesta-trading-api
```

### Production Checklist
- [ ] Change SECRET_KEY in .env
- [ ] Set DEBUG=False
- [ ] Configure PostgreSQL with strong password
- [ ] Setup HTTPS/SSL
- [ ] Configure CORS with actual frontend domain
- [ ] Setup monitoring and logging
- [ ] Configure rate limiting
- [ ] Setup backups for database
- [ ] Test authentication flow
- [ ] Load test bot trading logic

## Troubleshooting

### Database Connection Error
```
Check DATABASE_URL in .env
Ensure PostgreSQL is running
Verify credentials and permissions
```

### MT5 Connection Failed
```
Check MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER in .env
Ensure MetaTrader 5 terminal is running
Check firewall settings
```

### Bot Not Scanning
```
Check logs for startup errors
Verify database is initialized
Check bot_engine.py error handling
Bot status: /api/health endpoint
```

## Support & Documentation

- FastAPI Docs: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Pydantic: https://pydantic-settings.readthedocs.io/

## License

Proprietary - Zwesta Trading System
