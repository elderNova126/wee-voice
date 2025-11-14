from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import logging

from app.core.security import get_current_active_user
from app.models import get_db, User, Call, CallMessage, CallStatus, VoiceAgent
from app.services.agent_service import CallSummaryService
from app.services.call_followup_service import update_call_follow_up_data
from app.services.email_service import EmailService
from app.services.notification_service import get_notification_service

router = APIRouter()
logger = logging.getLogger(__name__)


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
    summarization_status: Optional[str] = None
    is_favorite: bool = False
    
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


class CallMessageRequest(BaseModel):
    content: str


class PaginatedCallResponse(BaseModel):
    items: List[CallResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("/", response_model=PaginatedCallResponse)
def list_calls(
    agent_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    action_required: Optional[bool] = Query(None, description="Filter by action required"),
    favorite: Optional[bool] = Query(None, description="Filter by favorite status"),
    search: Optional[str] = Query(None, description="Search in transcript, summary, caller name, and caller phone"),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List calls for current user with filters and pagination. Regular users see only calls from their agents. Admins see all calls."""
    # Admin users can see all calls
    if current_user.is_superuser:
        query = db.query(Call)
    else:
        # Regular users see only calls from agents they created
        # Join with VoiceAgent to filter by agent.user_id
        query = db.query(Call).join(VoiceAgent, Call.agent_id == VoiceAgent.id).filter(
            VoiceAgent.user_id == current_user.id
        )
    
    if agent_id:
        query = query.filter(Call.agent_id == agent_id)
        # For non-admin users, verify the agent belongs to them
        if not current_user.is_superuser:
            agent = db.query(VoiceAgent).filter(
                VoiceAgent.id == agent_id,
                VoiceAgent.user_id == current_user.id
            ).first()
            if not agent:
                raise HTTPException(status_code=403, detail="Access denied to this agent")
    
    if status:
        query = query.filter(Call.status == status)
    
    # Filter by favorite status
    if favorite is not None:
        query = query.filter(Call.is_favorite == favorite)
    
    # Search filter - search in transcript, summary, caller_name, and caller_phone
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Call.transcript.ilike(search_term),
                Call.summary.ilike(search_term),
                Call.caller_name.ilike(search_term),
                Call.caller_phone.ilike(search_term)
            )
        )
    
    # Filter by action required
    # Note: This is a simplified filter. For production, consider using PostgreSQL JSON/array functions
    # or maintaining a separate boolean column for action_required
    if action_required is not None:
        # First, get all matching calls to check action_tags and action_items
        # This is not ideal for large datasets but works for the current implementation
        temp_query = query
        all_matching_calls = temp_query.all()
        
        filtered_call_ids = []
        for call in all_matching_calls:
            # Ensure action_tags are up-to-date
            if call.action_items:
                update_call_follow_up_data(call, call.action_items)
            
            has_action_required = False
            
            # Check callback_requested flag
            if getattr(call, 'callback_requested', False):
                has_action_required = True
            
            # Check action_tags - match frontend logic: tags containing "request"
            if not has_action_required and call.action_tags and len(call.action_tags) > 0:
                # Frontend checks if tag includes "request" (case-insensitive)
                has_action_required = any('request' in tag.lower() for tag in call.action_tags)
            
            # Also check action_items for callback/follow-up keywords as fallback
            if not has_action_required and call.action_items and len(call.action_items) > 0:
                action_items_str = ' '.join(call.action_items).lower()
                has_action_required = any(keyword in action_items_str for keyword in [
                    'callback', 'follow-up', 'call back', 'contact', 'reach out', 'followup', 'rappel', 'rappeler'
                ])
            
            if action_required and has_action_required:
                filtered_call_ids.append(call.id)
            elif not action_required and not has_action_required:
                filtered_call_ids.append(call.id)
        
        if filtered_call_ids:
            query = query.filter(Call.id.in_(filtered_call_ids))
        else:
            # No calls match the filter, return empty result
            query = query.filter(Call.id == -1)  # Impossible condition
    
    # Get total count before pagination
    total = query.count()
    
    # Calculate offset from page and per_page
    offset = (page - 1) * per_page
    
    # Apply pagination
    calls = query.order_by(desc(Call.created_at)).offset(offset).limit(per_page).all()

    # Ensure follow-up tags are refreshed using the latest action items data
    # Note: This is already done in the action_required filter above, but we do it again
    # to ensure all calls have up-to-date tags when returned
    for call in calls:
        if call.action_items:
            update_call_follow_up_data(call, call.action_items)
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginatedCallResponse(
        items=calls,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{call_id}", response_model=CallDetailResponse)
def get_call(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific call. Regular users can only access calls from their agents."""
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check access: admin can access any call, regular users only their agents' calls
    if not current_user.is_superuser:
        agent = db.query(VoiceAgent).filter(
            VoiceAgent.id == call.agent_id,
            VoiceAgent.user_id == current_user.id
        ).first()
        if not agent:
            raise HTTPException(status_code=403, detail="Access denied to this call")
    
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
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check access: admin can access any call, regular users only their agents' calls
    if not current_user.is_superuser:
        agent = db.query(VoiceAgent).filter(
            VoiceAgent.id == call.agent_id,
            VoiceAgent.user_id == current_user.id
        ).first()
        if not agent:
            raise HTTPException(status_code=403, detail="Access denied to this call")

    try:
        logger.info(f"Attempting to send email for call {call_id} to {payload.to_email}")
        logger.info(f"Email subject: {payload.subject}")
        
        email_sent = EmailService.send_email(
            to_email=payload.to_email,
            subject=payload.subject,
            body_text=payload.body,
            from_email=payload.from_email,
            from_name=payload.from_name,
        )

        logger.info(f"Email service returned: {email_sent} for call {call_id} to {payload.to_email}")

        if not email_sent:
            logger.error(f"Failed to send email for call {call_id} to {payload.to_email}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to send email. Please check SMTP configuration and try again."
            )
        
        logger.info(f"Email sent successfully for call {call_id} to {payload.to_email}")
    except Exception as e:
        logger.error(f"Error sending email for call {call_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )

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
    """Get call statistics for the user with proper error handling"""
    try:
        from_date = datetime.utcnow() - timedelta(days=days)
        
        # Admin users can see all calls, regular users see only their agents' calls
        if current_user.is_superuser:
            base_query = db.query(Call)
        else:
            # Regular users see only calls from agents they created
            base_query = db.query(Call).join(VoiceAgent, Call.agent_id == VoiceAgent.id).filter(
                VoiceAgent.user_id == current_user.id
            )
        
        # Total calls
        total_calls = base_query.filter(
            Call.created_at >= from_date
        ).count()
        
        # Total minutes and cost from all calls (not just completed)
        # Use aggregate functions for better performance instead of loading all calls
        from sqlalchemy import func
        totals = base_query.filter(
            Call.created_at >= from_date
        ).with_entities(
            func.sum(Call.duration_minutes).label('total_minutes'),
            func.sum(Call.cost).label('total_cost')
        ).first()
        
        total_minutes = float(totals.total_minutes or 0)
        total_cost = float(totals.total_cost or 0)
        
        # Calls by status
        status_counts = base_query.filter(
            Call.created_at >= from_date
        ).with_entities(
            Call.status,
            func.count(Call.id)
        ).group_by(Call.status).all()
        
        return {
            "total_calls": total_calls,
            "total_minutes": round(total_minutes, 2),
            "total_cost": round(total_cost, 2),
            "status_breakdown": {str(status): count for status, count in status_counts},
            "period_days": days
        }
    except Exception as e:
        logger.error(f"Error fetching call stats: {e}", exc_info=True)
        # Return default values on error
        return {
            "total_calls": 0,
            "total_minutes": 0.0,
            "total_cost": 0.0,
            "status_breakdown": {},
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


@router.post("/{call_id}/messages")
async def send_message(
    call_id: int,
    message: CallMessageRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Send a message for a call (public endpoint for visitors)"""
    # Get call - no auth required for public agents
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify call is still active (not completed)
    if call.status in [CallStatus.COMPLETED, CallStatus.FAILED, CallStatus.INTERRUPTED]:
        raise HTTPException(status_code=400, detail="Cannot send message to completed call")
    
    content = message.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content is required")
    
    # Create message
    call_message = CallMessage(
        call_id=call_id,
        role="user",
        content=content
    )
    db.add(call_message)
    
    # Update transcript if it exists
    if call.transcript:
        call.transcript += f"\n\nUSER: {content}"
    else:
        call.transcript = f"USER: {content}"
    
    db.commit()
    db.refresh(call_message)
    
    # Broadcast message to call owner via WebSocket
    try:
        from app.api.websocket import call_monitor_manager
        await call_monitor_manager.broadcast_call_update(call.user_id, {
            "id": call.id,
            "new_message": {
                "id": call_message.id,
                "role": call_message.role,
                "content": call_message.content,
                "timestamp": call_message.timestamp.isoformat() if call_message.timestamp else None
            }
        })
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
    
    return {
        "id": call_message.id,
        "role": call_message.role,
        "content": call_message.content,
        "timestamp": call_message.timestamp
    }


@router.delete("/{call_id}")
def delete_call(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a call record. Regular users can only delete calls from their agents. Admins can delete any call."""
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check access: admin can delete any call, regular users only their agents' calls
    if not current_user.is_superuser:
        agent = db.query(VoiceAgent).filter(
            VoiceAgent.id == call.agent_id,
            VoiceAgent.user_id == current_user.id
        ).first()
        if not agent:
            raise HTTPException(status_code=403, detail="Access denied to delete this call")
    
    db.delete(call)
    db.commit()
    
    return {"message": "Call deleted successfully"}


class BulkDeleteRequest(BaseModel):
    call_ids: List[int]


class BulkFavoriteRequest(BaseModel):
    call_ids: List[int]
    is_favorite: bool


@router.post("/bulk/delete", response_model=dict)
def bulk_delete_calls(
    request: BulkDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete multiple call records. Regular users can only delete calls from their agents. Admins can delete any calls."""
    if not request.call_ids:
        raise HTTPException(status_code=400, detail="No call IDs provided")
    
    # Get all calls
    calls = db.query(Call).filter(Call.id.in_(request.call_ids)).all()
    
    if not calls:
        raise HTTPException(status_code=404, detail="No calls found")
    
    # Filter calls based on user permissions
    if current_user.is_superuser:
        # Admin can delete all calls
        calls_to_delete = calls
    else:
        # Regular users can only delete calls from their agents
        user_agent_ids = [agent_id for (agent_id,) in db.query(VoiceAgent.id).filter(
            VoiceAgent.user_id == current_user.id
        ).all()]
        calls_to_delete = [call for call in calls if call.agent_id in user_agent_ids]
    
    if not calls_to_delete:
        raise HTTPException(status_code=403, detail="Access denied to delete these calls")
    
    # Delete calls
    for call in calls_to_delete:
        db.delete(call)
    
    db.commit()
    
    return {
        "message": f"Successfully deleted {len(calls_to_delete)} call(s)",
        "deleted_count": len(calls_to_delete),
        "requested_count": len(request.call_ids)
    }


@router.post("/{call_id}/toggle-favorite", response_model=dict)
def toggle_favorite(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for a single call"""
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check access
    if not current_user.is_superuser:
        agent = db.query(VoiceAgent).filter(
            VoiceAgent.id == call.agent_id,
            VoiceAgent.user_id == current_user.id
        ).first()
        if not agent:
            raise HTTPException(status_code=403, detail="Access denied to this call")
    
    # Toggle favorite status
    call.is_favorite = not call.is_favorite
    db.commit()
    db.refresh(call)
    
    return {
        "id": call.id,
        "is_favorite": call.is_favorite,
        "message": f"Call {'added to' if call.is_favorite else 'removed from'} favorites"
    }


@router.post("/bulk/favorite", response_model=dict)
def bulk_toggle_favorite(
    request: BulkFavoriteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for multiple calls"""
    if not request.call_ids:
        raise HTTPException(status_code=400, detail="No call IDs provided")
    
    calls = db.query(Call).filter(Call.id.in_(request.call_ids)).all()
    
    if not calls:
        raise HTTPException(status_code=404, detail="No calls found")
    
    # Filter calls based on user permissions
    if current_user.is_superuser:
        calls_to_update = calls
    else:
        user_agent_ids = [agent_id for (agent_id,) in db.query(VoiceAgent.id).filter(
            VoiceAgent.user_id == current_user.id
        ).all()]
        calls_to_update = [call for call in calls if call.agent_id in user_agent_ids]
    
    if not calls_to_update:
        raise HTTPException(status_code=403, detail="Access denied to update these calls")
    
    # Update favorite status
    for call in calls_to_update:
        call.is_favorite = request.is_favorite
    
    db.commit()
    
    return {
        "message": f"Successfully {'added' if request.is_favorite else 'removed'} {len(calls_to_update)} call(s) {'to' if request.is_favorite else 'from'} favorites",
        "updated_count": len(calls_to_update),
        "requested_count": len(request.call_ids)
    }

