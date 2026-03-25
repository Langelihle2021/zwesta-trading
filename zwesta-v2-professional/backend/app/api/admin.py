"""
Admin API routes
System management, user management, settings
Only accessible to admin users
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models import User, TradingAccount

router = APIRouter()

# Request/Response models
class UserManagementResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: str
    
    class Config:
        from_attributes = True

class SystemStatusResponse(BaseModel):
    api_version: str
    database_status: str
    bot_status: str
    total_users: int
    total_accounts: int
    total_active_trades: int

@router.get("/users", response_model=List[UserManagementResponse])
async def list_all_users(db: Session = Depends(get_db)):
    """List all users (admin only)"""
    users = db.query(User).all()
    return users

@router.get("/system-status", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    """Get system status"""
    from app.models import Trade, TradeStatus
    
    total_users = db.query(User).count()
    total_accounts = db.query(TradingAccount).count()
    total_active_trades = db.query(Trade).filter(
        Trade.status == TradeStatus.OPEN
    ).count()
    
    return SystemStatusResponse(
        api_version="2.0.0",
        database_status="healthy",
        bot_status="running",
        total_users=total_users,
        total_accounts=total_accounts,
        total_active_trades=total_active_trades
    )

@router.post("/users/{user_id}/activate")
async def activate_user(user_id: int, db: Session = Depends(get_db)):
    """Activate user account"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    db.commit()
    return {"message": f"User {user.username} activated"}

@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: int, db: Session = Depends(get_db)):
    """Deactivate user account"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    return {"message": f"User {user.username} deactivated"}

@router.post("/users/{user_id}/promote-admin")
async def promote_to_admin(user_id: int, db: Session = Depends(get_db)):
    """Promote user to admin"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = True
    db.commit()
    return {"message": f"User {user.username} promoted to admin"}

@router.post("/users/{user_id}/demote-admin")
async def demote_from_admin(user_id: int, db: Session = Depends(get_db)):
    """Demote user from admin"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = False
    db.commit()
    return {"message": f"User {user.username} demoted from admin"}
