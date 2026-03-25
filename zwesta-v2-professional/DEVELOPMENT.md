# Development Guide - Zwesta Trading System v2

Detailed guide for developers working on the Zwesta platform.

## Project Structure

```
zwesta-v2-professional/
├── backend/                    # FastAPI REST API
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app setup
│   │   ├── config.py          # Configuration (Pydantic)
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── models.py          # 8 ORM models
│   │   │
│   │   ├── api/               # API routes
│   │   │   ├── auth.py        # Login, signup, tokens
│   │   │   ├── trading.py     # Trades, positions
│   │   │   ├── accounts.py    # Account mgmt
│   │   │   ├── alerts.py      # Profit alerts
│   │   │   ├── reports.py     # PDF reports
│   │   │   └── admin.py       # User management
│   │   │
│   │   ├── services/          # Business logic
│   │   │   └── auth.py        # JWT, password hashing
│   │   │
│   │   └── bot/               # Trading bot
│   │       └── engine.py      # Async market scanner
│   │
│   ├── tests/                 # (To be created)
│   │   ├── test_api.py
│   │   ├── test_models.py
│   │   └── test_bot.py
│   │
│   ├── requirements.txt        # Dependencies
│   ├── .env.example           # Config template
│   └── README.md              # Backend docs
│
├── frontend/                   # React web app (To create)
│   ├── public/
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── services/          # API clients
│   │   ├── context/           # State management
│   │   ├── hooks/             # Custom hooks
│   │   └── App.js
│   ├── package.json
│   └── README.md
│
├── mobile/                     # React Native app (To create)
│   ├── src/
│   │   ├── screens/
│   │   ├── navigation/
│   │   ├── components/
│   │   └── services/
│   ├── package.json
│   └── README.md
│
├── Dockerfile                 # Backend container
├── docker-compose.yml         # Service orchestration
└── README.md                  # Main documentation
```

## Backend Development

### Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# Edit configuration
nano .env
```

### Database Initialization

```bash
# Create tables from models
python -c "from app.database import init_db; init_db()"

# Or manually with PostgreSQL
psql -U postgres
CREATE DATABASE zwesta_db;
\q
```

### Running the Server

```bash
# Development (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

### Making Code Changes

1. **Adding a new model** (e.g., `Transaction`):
   - Add class to `app/models.py`
   - Run `python -c "from app.database import init_db; init_db()"` to create table
   - Create API routes in `app/api/`

2. **Adding a new API route**:
   - Create function in `app/api/trading.py` (or new file)
   - Use Pydantic for request/response models
   - Use `Depends(get_db)` for database access
   - Test with Swagger UI at `/docs`

3. **Adding business logic**:
   - Create service class in `app/services/`
   - Import and use in API routes
   - Keep logic separate from HTTP layer

### API Development Example

```python
# app/api/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models import MyModel

router = APIRouter()

class MyRequest(BaseModel):
    name: str
    value: float

class MyResponse(BaseModel):
    id: int
    name: str
    value: float
    
    class Config:
        from_attributes = True

@router.get("/items", response_model=list[MyResponse])
async def get_items(db: Session = Depends(get_db)):
    items = db.query(MyModel).all()
    return items

@router.post("/items", response_model=MyResponse)
async def create_item(req: MyRequest, db: Session = Depends(get_db)):
    item = MyModel(name=req.name, value=req.value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

Then include in `app/main.py`:
```python
from app.api import example
app.include_router(example.router, prefix="/api/items", tags=["Items"])
```

### Testing

```bash
# Install pytest
pip install pytest pytest-asyncio httpx

# Write tests (example)
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200

