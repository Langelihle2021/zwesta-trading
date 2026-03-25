"""
Account management API routes
Account info, deposits, withdrawals, account switching
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from decimal import Decimal

from app.database import get_db
from app.models import TradingAccount, Deposit, Withdrawal, AccountType

router = APIRouter()

# Request/Response models
class AccountResponse(BaseModel):
    id: int
    account_type: str
    balance: Decimal
    equity: Decimal
    profit: Decimal
    used_margin: Decimal
    free_margin: Decimal
    margin_level: float
    is_active: bool
    
    class Config:
        from_attributes = True

class DepositRequest(BaseModel):
    amount: float
    currency: str = "USD"
    payment_method: str

class WithdrawalRequest(BaseModel):
    amount: float
    currency: str = "USD"
    payment_method: str
    account_details: str

class DepositResponse(BaseModel):
    id: int
    amount: Decimal
    status: str
    created_at: str
    
    class Config:
        from_attributes = True

class WithdrawalResponse(BaseModel):
    id: int
    amount: Decimal
    status: str
    created_at: str
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[AccountResponse])
async def get_user_accounts(user_id: int, db: Session = Depends(get_db)):
    """Get all accounts for user"""
    accounts = db.query(TradingAccount).filter(
        TradingAccount.user_id == user_id
    ).all()
    return accounts

@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, db: Session = Depends(get_db)):
    """Get account details"""
    account = db.query(TradingAccount).filter(
        TradingAccount.id == account_id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=404,
            detail="Account not found"
        )
    
    return account

@router.post("/{account_id}/deposits", response_model=DepositResponse)
async def create_deposit(
    account_id: int,
    request: DepositRequest,
    db: Session = Depends(get_db)
):
    """Create deposit request"""
    deposit = Deposit(
        account_id=account_id,
        amount=Decimal(str(request.amount)),
        currency=request.currency,
        payment_method=request.payment_method,
        status="pending"
    )
    db.add(deposit)
    db.commit()
    db.refresh(deposit)
    
    return DepositResponse(
        id=deposit.id,
        amount=deposit.amount,
        status=deposit.status,
        created_at=deposit.created_at.isoformat()
    )

@router.post("/{account_id}/withdrawals", response_model=WithdrawalResponse)
async def create_withdrawal(
    account_id: int,
    request: WithdrawalRequest,
    db: Session = Depends(get_db)
):
    """Create withdrawal request"""
    account = db.query(TradingAccount).filter(
        TradingAccount.id == account_id
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=404,
            detail="Account not found"
        )
    
    if account.free_margin < request.amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient funds"
        )
    
    withdrawal = Withdrawal(
        account_id=account_id,
        amount=Decimal(str(request.amount)),
        currency=request.currency,
        payment_method=request.payment_method,
        account_details=request.account_details,
        status="pending"
    )
    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)
    
    return WithdrawalResponse(
        id=withdrawal.id,
        amount=withdrawal.amount,
        status=withdrawal.status,
        created_at=withdrawal.created_at.isoformat()
    )

@router.get("/{account_id}/deposits")
async def get_account_deposits(account_id: int, db: Session = Depends(get_db)):
    """Get deposit history"""
    deposits = db.query(Deposit).filter(
        Deposit.account_id == account_id
    ).order_by(Deposit.created_at.desc()).all()
    
    return [
        {
            "id": d.id,
            "amount": float(d.amount),
            "status": d.status,
            "created_at": d.created_at.isoformat()
        }
        for d in deposits
    ]

@router.get("/{account_id}/withdrawals")
async def get_account_withdrawals(account_id: int, db: Session = Depends(get_db)):
    """Get withdrawal history"""
    withdrawals = db.query(Withdrawal).filter(
        Withdrawal.account_id == account_id
    ).order_by(Withdrawal.created_at.desc()).all()
    
    return [
        {
            "id": w.id,
            "amount": float(w.amount),
            "status": w.status,
            "created_at": w.created_at.isoformat()
        }
        for w in withdrawals
    ]
