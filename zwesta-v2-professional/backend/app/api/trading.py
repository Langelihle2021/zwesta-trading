"""
Trading API routes
Trades, positions, symbols, market data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import Trade, Position, TradeStatus

router = APIRouter()

# Request/Response models
class TradeResponse(BaseModel):
    id: int
    symbol: str
    trade_type: str
    entry_price: float
    exit_price: float
    quantity: float
    profit_loss: float
    profit_loss_percent: float
    status: str
    opened_at: datetime
    closed_at: datetime = None
    
    class Config:
        from_attributes = True

class PositionResponse(BaseModel):
    id: int
    symbol: str
    position_type: str
    entry_price: float
    current_price: float
    quantity: float
    unrealized_profit: float
    unrealized_profit_percent: float
    stop_loss: float = None
    take_profit: float = None
    
    class Config:
        from_attributes = True

class CreateTradeRequest(BaseModel):
    symbol: str
    trade_type: str  # BUY or SELL
    entry_price: float
    quantity: float
    stop_loss: float = None
    take_profit: float = None

class CloseTradeRequest(BaseModel):
    exit_price: float

@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    account_id: int,
    symbol: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get trades for account"""
    query = db.query(Trade).filter(Trade.account_id == account_id)
    
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    
    if status:
        query = query.filter(Trade.status == status)
    
    trades = query.order_by(Trade.closed_at.desc()).all()
    return trades

@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(account_id: int, db: Session = Depends(get_db)):
    """Get open positions for account"""
    positions = db.query(Position).filter(
        Position.account_id == account_id
    ).all()
    return positions

@router.post("/trades", response_model=TradeResponse)
async def create_trade(
    account_id: int,
    request: CreateTradeRequest,
    db: Session = Depends(get_db)
):
    """Create new trade"""
    # Implementation for creating trades via API
    raise HTTPException(
        status_code=501,
        detail="Trade creation endpoint not yet implemented"
    )

@router.post("/trades/{trade_id}/close")
async def close_trade(
    trade_id: int,
    request: CloseTradeRequest,
    db: Session = Depends(get_db)
):
    """Close open trade"""
    # Implementation for closing trades
    raise HTTPException(
        status_code=501,
        detail="Trade closing endpoint not yet implemented"
    )

@router.get("/symbols")
async def get_tradeable_symbols():
    """Get list of tradeable symbols"""
    return {
        "symbols": [
            "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
            "GOLD", "XAUUSD", "XAGUSD", "BRENT",
            "BTCUSD", "ETHUSD"
        ]
    }

@router.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get current market data for symbol"""
    # Implementation for fetching live market data
    raise HTTPException(
        status_code=501,
        detail="Market data endpoint not yet implemented"
    )

@router.get("/statistics")
async def get_account_statistics(account_id: int, db: Session = Depends(get_db)):
    """Get trading statistics for account"""
    trades = db.query(Trade).filter(
        Trade.account_id == account_id,
        Trade.status == TradeStatus.CLOSED
    ).all()
    
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_profit": 0.0,
            "average_profit": 0.0
        }
    
    winning_trades = [t for t in trades if t.profit_loss > 0]
    losing_trades = [t for t in trades if t.profit_loss < 0]
    total_profit = sum(t.profit_loss for t in trades)
    
    return {
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": (len(winning_trades) / len(trades)) * 100 if trades else 0,
        "total_profit": total_profit,
        "average_profit": total_profit / len(trades) if trades else 0
    }
