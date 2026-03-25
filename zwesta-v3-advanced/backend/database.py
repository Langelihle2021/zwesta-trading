from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import get_settings
from datetime import datetime

settings = get_settings()

# Database
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255))
    full_name = Column(String(100))
    phone = Column(String(20))
    whatsapp_number = Column(String(20))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    name = Column(String(100))
    broker = Column(String(50))  # XM, FXCM, etc
    account_number = Column(String(50))
    api_key = Column(String(255))
    api_secret = Column(String(255))
    balance = Column(Float, default=10000.0)
    equity = Column(Float, default=10000.0)
    margin_used = Column(Float, default=0.0)
    margin_level = Column(Float, default=0.0)
    is_demo = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    name = Column(String(100))
    strategy = Column(String(50))  # scalping, swing, trend, etc
    symbol = Column(String(20))
    is_active = Column(Boolean, default=False)
    risk_percent = Column(Float, default=2.0)
    tp_percent = Column(Float, default=2.0)
    sl_percent = Column(Float, default=1.0)
    settings = Column(Text)  # JSON settings
    created_at = Column(DateTime, default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    symbol = Column(String(20))
    type = Column(String(10))  # BUY, SELL
    entry_price = Column(Float)
    current_price = Column(Float)
    quantity = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)
    opened_at = Column(DateTime, default=datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    symbol = Column(String(20))
    type = Column(String(10))  # BUY, SELL
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)
    opened_at = Column(DateTime)
    closed_at = Column(DateTime)
    status = Column(String(20))  # closed, cancelled

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    user_id = Column(Integer)
    type = Column(String(50))  # price_alert, pnl_alert, margin_alert
    symbol = Column(String(20))
    message = Column(Text)
    severity = Column(String(20))  # info, warning, critical
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Deposit(Base):
    __tablename__ = "deposits"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    user_id = Column(Integer)
    amount = Column(Float)
    currency = Column(String(10))
    status = Column(String(20))  # pending, confirmed, failed
    stripe_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer)
    user_id = Column(Integer)
    amount = Column(Float)
    currency = Column(String(10))
    status = Column(String(20))  # pending, confirmed, failed
    bank_account = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
