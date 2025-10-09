from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.security import get_current_active_user
from app.models import get_db, User, Call, CallMessage, CallStatus
from app.services.agent_service import CallSummaryService

router = APIRouter()


class CallResponse(BaseModel):
    id: int
    session_id: str
    agent_id: int
    status: str
    duration_seconds: float
    duration_minutes: float
    cost: float
    transcript: Optional[str]
    summary: Optional[str]
    sentiment: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class CallDetailResponse(CallResponse):
    messages: List[Any] = []
    key_points: Optional[List[str]] = None
    caller_phone: Optional[str] = None
    caller_name: Optional[str] = None


class CallListFilters(BaseModel):
    agent_id: Optional[int] = None
    status: Optional[CallStatus] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


@router.get("/", response_model=List[CallResponse])
def list_calls(
    agent_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List calls for current user with filters"""
    query = db.query(Call).filter(Call.user_id == current_user.id)
    
    if agent_id:
        query = query.filter(Call.agent_id == agent_id)
    
    if status:
        query = query.filter(Call.status == status)
    
    calls = query.order_by(desc(Call.created_at)).offset(offset).limit(limit).all()
    return calls


@router.get("/{call_id}", response_model=CallDetailResponse)
def get_call(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific call"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Include messages
    messages = db.query(CallMessage).filter(
        CallMessage.call_id == call_id
    ).order_by(CallMessage.timestamp).all()
    
    call_data = CallDetailResponse.model_validate(call)
    call_data.messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp
        }
        for msg in messages
    ]
    
    return call_data


@router.get("/{call_id}/transcript")
def get_transcript(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get transcript for a call"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if not call.transcript:
        raise HTTPException(status_code=404, detail="Transcript not available")
    
    return {
        "call_id": call.id,
        "transcript": call.transcript,
        "transcript_json": call.transcript_json
    }


@router.post("/{call_id}/generate-summary")
async def generate_summary(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Generate AI summary for a call"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if not call.transcript:
        raise HTTPException(status_code=400, detail="Transcript not available")
    
    # Generate summary
    summary_service = CallSummaryService()
    result = await summary_service.generate_summary(call)
    
    db.commit()
    
    return result


@router.get("/stats/overview")
def get_call_stats(
    days: int = Query(30, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get call statistics for the user"""
    from_date = datetime.utcnow() - timedelta(days=days)
    
    # Total calls
    total_calls = db.query(Call).filter(
        Call.user_id == current_user.id,
        Call.created_at >= from_date
    ).count()
    
    # Total minutes
    calls = db.query(Call).filter(
        Call.user_id == current_user.id,
        Call.created_at >= from_date,
        Call.status == CallStatus.COMPLETED
    ).all()
    
    total_minutes = sum(call.duration_minutes for call in calls)
    total_cost = sum(call.cost for call in calls)
    
    # Calls by status
    from sqlalchemy import func
    status_counts = db.query(
        Call.status,
        func.count(Call.id)
    ).filter(
        Call.user_id == current_user.id,
        Call.created_at >= from_date
    ).group_by(Call.status).all()
    
    return {
        "total_calls": total_calls,
        "total_minutes": round(total_minutes, 2),
        "total_cost": round(total_cost, 2),
        "status_breakdown": {status: count for status, count in status_counts},
        "period_days": days
    }


@router.delete("/{call_id}")
def delete_call(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a call record"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    db.delete(call)
    db.commit()
    
    return {"message": "Call deleted successfully"}

