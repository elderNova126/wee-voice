"""
Callback Requests API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.models import get_db, User, Call, VoiceAgent, CallbackRequest
from app.core.security import get_current_user
from app.services.notification_service import get_notification_service
from app.services.call_followup_service import update_call_follow_up_data

router = APIRouter()


# Pydantic models
class CallbackRequestCreate(BaseModel):
    call_id: int
    reason: str
    priority: str = "normal"  # "urgent", "high", "normal", "low"
    caller_name: Optional[str] = None
    caller_phone: Optional[str] = None
    caller_email: Optional[str] = None
    preferred_callback_time: Optional[str] = None
    notes: Optional[str] = None


class CallbackRequestUpdate(BaseModel):
    status: Optional[str] = None  # "pending", "contacted", "completed", "cancelled"
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    resolution: Optional[str] = None


class CallbackRequestResponse(BaseModel):
    id: int
    call_id: int
    agent_id: int
    reason: str
    priority: str
    caller_name: Optional[str]
    caller_phone: Optional[str]
    caller_email: Optional[str]
    preferred_callback_time: Optional[str]
    status: str
    assigned_to: Optional[str]
    notes: Optional[str]
    resolution: Optional[str]
    created_at: datetime
    contacted_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@router.post("/", response_model=CallbackRequestResponse)
async def create_callback_request(
    request: CallbackRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new callback request"""
    # Verify call exists and belongs to user
    call = db.query(Call).filter(
        Call.id == request.call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Create callback request
    callback_request = CallbackRequest(
        call_id=request.call_id,
        user_id=current_user.id,
        agent_id=call.agent_id,
        reason=request.reason,
        priority=request.priority,
        caller_name=request.caller_name or call.caller_name,
        caller_phone=request.caller_phone or call.caller_phone,
        caller_email=request.caller_email,
        preferred_callback_time=request.preferred_callback_time,
        notes=request.notes
    )
    
    db.add(callback_request)
    
    # Update call record
    call.callback_requested = True
    call.callback_reason = request.reason
    update_call_follow_up_data(call)
    
    db.commit()
    db.refresh(callback_request)
    
    # Send notification email
    notification_service = get_notification_service()
    await notification_service.send_callback_notification(db, callback_request)
    
    return callback_request


@router.get("/", response_model=List[CallbackRequestResponse])
async def list_callback_requests(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all callback requests for current user"""
    query = db.query(CallbackRequest).filter(
        CallbackRequest.user_id == current_user.id
    )
    
    if status_filter:
        query = query.filter(CallbackRequest.status == status_filter)
    
    if priority_filter:
        query = query.filter(CallbackRequest.priority == priority_filter)
    
    callback_requests = query.order_by(
        CallbackRequest.created_at.desc()
    ).all()
    
    return callback_requests


@router.get("/{callback_id}", response_model=CallbackRequestResponse)
async def get_callback_request(
    callback_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific callback request"""
    callback_request = db.query(CallbackRequest).filter(
        CallbackRequest.id == callback_id,
        CallbackRequest.user_id == current_user.id
    ).first()
    
    if not callback_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Callback request not found"
        )
    
    return callback_request


@router.patch("/{callback_id}", response_model=CallbackRequestResponse)
async def update_callback_request(
    callback_id: int,
    update: CallbackRequestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a callback request"""
    callback_request = db.query(CallbackRequest).filter(
        CallbackRequest.id == callback_id,
        CallbackRequest.user_id == current_user.id
    ).first()
    
    if not callback_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Callback request not found"
        )
    
    # Update fields
    if update.status:
        callback_request.status = update.status
        
        if update.status == "contacted" and not callback_request.contacted_at:
            callback_request.contacted_at = datetime.utcnow()
        elif update.status == "completed" and not callback_request.completed_at:
            callback_request.completed_at = datetime.utcnow()
    
    if update.assigned_to is not None:
        callback_request.assigned_to = update.assigned_to
    
    if update.notes is not None:
        callback_request.notes = update.notes
    
    if update.resolution is not None:
        callback_request.resolution = update.resolution
    
    db.commit()
    db.refresh(callback_request)
    
    return callback_request


@router.delete("/{callback_id}")
async def delete_callback_request(
    callback_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete (cancel) a callback request"""
    callback_request = db.query(CallbackRequest).filter(
        CallbackRequest.id == callback_id,
        CallbackRequest.user_id == current_user.id
    ).first()
    
    if not callback_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Callback request not found"
        )
    
    callback_request.status = "cancelled"
    db.commit()
    
    return {"message": "Callback request cancelled"}

