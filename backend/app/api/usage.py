from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from collections import defaultdict

from app.models import get_db, User, UsageRecord, Call
from app.core.security import get_current_user

router = APIRouter()


# Pydantic models
class UsageRecordResponse(BaseModel):
    id: int
    minutes_used: float
    cost: float
    date: datetime
    agent_id: Optional[int]
    call_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UsageSummary(BaseModel):
    total_minutes: float
    total_cost: float
    total_calls: int
    average_call_duration: float
    current_month_minutes: float
    current_month_cost: float


class UsageByMonth(BaseModel):
    month: str
    minutes: float
    cost: float
    calls: int


class UsageByDay(BaseModel):
    date: str
    minutes: float
    cost: float
    calls: int


class UsageByAgent(BaseModel):
    agent_id: int
    agent_name: str
    minutes: float
    cost: float
    calls: int


class UsageAnalytics(BaseModel):
    summary: UsageSummary
    by_month: List[UsageByMonth]
    by_day: List[UsageByDay]
    by_agent: List[UsageByAgent]


# Get all usage records
@router.get("/records", response_model=List[UsageRecordResponse])
async def get_usage_records(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage records for the current user"""
    query = db.query(UsageRecord).filter(UsageRecord.user_id == current_user.id)
    
    # Filter by date range if provided
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(UsageRecord.date >= start)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (YYYY-MM-DD)"
            )
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(UsageRecord.date <= end)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (YYYY-MM-DD)"
            )
    
    records = query.order_by(UsageRecord.date.desc()).offset(skip).limit(limit).all()
    return records


# Get usage summary
@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage summary for the current user"""
    
    # Total usage
    total_result = db.query(
        func.sum(UsageRecord.minutes_used).label("total_minutes"),
        func.sum(UsageRecord.cost).label("total_cost"),
        func.count(UsageRecord.id).label("total_calls")
    ).filter(UsageRecord.user_id == current_user.id).first()
    
    total_minutes = float(total_result.total_minutes or 0)
    total_cost = float(total_result.total_cost or 0)
    total_calls = int(total_result.total_calls or 0)
    
    # Average call duration
    average_duration = total_minutes / total_calls if total_calls > 0 else 0
    
    # Current month usage
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
    
    month_result = db.query(
        func.sum(UsageRecord.minutes_used).label("month_minutes"),
        func.sum(UsageRecord.cost).label("month_cost")
    ).filter(
        UsageRecord.user_id == current_user.id,
        UsageRecord.month == current_month
    ).first()
    
    current_month_minutes = float(month_result.month_minutes or 0)
    current_month_cost = float(month_result.month_cost or 0)
    
    return UsageSummary(
        total_minutes=total_minutes,
        total_cost=total_cost,
        total_calls=total_calls,
        average_call_duration=average_duration,
        current_month_minutes=current_month_minutes,
        current_month_cost=current_month_cost
    )


# Get usage by month
@router.get("/by-month", response_model=List[UsageByMonth])
async def get_usage_by_month(
    months: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by month"""
    
    results = db.query(
        UsageRecord.month,
        func.sum(UsageRecord.minutes_used).label("minutes"),
        func.sum(UsageRecord.cost).label("cost"),
        func.count(UsageRecord.id).label("calls")
    ).filter(
        UsageRecord.user_id == current_user.id
    ).group_by(
        UsageRecord.month
    ).order_by(
        UsageRecord.month.desc()
    ).limit(months).all()
    
    return [
        UsageByMonth(
            month=r.month,
            minutes=float(r.minutes or 0),
            cost=float(r.cost or 0),
            calls=int(r.calls or 0)
        )
        for r in results
    ]


# Get usage by day
@router.get("/by-day", response_model=List[UsageByDay])
async def get_usage_by_day(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by day"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    results = db.query(
        func.date(UsageRecord.date).label("date"),
        func.sum(UsageRecord.minutes_used).label("minutes"),
        func.sum(UsageRecord.cost).label("cost"),
        func.count(UsageRecord.id).label("calls")
    ).filter(
        UsageRecord.user_id == current_user.id,
        UsageRecord.date >= start_date
    ).group_by(
        func.date(UsageRecord.date)
    ).order_by(
        func.date(UsageRecord.date).desc()
    ).all()
    
    return [
        UsageByDay(
            date=str(r.date),
            minutes=float(r.minutes or 0),
            cost=float(r.cost or 0),
            calls=int(r.calls or 0)
        )
        for r in results
    ]


# Get usage by agent
@router.get("/by-agent", response_model=List[UsageByAgent])
async def get_usage_by_agent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by agent"""
    from app.models import VoiceAgent
    
    results = db.query(
        UsageRecord.agent_id,
        VoiceAgent.name.label("agent_name"),
        func.sum(UsageRecord.minutes_used).label("minutes"),
        func.sum(UsageRecord.cost).label("cost"),
        func.count(UsageRecord.id).label("calls")
    ).join(
        VoiceAgent, UsageRecord.agent_id == VoiceAgent.id
    ).filter(
        UsageRecord.user_id == current_user.id,
        UsageRecord.agent_id.isnot(None)
    ).group_by(
        UsageRecord.agent_id,
        VoiceAgent.name
    ).all()
    
    return [
        UsageByAgent(
            agent_id=r.agent_id,
            agent_name=r.agent_name,
            minutes=float(r.minutes or 0),
            cost=float(r.cost or 0),
            calls=int(r.calls or 0)
        )
        for r in results
    ]


# Get complete analytics
@router.get("/analytics", response_model=UsageAnalytics)
async def get_usage_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete usage analytics"""
    
    # Get all data in parallel
    summary = await get_usage_summary(db=db, current_user=current_user)
    by_month = await get_usage_by_month(db=db, current_user=current_user)
    by_day = await get_usage_by_day(db=db, current_user=current_user)
    by_agent = await get_usage_by_agent(db=db, current_user=current_user)
    
    return UsageAnalytics(
        summary=summary,
        by_month=by_month,
        by_day=by_day,
        by_agent=by_agent
    )


# Create usage record from call
@router.post("/record-call/{call_id}")
async def record_call_usage(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record usage from a completed call"""
    
    # Get the call
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Check if usage already recorded
    existing = db.query(UsageRecord).filter(
        UsageRecord.call_id == call_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usage already recorded for this call"
        )
    
    # Create usage record
    call_date = call.started_at or call.created_at
    usage_record = UsageRecord(
        user_id=current_user.id,
        agent_id=call.agent_id,
        call_id=call.id,
        minutes_used=call.duration_minutes,
        cost=call.cost,
        date=call_date,
        month=call_date.strftime("%Y-%m"),
        year=call_date.year
    )
    
    db.add(usage_record)
    
    # Update user's usage counters
    current_user.total_minutes_used += call.duration_minutes
    current_user.monthly_minutes_used += call.duration_minutes
    
    db.commit()
    
    return {"success": True, "usage_record_id": usage_record.id}


# Export usage data as CSV
@router.get("/export")
async def export_usage_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export usage data as CSV"""
    from fastapi.responses import StreamingResponse
    import csv
    from io import StringIO
    
    query = db.query(UsageRecord).filter(UsageRecord.user_id == current_user.id)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(UsageRecord.date >= start)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format"
            )
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(UsageRecord.date <= end)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format"
            )
    
    records = query.order_by(UsageRecord.date.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["Date", "Minutes Used", "Cost", "Agent ID", "Call ID"])
    
    # Write data
    for record in records:
        writer.writerow([
            record.date.isoformat(),
            record.minutes_used,
            record.cost,
            record.agent_id,
            record.call_id
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=usage_export_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        }
    )