def test_login():
    response = client.post(
        "/api/auth/login",
        json={"username": "demo", "password": "password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

# Run tests
pytest tests/
pytest -v tests/  # Verbose
pytest --cov=app tests/  # With coverage
```

## Database Operations

### Using SQLAlchemy

```python
from sqlalchemy.orm import Session
from app.models import Trade

# Query
trades = db.query(Trade).filter(Trade.symbol == "EURUSD").all()
trade = db.query(Trade).filter(Trade.id == 1).first()

# Count
count = db.query(Trade).count()

# Create
trade = Trade(symbol="EURUSD", trade_type="BUY", ...)
db.add(trade)
db.commit()
db.refresh(trade)

# Update
trade = db.query(Trade).filter(Trade.id == 1).first()
trade.profit_loss = 100
db.commit()

# Delete
trade = db.query(Trade).filter(Trade.id == 1).first()
db.delete(trade)
db.commit()

# Filter with multiple conditions
trades = db.query(Trade).filter(
    Trade.symbol == "EURUSD",
    Trade.status == "closed"
).all()

# Order and limit
trades = db.query(Trade).order_by(Trade.closed_at.desc()).limit(10).all()

# Join
from app.models import TradingAccount
trades = db.query(Trade).join(TradingAccount).filter(
    TradingAccount.user_id == 1
).all()
```

## Integrations (To Implement)

### MT5 Integration
```python
# backend/app/integrations/mt5.py
import MetaTrader5 as mt5

class MT5Provider:
    def __init__(self, account, password, server):
        self.account = account
        self.password = password
        self.server = server
    
    def connect(self):
        if not mt5.initialize():
            return False
        return mt5.login(self.account, self.password, self.server)
    
    def get_account_info(self):
        info = mt5.account_info()
        return {
            "balance": info.balance,
            "equity": info.equity,
            "profit": info.profit
        }
```

### Binance Integration
```python
# backend/app/integrations/binance.py
from binance.client import Client

class BinanceProvider:
    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
    
    def get_price(self, symbol):
        ticker = self.client.get_symbol_info(symbol)
        return float(ticker['price'])
    
    def create_order(self, symbol, side, quantity, price):
        order = self.client.create_limit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price
        )
        return order
```

### WhatsApp Alerts
```python
# backend/app/integrations/whatsapp.py
from twilio.rest import Client

class WhatsAppService:
    def __init__(self, account_sid, auth_token, from_number):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
    
    def send_alert(self, to_number, message):
        self.client.messages.create(
            from_=f"whatsapp:{self.from_number}",
            to=f"whatsapp:{to_number}",
            body=message
        )
```

## Docker Development

### Building Image

```bash
# From project root
docker build -t zwesta-api .

# Run container
docker run -p 8000:8000 --env-file .env zwesta-api

# Or use docker-compose
docker-compose up --build
```

### Debugging Container

```bash
# Access container shell
docker exec -it zwesta-api /bin/bash

# View logs
docker logs zwesta-api
docker logs -f zwesta-api  # Follow logs

# Run command in container
docker exec zwesta-api python -c "from app.database import init_db; init_db()"
```

## Frontend Development (Coming Next)

```bash
cd frontend

# Initialize React app
npx create-react-app .

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
```

Key packages to install:
```bash
npm install axios redux react-router-dom chart.js recharts
```

## Testing Checklist

Before committing code:

- [ ] Code runs without errors
- [ ] Tests pass: `pytest`
- [ ] Linting passes: `flake8 app/`
- [ ] Type checking passes: `mypy app/`
- [ ] Format with Black: `black app/`
- [ ] API endpoints work in Swagger UI
- [ ] Database queries execute correctly
- [ ] No debug print statements left
- [ ] Commit message is clear and descriptive

## Common Commands

```bash
# Backend commands
python -m venv venv                          # Create venv
source venv/bin/activate                    # Activate (Linux/Mac)
venv\Scripts\activate                       # Activate (Windows)
pip install -r requirements.txt             # Install deps
python -c "from app.database import init_db; init_db()"  # Init DB
uvicorn app.main:app --reload               # Run dev server
pytest                                       # Run tests
black app/                                  # Format code
flake8 app/                                 # Lint code
mypy app/                                   # Type checking

# Database
psql -U postgres                            # Connect to PostgreSQL
\l                                          # List databases
\d                                          # List tables
\q                                          # Quit

# Docker
docker-compose up --build                   # Start services
docker-compose down                         # Stop services
docker-compose logs -f api                  # View logs
docker exec -it zwesta-api bash             # Shell into container
```

## Performance & Optimization

1. **Database Queries**
   - Use `.all()` or `.first()` carefully - gets all rows
   - Use `.count()` for counting instead of `.all()`
   - Add `.limit()` to large queries
   - Use indexes on frequently filtered columns

2. **Async/Await**
   - Use async functions for I/O operations
   - Avoid blocking operations in async functions
   - Used ThreadPoolExecutor for CPU-bound tasks

3. **Caching**
   - Add Redis for session/cache storage
   - Cache expensive database queries
   - Use HTTP caching headers

4. **API Optimization**
   - Paginate large result sets
   - Use SELECT specific columns, not `*`
   - Compress responses
   - Use proper HTTP status codes

## Debugging Tips

```python
# Add debug prints
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Variable value: {var}")

# Use debugger
import pdb; pdb.set_trace()

# In async code
import asyncio
asyncio.run(debug_async_function())

# Database debugging
from sqlalchemy import event
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    print(f"SQL: {statement}")
```

## Next Steps

1. **Implement integrations** - MT5, Binance, Twilio
2. **Complete trading bot** - Add signal logic
3. **Start frontend** - React web app
4. **Add tests** - Unit & integration tests
5. **Production hardening** - Security, monitoring

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)
- [React Documentation](https://react.dev/)

## Support

For issues while developing:
1. Check the error message carefully
2. Search the FastAPI/SQLAlchemy docs
3. Check existing code patterns in repo
4. Add print statements / use debugger
5. Check API docs at `http://localhost:8000/docs`

Good luck with development! 🚀
