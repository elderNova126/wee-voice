from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from collections import defaultdict

from app.models import get_db, User, UsageRecord, Call, VoiceAgent
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


# Get usage summary (from Call table for real call data)
@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage summary for the current user from actual calls"""
    
    # Total usage from Call table
    total_result = db.query(
        func.coalesce(func.sum(Call.duration_minutes), 0).label("total_minutes"),
        func.coalesce(func.sum(Call.cost), 0).label("total_cost"),
        func.count(Call.id).label("total_calls")
    ).filter(Call.user_id == current_user.id).first()
    
    total_minutes = float(total_result.total_minutes or 0)
    total_cost = float(total_result.total_cost or 0)
    total_calls = int(total_result.total_calls or 0)
    
    # Average call duration
    average_duration = total_minutes / total_calls if total_calls > 0 else 0
    
    # Current month usage (use started_at or created_at for date)
    now = datetime.utcnow()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    month_result = db.query(
        func.coalesce(func.sum(Call.duration_minutes), 0).label("month_minutes"),
        func.coalesce(func.sum(Call.cost), 0).label("month_cost")
    ).filter(
        Call.user_id == current_user.id,
        func.coalesce(Call.started_at, Call.created_at) >= current_month_start
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


# Get usage by month (from Call table)
@router.get("/by-month", response_model=List[UsageByMonth])
async def get_usage_by_month(
    months: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by month from actual calls"""
    
    call_date = func.coalesce(Call.started_at, Call.created_at)
    dialect_name = db.get_bind().dialect.name if hasattr(db.get_bind(), 'dialect') else 'sqlite'
    if dialect_name == 'postgresql':
        month_col = func.to_char(call_date, 'YYYY-MM')
    else:
        month_col = func.strftime("%Y-%m", call_date)
    
    results = db.query(
        month_col.label("month"),
        func.coalesce(func.sum(Call.duration_minutes), 0).label("minutes"),
        func.coalesce(func.sum(Call.cost), 0).label("cost"),
        func.count(Call.id).label("calls")
    ).filter(
        Call.user_id == current_user.id
    ).group_by(
        month_col
    ).order_by(
        month_col.desc()
    ).limit(months).all()
    
    return [
        UsageByMonth(
            month=r.month or "",
            minutes=float(r.minutes or 0),
            cost=float(r.cost or 0),
            calls=int(r.calls or 0)
        )
        for r in results
    ]


# Get usage by day (from Call table)
@router.get("/by-day", response_model=List[UsageByDay])
async def get_usage_by_day(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by day from actual calls"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    call_date = func.coalesce(Call.started_at, Call.created_at)
    
    results = db.query(
        func.date(call_date).label("date"),
        func.coalesce(func.sum(Call.duration_minutes), 0).label("minutes"),
        func.coalesce(func.sum(Call.cost), 0).label("cost"),
        func.count(Call.id).label("calls")
    ).filter(
        Call.user_id == current_user.id,
        call_date >= start_date
    ).group_by(
        func.date(call_date)
    ).order_by(
        func.date(call_date).desc()
    ).all()
    
    return [
        UsageByDay(
            date=str(r.date) if r.date else "",
            minutes=float(r.minutes or 0),
            cost=float(r.cost or 0),
            calls=int(r.calls or 0)
        )
        for r in results
    ]


# Get usage by agent (from Call table)
@router.get("/by-agent", response_model=List[UsageByAgent])
async def get_usage_by_agent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage grouped by agent from actual calls"""
    
    results = db.query(
        Call.agent_id,
        VoiceAgent.name.label("agent_name"),
        func.coalesce(func.sum(Call.duration_minutes), 0).label("minutes"),
        func.coalesce(func.sum(Call.cost), 0).label("cost"),
        func.count(Call.id).label("calls")
    ).join(
        VoiceAgent, Call.agent_id == VoiceAgent.id
    ).filter(
        Call.user_id == current_user.id
    ).group_by(
        Call.agent_id,
        VoiceAgent.name
    ).all()
    
    return [
        UsageByAgent(
            agent_id=r.agent_id,
            agent_name=r.agent_name or "",
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

