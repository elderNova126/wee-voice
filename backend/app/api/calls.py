from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr

from app.core.security import get_current_active_user
from app.models import get_db, User, Call, CallMessage, CallStatus
from app.services.agent_service import CallSummaryService
from app.services.call_followup_service import update_call_follow_up_data
from app.services.email_service import EmailService
from app.services.notification_service import get_notification_service

router = APIRouter()


class CallResponse(BaseModel):
    id: int
    session_id: Optional[str] = None
    agent_id: int
    status: str
    duration_seconds: float
    duration_minutes: float
    cost: float
    transcript: Optional[str]
    summary: Optional[str]
    sentiment: Optional[str]
    started_at: Optional[datetime]  # Nullable - set when session actually starts
    ended_at: Optional[datetime]
    callback_requested: bool = False
    callback_reason: Optional[str] = None
    action_items: Optional[List[str]] = None
    action_tags: Optional[List[str]] = None
    
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


class CallEmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None


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

    # Ensure follow-up tags are refreshed using the latest action items data
    for call in calls:
        if call.action_items:
            update_call_follow_up_data(call, call.action_items)

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
    
    # If no transcript but has messages, build transcript from messages
    if not call.transcript:
        messages = db.query(CallMessage).filter(
            CallMessage.call_id == call_id
        ).order_by(CallMessage.timestamp).all()
        
        if messages:
            # Build transcript from messages
            transcript_lines = []
            for msg in messages:
                transcript_lines.append(f"{msg.role.upper()}: {msg.content}")
            call.transcript = "\n\n".join(transcript_lines)
            db.commit()
    
    # Return transcript or empty if still not available
    return {
        "call_id": call.id,
        "transcript": call.transcript or "",
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
    db.refresh(call)
    
    # Enrich response with persisted values
    result["summary"] = call.summary
    result["sentiment"] = call.sentiment
    result["key_points"] = call.key_points
    result["action_items"] = call.action_items
    result["action_tags"] = call.action_tags
    
    # Send email notification with summary
    if result.get("summary"):
        notification_service = get_notification_service()
        await notification_service.send_call_summary_email(db, call, result)
    
    return result


@router.post("/{call_id}/send-email")
def send_call_followup_email(
    call_id: int,
    payload: CallEmailRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Send a follow-up email related to a call."""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    email_sent = EmailService.send_email(
        to_email=payload.to_email,
        subject=payload.subject,
        body_text=payload.body,
        from_email=payload.from_email,
        from_name=payload.from_name,
    )

    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send email")

    # Record email activity as a system message on the call
    activity_message = CallMessage(
        call_id=call.id,
        role="system",
        content=(
            f"Follow-up email sent to {payload.to_email}\n"
            f"Subject: {payload.subject}\n\n{payload.body}"
        )
    )
    db.add(activity_message)
    db.commit()

    return {"message": "Email sent successfully"}


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


@router.post("/{call_id}/recalculate")
def recalculate_call_duration(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Recalculate duration and cost for a call"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Recalculate duration and cost
    if call.calculate_duration_and_cost():
        db.commit()
        return {
            "message": "Duration and cost recalculated successfully",
            "duration_minutes": call.duration_minutes,
            "cost": call.cost
        }
    else:
        raise HTTPException(status_code=400, detail="Cannot calculate duration - call not ended yet")


@router.post("/recalculate-all")
def recalculate_all_calls(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Recalculate duration and cost for all calls that have ended_at but 0 duration"""
    calls = db.query(Call).filter(
        Call.user_id == current_user.id,
        Call.ended_at.isnot(None),
        Call.duration_minutes == 0.0
    ).all()
    
    updated_count = 0
    for call in calls:
        if call.calculate_duration_and_cost():
            updated_count += 1
    
    db.commit()
    
    return {
        "message": f"Recalculated duration and cost for {updated_count} calls",
        "updated_count": updated_count
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

