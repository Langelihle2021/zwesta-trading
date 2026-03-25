"""
Alerts API routes
Profit alerts, loss alerts, level-reached alerts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models import ProfitAlert, AlertType

router = APIRouter()

# Request/Response models
class AlertRequest(BaseModel):
    alert_type: str
    symbol: str = None
    threshold: float = None
    send_whatsapp: bool = True
    send_email: bool = False

class AlertResponse(BaseModel):
    id: int
    alert_type: str
    symbol: str = None
    threshold: float = None
    is_enabled: bool
    send_whatsapp: bool
    send_email: bool
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[AlertResponse])
async def get_user_alerts(user_id: int, db: Session = Depends(get_db)):
    """Get all alerts for user"""
    alerts = db.query(ProfitAlert).filter(
        ProfitAlert.user_id == user_id
    ).all()
    return alerts

@router.post("/", response_model=AlertResponse)
async def create_alert(user_id: int, request: AlertRequest, db: Session = Depends(get_db)):
    """Create new alert"""
    alert = ProfitAlert(
        user_id=user_id,
        alert_type=request.alert_type,
        symbol=request.symbol,
        threshold=request.threshold,
        send_whatsapp=request.send_whatsapp,
        send_email=request.send_email
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    request: AlertRequest,
    db: Session = Depends(get_db)
):
    """Update alert configuration"""
    alert = db.query(ProfitAlert).filter(ProfitAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.alert_type = request.alert_type
    alert.symbol = request.symbol
    alert.threshold = request.threshold
    alert.send_whatsapp = request.send_whatsapp
    alert.send_email = request.send_email
    
    db.commit()
    db.refresh(alert)
    return alert

@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """Delete alert"""
    alert = db.query(ProfitAlert).filter(ProfitAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}

@router.post("/{alert_id}/enable")
async def enable_alert(alert_id: int, db: Session = Depends(get_db)):
    """Enable alert"""
    alert = db.query(ProfitAlert).filter(ProfitAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_enabled = True
    db.commit()
    return {"message": "Alert enabled"}

@router.post("/{alert_id}/disable")
async def disable_alert(alert_id: int, db: Session = Depends(get_db)):
    """Disable alert"""
    alert = db.query(ProfitAlert).filter(ProfitAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_enabled = False
    db.commit()
    return {"message": "Alert disabled"}
