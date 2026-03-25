"""
Reports API routes
PDF report generation, report history, statistics
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import Report, Trade, TradeStatus

router = APIRouter()

# Request/Response models
class ReportRequest(BaseModel):
    report_type: str  # monthly, quarterly, custom
    start_date: datetime = None
    end_date: datetime = None

class ReportResponse(BaseModel):
    id: int
    report_type: str
    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    total_profit: float
    win_rate: float
    file_url: str = None
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[ReportResponse])
async def get_account_reports(account_id: int, db: Session = Depends(get_db)):
    """Get all reports for account"""
    reports = db.query(Report).filter(
        Report.account_id == account_id
    ).order_by(Report.created_at.desc()).all()
    
    return reports

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    account_id: int,
    request: ReportRequest,
    db: Session = Depends(get_db)
):
    """Generate new report"""
    # Get trades for date range
    query = db.query(Trade).filter(
        Trade.account_id == account_id,
        Trade.status == TradeStatus.CLOSED
    )
    
    if request.start_date:
        query = query.filter(Trade.closed_at >= request.start_date)
    
    if request.end_date:
        query = query.filter(Trade.closed_at <= request.end_date)
    
    trades = query.all()
    
    # Calculate statistics
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.profit_loss > 0])
    total_profit = sum(t.profit_loss for t in trades)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Create report record
    report = Report(
        account_id=account_id,
        report_type=request.report_type,
        start_date=request.start_date or datetime.utcnow(),
        end_date=request.end_date or datetime.utcnow(),
        total_trades=total_trades,
        winning_trades=winning_trades,
        total_profit=total_profit,
        win_rate=win_rate
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    
    return report

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: Session = Depends(get_db)):
    """Get report details"""
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report

@router.get("/{report_id}/download")
async def download_report(report_id: int, db: Session = Depends(get_db)):
    """Download report as PDF"""
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # TODO: Implement PDF generation using ReportLab or WeasyPrint
    raise HTTPException(
        status_code=501,
        detail="PDF download not yet implemented"
    )

@router.delete("/{report_id}")
async def delete_report(report_id: int, db: Session = Depends(get_db)):
    """Delete report"""
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    db.delete(report)
    db.commit()
    return {"message": "Report deleted"}
