from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import json
import uvicorn

from config import get_settings
from database import get_db, User, Account, Bot, Position, Trade, Alert, Deposit, Withdrawal
from security import hash_password, verify_password, create_access_token, create_refresh_token, get_current_user
from services import CryptoService, AlertService, ReportService, PaymentService, BotService

# ===== Initialize App =====
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0",
    docs_url="/api/docs"
)

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Pydantic Models =====
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    phone: Optional[str]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse

class CreateAccount(BaseModel):
    name: str
    broker: str
    account_number: str
    api_key: Optional[str]
    api_secret: Optional[str]

class AccountResponse(BaseModel):
    id: int
    name: str
    broker: str
    balance: float
    equity: float
    margin_used: float
    is_demo: bool
    is_active: bool

class CreateBot(BaseModel):
    name: str
    strategy: str
    symbol: str
    risk_percent: float = 2.0
    tp_percent: float = 2.0
    sl_percent: float = 1.0

class BotResponse(BaseModel):
    id: int
    name: str
    strategy: str
    symbol: str
    is_active: bool

class DepositRequest(BaseModel):
    amount: float
    card_token: Optional[str] = None

class WithdrawalRequest(BaseModel):
    amount: float
    bank_account: str

# ===== Authentication Endpoints =====
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user: UserRegister, db: Session = Depends(get_db)):
    """Register new user"""
    # Check if user exists
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create user
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
        full_name=user.full_name,
        phone=user.phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token = create_access_token({"sub": db_user.id})
    refresh_token = create_refresh_token({"sub": db_user.id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "phone": db_user.phone
        }
    }

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone
        }
    }

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user info"""
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone
    }

# ===== Account Management Endpoints =====
@app.post("/api/accounts", response_model=AccountResponse)
async def create_account(account: CreateAccount, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create new trading account"""
    db_account = Account(
        user_id=current_user["user_id"],
        name=account.name,
        broker=account.broker,
        account_number=account.account_number,
        api_key=account.api_key,
        api_secret=account.api_secret,
        balance=10000.0,
        equity=10000.0
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    
    return {
        "id": db_account.id,
        "name": db_account.name,
        "broker": db_account.broker,
        "balance": db_account.balance,
        "equity": db_account.equity,
        "margin_used": db_account.margin_used,
        "is_demo": db_account.is_demo,
        "is_active": db_account.is_active
    }

@app.get("/api/accounts", response_model=List[AccountResponse])
async def get_accounts(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all user accounts"""
    accounts = db.query(Account).filter(Account.user_id == current_user["user_id"]).all()
    return [
        {
            "id": acc.id,
            "name": acc.name,
            "broker": acc.broker,
            "balance": acc.balance,
            "equity": acc.equity,
            "margin_used": acc.margin_used,
            "is_demo": acc.is_demo,
            "is_active": acc.is_active
        }
        for acc in accounts
    ]

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get account details"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {
        "id": account.id,
        "name": account.name,
        "broker": account.broker,
        "account_number": account.account_number,
        "balance": account.balance,
        "equity": account.equity,
        "margin_used": account.margin_used,
        "margin_level": account.margin_level,
        "is_demo": account.is_demo,
        "is_active": account.is_active,
        "created_at": account.created_at.isoformat()
    }

# ===== Bot Management Endpoints =====
@app.post("/api/bots", response_model=BotResponse)
async def create_bot(bot: CreateBot, account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create trading bot"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    db_bot = Bot(
        account_id=account_id,
        name=bot.name,
        strategy=bot.strategy,
        symbol=bot.symbol,
        risk_percent=bot.risk_percent,
        tp_percent=bot.tp_percent,
        sl_percent=bot.sl_percent,
        settings=json.dumps({
            "risk_percent": bot.risk_percent,
            "tp_percent": bot.tp_percent,
            "sl_percent": bot.sl_percent
        })
    )
    db.add(db_bot)
    db.commit()
    db.refresh(db_bot)
    
    return {
        "id": db_bot.id,
        "name": db_bot.name,
        "strategy": db_bot.strategy,
        "symbol": db_bot.symbol,
        "is_active": db_bot.is_active
    }

@app.get("/api/bots/{account_id}")
async def get_bots(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all bots for account"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    bots = db.query(Bot).filter(Bot.account_id == account_id).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "strategy": b.strategy,
            "symbol": b.symbol,
            "is_active": b.is_active,
            "risk_percent": b.risk_percent
        }
        for b in bots
    ]

@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start bot"""
    bot = db.query(Bot).join(Account).filter(
        Bot.id == bot_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot.is_active = True
    db.commit()
    
    return {"status": "started", "bot_id": bot_id}

@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Stop bot"""
    bot = db.query(Bot).join(Account).filter(
        Bot.id == bot_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    bot.is_active = False
    db.commit()
    
    return {"status": "stopped", "bot_id": bot_id}

# ===== Trading Data Endpoints =====
@app.get("/api/positions/{account_id}")
async def get_positions(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get open positions"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    positions = db.query(Position).filter(Position.account_id == account_id).all()
    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "type": p.type,
            "entry_price": p.entry_price,
            "current_price": p.current_price,
            "quantity": p.quantity,
            "pnl": p.pnl,
            "pnl_percent": p.pnl_percent,
            "opened_at": p.opened_at.isoformat()
        }
        for p in positions
    ]

@app.get("/api/trades/{account_id}")
async def get_trades(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get trade history"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trades = db.query(Trade).filter(Trade.account_id == account_id).order_by(Trade.closed_at.desc()).limit(50).all()
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "type": t.type,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "pnl_percent": t.pnl_percent,
            "opened_at": t.opened_at.isoformat(),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "status": t.status
        }
        for t in trades
    ]

@app.get("/api/statistics/{account_id}")
async def get_statistics(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get trading statistics"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trades = db.query(Trade).filter(Trade.account_id == account_id).all()
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl < 0]
    
    total_pnl = sum(t.pnl for t in trades)
    win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
    profit_factor = (sum(t.pnl for t in winning_trades) / abs(sum(t.pnl for t in losing_trades))) if losing_trades else 0
    
    return {
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(sum(t.pnl for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
        "avg_loss": round(sum(t.pnl for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
        "profit_factor": round(profit_factor, 2)
    }

# ===== Crypto/Forex Monitoring =====
@app.get("/api/market/price/{symbol}")
async def get_price(symbol: str):
    """Get real-time price for crypto or forex"""
    if symbol in ["BTC", "ETH", "BNB", "ADA", "XRP", "SOL"]:
        return await CryptoService.get_crypto_price(symbol)
    else:
        return await CryptoService.get_forex_price(symbol)

@app.get("/api/market/prices")
async def get_prices(symbols: str):
    """Get multiple prices"""
    symbol_list = symbols.split(",")
    prices = []
    
    for symbol in symbol_list:
        if symbol in ["BTC", "ETH", "BNB", "ADA", "XRP", "SOL"]:
            price = await CryptoService.get_crypto_price(symbol)
        else:
            price = await CryptoService.get_forex_price(symbol)
        prices.append(price)
    
    return prices

# ===== Financial Operations =====
@app.post("/api/deposits")
async def deposit(deposit: DepositRequest, account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create deposit"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Process payment
    payment = await PaymentService.process_deposit(deposit.amount, deposit.card_token)
    
    # Create deposit record
    db_deposit = Deposit(
        account_id=account_id,
        user_id=current_user["user_id"],
        amount=deposit.amount,
        currency="USD",
        status="confirmed" if payment["status"] == "confirmed" else "pending",
        stripe_id=payment.get("id")
    )
    db.add(db_deposit)
    
    # Update account balance
    if payment["status"] == "confirmed":
        account.balance += deposit.amount
        account.equity += deposit.amount
    
    db.commit()
    db.refresh(db_deposit)
    
    return {
        "id": db_deposit.id,
        "amount": deposit.amount,
        "status": db_deposit.status,
        "created_at": db_deposit.created_at.isoformat()
    }

@app.post("/api/withdrawals")
async def withdraw(withdrawal: WithdrawalRequest, account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create withdrawal"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if account.balance < withdrawal.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Create withdrawal record
    db_withdrawal = Withdrawal(
        account_id=account_id,
        user_id=current_user["user_id"],
        amount=withdrawal.amount,
        currency="USD",
        status="pending",
        bank_account=withdrawal.bank_account
    )
    db.add(db_withdrawal)
    
    # Deduct from balance
    account.balance -= withdrawal.amount
    
    db.commit()
    db.refresh(db_withdrawal)
    
    # Send WhatsApp notification
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if user and user.whatsapp_number:
        await AlertService.send_whatsapp_alert(
            user.whatsapp_number,
            f"Withdrawal request of ${withdrawal.amount} submitted. Status: Pending review."
        )
    
    return {
        "id": db_withdrawal.id,
        "amount": withdrawal.amount,
        "status": db_withdrawal.status,
        "created_at": db_withdrawal.created_at.isoformat()
    }

# ===== Alerts =====
@app.get("/api/alerts/{account_id}")
async def get_alerts(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get alerts"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    alerts = db.query(Alert).filter(Alert.account_id == account_id).order_by(Alert.created_at.desc()).limit(20).all()
    return [
        {
            "id": a.id,
            "type": a.type,
            "symbol": a.symbol,
            "message": a.message,
            "severity": a.severity,
            "is_sent": a.is_sent,
            "created_at": a.created_at.isoformat()
        }
        for a in alerts
    ]

# ===== Reports =====
@app.get("/api/reports/{account_id}")
async def generate_report(account_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate PDF report"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.user_id == current_user["user_id"]
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    trades = db.query(Trade).filter(Trade.account_id == account_id).all()
    
    # Generate PDF
    pdf_bytes = ReportService.generate_trading_report(
        {
            "name": account.name,
            "broker": account.broker,
            "balance": account.balance,
            "equity": account.equity
        },
        [
            {
                "symbol": t.symbol,
                "type": t.type,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent
            }
            for t in trades
        ]
    )
    
    return FileResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        filename=f"trading_report_{account_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    )

# ===== Health Check =====
@app.get("/api/health")
async def health():
    """Health check"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ===== WebSocket for Live Updates =====
@app.get("/api/config")
async def get_config():
    """Get frontend configuration"""
    return {
        "api_base": "http://localhost:8000/api",
        "websocket_url": "ws://localhost:8000/ws",
        "app_name": settings.APP_NAME,
        "app_version": "3.0.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True if settings.APP_ENV == "development" else False
    )
