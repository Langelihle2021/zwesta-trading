"""
Database models
SQLAlchemy ORM models for Zwesta Trading System
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Boolean, Text, Enum, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base

# Enums
class AccountType(str, enum.Enum):
    DEMO = "demo"
    LIVE = "live"

class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"

class AlertType(str, enum.Enum):
    PROFIT = "profit"
    LOSS = "loss"
    LEVEL_REACHED = "level_reached"
    MARGIN_CALL = "margin_call"

# Models
class User(Base):
    """User account"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    phone = Column(String(20))
    whatsapp_number = Column(String(20))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    accounts = relationship("TradingAccount", back_populates="user")
    alerts = relationship("ProfitAlert", back_populates="user")
    mt5_credentials = relationship("MT5Credential", back_populates="user")

class TradingAccount(Base):
    """Trading account linked to user"""
    __tablename__ = "trading_accounts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_type = Column(Enum(AccountType), default=AccountType.DEMO)
    balance = Column(Numeric(15, 2), default=0.0)
    equity = Column(Numeric(15, 2), default=0.0)
    profit = Column(Numeric(15, 2), default=0.0)
    used_margin = Column(Numeric(15, 2), default=0.0)
    free_margin = Column(Numeric(15, 2), default=0.0)
    margin_level = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    trades = relationship("Trade", back_populates="account")
    positions = relationship("Position", back_populates="account")

class Trade(Base):
    """Executed trade record"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    status = Column(Enum(TradeStatus), default=TradeStatus.CLOSED)
    trade_type = Column(String(10), nullable=False)  # BUY or SELL
    entry_price = Column(Numeric(10, 5), nullable=False)
    exit_price = Column(Numeric(10, 5))
    quantity = Column(Numeric(10, 2), nullable=False)
    profit_loss = Column(Numeric(15, 2))
    profit_loss_percent = Column(Float)
    commission = Column(Numeric(10, 2), default=0.0)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    account = relationship("TradingAccount", back_populates="trades")

class Position(Base):
    """Open position"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    position_type = Column(String(10), nullable=False)  # BUY or SELL
    entry_price = Column(Numeric(10, 5), nullable=False)
    current_price = Column(Numeric(10, 5), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unrealized_profit = Column(Numeric(15, 2))
    unrealized_profit_percent = Column(Float)
    stop_loss = Column(Numeric(10, 5))
    take_profit = Column(Numeric(10, 5))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("TradingAccount", back_populates="positions")

class MT5Credential(Base):
    """MT5 terminal connection credentials"""
    __tablename__ = "mt5_credentials"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_number = Column(String(20), nullable=False)
    password = Column(String(255), nullable=False)  # Encrypted in production
    server = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    last_connected = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="mt5_credentials")

class ProfitAlert(Base):
    """Profit/loss alerts configuration"""
    __tablename__ = "profit_alerts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    symbol = Column(String(20))  # None = all symbols
    threshold = Column(Float)  # Alert when profit > threshold
    is_enabled = Column(Boolean, default=True)
    send_whatsapp = Column(Boolean, default=True)
    send_email = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="alerts")

class Deposit(Base):
    """Deposit transaction"""
    __tablename__ = "deposits"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="completed")  # pending, completed, rejected
    payment_method = Column(String(50))
    transaction_id = Column(String(100), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    """Withdrawal transaction"""
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(20), default="pending")  # pending, approved, completed, rejected
    payment_method = Column(String(50))
    account_details = Column(Text)
    transaction_id = Column(String(100), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

class Report(Base):
    """Generated PDF report"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=False, index=True)
    report_type = Column(String(50), nullable=False)  # monthly, quarterly, custom
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    file_path = Column(String(255))
    file_url = Column(String(255))
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    total_profit = Column(Numeric(15, 2), default=0.0)
    win_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
