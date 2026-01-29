from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import logging
import asyncio

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
    caller_phone: Optional[str] = None  # Caller's phone number
    caller_name: Optional[str] = None  # Caller's name
    has_messages: bool = False  # Whether this call has text chat messages
    
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
    
    # Filter by action required using SQL-level filtering for performance
    # Uses callback_requested flag and JSONB operators for action_tags
    if action_required is not None:
        from sqlalchemy import text
        
        if action_required:
            # Filter calls that have action required:
            # 1. callback_requested is True, OR
            # 2. action_tags contains any tag with "request" (case-insensitive)
            query = query.filter(
                or_(
                    Call.callback_requested == True,
                    # PostgreSQL: check if any element in action_tags array contains 'request'
                    text("EXISTS (SELECT 1 FROM jsonb_array_elements_text(action_tags) AS tag WHERE LOWER(tag) LIKE '%request%')")
                )
            )
        else:
            # Filter calls without action required
            query = query.filter(
                Call.callback_requested != True,
                # Ensure no action_tags contain 'request'
                or_(
                    Call.action_tags == None,
                    text("NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(action_tags, '[]'::jsonb)) AS tag WHERE LOWER(tag) LIKE '%request%')")
                )
            )
    
    # Get total count before pagination
    total = query.count()
    
    # Calculate offset from page and per_page
    offset = (page - 1) * per_page
    
    # Apply pagination
    calls = query.order_by(desc(Call.created_at)).offset(offset).limit(per_page).all()
    
    # Check which calls have messages (for text chat detection)
    call_ids = [call.id for call in calls]
    calls_with_messages = set()
    if call_ids:
        try:
            message_counts = db.query(
                CallMessage.call_id,
                func.count(CallMessage.id).label('message_count')
            ).filter(
                CallMessage.call_id.in_(call_ids)
            ).group_by(CallMessage.call_id).all()
            
            calls_with_messages = {row.call_id for row in message_counts if row.message_count > 0}
            logger.debug(f"Found {len(calls_with_messages)} calls with messages out of {len(call_ids)} total calls")
        except Exception as e:
            logger.error(f"Error checking for messages: {e}")
            calls_with_messages = set()
    
    # Serialize calls and add has_messages flag
    serialized_calls = []
    for call in calls:
        call_dict = CallResponse.model_validate(call).model_dump()
        has_messages = call.id in calls_with_messages
        call_dict['has_messages'] = has_messages
        # Debug logging for text chat detection
        if has_messages and not call.transcript:
            logger.debug(f"Call {call.id} detected as text chat: has_messages={has_messages}, transcript={'present' if call.transcript else 'none'}")
        serialized_calls.append(call_dict)
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginatedCallResponse(
        items=serialized_calls,
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


async def generate_summary_background(call_id: int, user_id: int):
    """
    Background task to generate summary for a call.
    This runs independently and doesn't block the API response.
    """
    from app.models.database import SessionLocal
    
    # Create a new database session for the background task
    db = SessionLocal()
    try:
        logger.info(f"Starting background summary generation for call {call_id}")
        
        # Fetch the call
        call = db.query(Call).filter(
            Call.id == call_id,
            Call.user_id == user_id
        ).first()
        
        if not call:
            logger.error(f"Call {call_id} not found for user {user_id}")
            return
        
        if not call.transcript:
            logger.error(f"Call {call_id} has no transcript")
            # Update status to failed
            call.summarization_status = "failed"
            db.commit()
            
            # Broadcast update if websocket manager is available
            try:
                from app.api.websocket import call_monitor_manager
                call_data = {
                    "id": call.id,
                    "status": call.status.value if hasattr(call.status, 'value') else call.status,
                    "summarization_status": call.summarization_status,
                    "error": "No transcript available"
                }
                await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
            except Exception as e:
                logger.warning(f"Could not broadcast update: {e}")
            return
        
        # Set status to summarizing
        call.summarization_status = "summarizing"
        db.commit()
        
        # Broadcast status update
        try:
            from app.api.websocket import call_monitor_manager
            call_data = {
                "id": call.id,
                "status": call.status.value if hasattr(call.status, 'value') else call.status,
                "summarization_status": call.summarization_status
            }
            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        except Exception as e:
            logger.warning(f"Could not broadcast update: {e}")
        
        # Generate summary - this is the long-running operation
        # The database session will be released during the API call
        summary_service = CallSummaryService()
        result = await summary_service.generate_summary(call, db)
        
        # Check for errors
        if result.get("error"):
            logger.error(f"Summary generation failed for call {call_id}: {result.get('error')}")
            call.summarization_status = "failed"
        else:
            logger.info(f"Summary generated successfully for call {call_id}")
            call.summarization_status = "summarized"
        
        # Commit the results
        db.commit()
        db.refresh(call)
        
        # Send email notification with summary if successful
        if result.get("summary"):
            try:
                notification_service = get_notification_service()
                await notification_service.send_call_summary_email(db, call, result)
                logger.info(f"Email notification sent for call {call_id}")
            except Exception as e:
                logger.error(f"Failed to send email notification: {e}")
        
        # Broadcast final update with results
        try:
            from app.api.websocket import call_monitor_manager
            call_data = {
                "id": call.id,
                "status": call.status.value if hasattr(call.status, 'value') else call.status,
                "summarization_status": call.summarization_status,
                "summary": call.summary,
                "sentiment": call.sentiment,
                "key_points": call.key_points,
                "action_items": call.action_items,
                "action_tags": call.action_tags
            }
            await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
            logger.info(f"Broadcast final update for call {call_id}")
        except Exception as e:
            logger.warning(f"Could not broadcast final update: {e}")
            
    except Exception as e:
        logger.error(f"Error in background summary generation for call {call_id}: {e}", exc_info=True)
        # Try to update the call status to failed
        try:
            call = db.query(Call).filter(Call.id == call_id).first()
            if call:
                call.summarization_status = "failed"
                db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to update call status: {commit_error}")
    finally:
        db.close()
        logger.info(f"Background summary generation completed for call {call_id}")


@router.post("/{call_id}/generate-summary")
async def generate_summary(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI summary for a call (async/non-blocking).
    
    This endpoint triggers summary generation as a background task and returns immediately.
    The client can poll the call status or use WebSocket to get real-time updates.
    """
    # Validate the call exists and belongs to the user
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    if not call.transcript:
        raise HTTPException(status_code=400, detail="Transcript not available")
    
    # Check if summary is already being generated
    if call.summarization_status == "summarizing":
        return {
            "status": "in_progress",
            "message": "Summary generation is already in progress",
            "call_id": call_id,
            "summarization_status": call.summarization_status
        }
    
    # Set initial status
    call.summarization_status = "pending"
    db.commit()
    
    # Trigger background task - this doesn't block
    asyncio.create_task(generate_summary_background(call_id, current_user.id))
    
    logger.info(f"Triggered background summary generation for call {call_id}")
    
    # Return immediately with pending status
    return {
        "status": "pending",
        "message": "Summary generation started. Check back shortly for results.",
        "call_id": call_id,
        "summarization_status": "pending"
    }


@router.get("/{call_id}/summary-status")
async def get_summary_status(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check the status of summary generation for a call.
    
    Returns:
    - summarization_status: "pending", "summarizing", "summarized", "failed", or "not_summarized"
    - summary data if available
    """
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.user_id == current_user.id
    ).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    response = {
        "call_id": call_id,
        "summarization_status": call.summarization_status,
        "status": call.status.value if hasattr(call.status, 'value') else call.status
    }
    
    # Include summary data if available
    if call.summarization_status == "summarized":
        response.update({
            "summary": call.summary,
            "sentiment": call.sentiment,
            "key_points": call.key_points,
            "action_items": call.action_items,
            "action_tags": call.action_tags
        })
    
    return response


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
        from sqlalchemy.orm import noload
        
        # Admin users can see all calls, regular users see only their agents' calls
        # Use noload to prevent loading agent relationship (which would load PhoneNumber with missing sip_id column)
        if current_user.is_superuser:
            base_query = db.query(Call).options(noload(Call.agent))
        else:
            # Regular users see only calls from agents they created
            # Join with VoiceAgent but don't load the relationship to avoid PhoneNumber loading
            base_query = db.query(Call).join(VoiceAgent, Call.agent_id == VoiceAgent.id).filter(
                VoiceAgent.user_id == current_user.id
            ).options(noload(Call.agent))
        
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


# ============================================================================
# Outbound Calling
# ============================================================================

class OutboundCallRequest(BaseModel):
    """Request to initiate an outbound call"""
    from_phone_number: str  # Phone number to call from (must be registered)
    to_number: str  # Number to call
    agent_id: int  # AI agent to use
    script_id: Optional[int] = None  # Optional outbound script to use


class OutboundCallResponse(BaseModel):
    """Response for outbound call initiation"""
    success: bool
    message: str
    call_id: Optional[int] = None
    sip_call_id: Optional[str] = None
    status: Optional[str] = None
    from_number: Optional[str] = None
    to_number: Optional[str] = None
    agent_id: Optional[int] = None


@router.post("/outbound", response_model=OutboundCallResponse)
async def make_outbound_call(
    request: OutboundCallRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Initiate an outbound call using AI agent.
    
    The call will be placed from the specified phone number to the target number.
    Once the call is answered, the AI agent will handle the conversation.
    
    Requirements:
    - from_phone_number must be a registered phone number with SIP credentials
    - agent_id must be an agent owned by the current user (or any agent for admins)
    - The phone number's SIP client must be registered with the SIP server
    - script_id (optional) - an outbound script to use for the call
    """
    logger.info(f"Outbound call request: {request.from_phone_number} -> {request.to_number} (agent: {request.agent_id}, script: {request.script_id})")
    
    # Verify agent exists and user has access
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == request.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not current_user.is_superuser and agent.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this agent")
    
    # Get script if specified
    script_data = None
    if request.script_id:
        from app.models import OutboundScript
        script = db.query(OutboundScript).filter(
            OutboundScript.id == request.script_id,
            OutboundScript.agent_id == request.agent_id,
            OutboundScript.is_active == True
        ).first()
        
        if not script:
            raise HTTPException(status_code=404, detail="Script not found or inactive")
        
        # Record script use
        script.use_count += 1
        script.last_used_at = datetime.utcnow()
        db.commit()
        
        # Build script data for the call
        script_data = {
            "id": script.id,
            "name": script.name,
            "opening_message": script.opening_message,
            "main_content": script.main_content,
            "closing_message": script.closing_message,
            "tone": script.tone,
            "objective": script.objective,
            "key_points": script.key_points,
            "objection_handling": script.objection_handling
        }
        logger.info(f"Using outbound script: {script.name} (ID: {script.id})")
    
    # Import SIP call handler
    try:
        from app.services.sip_call_handler import sip_call_handler
    except ImportError as e:
        logger.error(f"Failed to import sip_call_handler: {e}")
        raise HTTPException(status_code=500, detail="SIP call handler not available")
    
    # Check if the from_phone_number is registered
    if request.from_phone_number not in sip_call_handler.sip_clients:
        # List available phone numbers for debugging
        available = list(sip_call_handler.sip_clients.keys())
        logger.error(f"Phone number {request.from_phone_number} not registered. Available SIP clients: {available}")
        
        # Try to find a similar number (might be format mismatch)
        requested_digits = ''.join(c for c in request.from_phone_number if c.isdigit())
        for avail_num in available:
            avail_digits = ''.join(c for c in avail_num if c.isdigit())
            if requested_digits == avail_digits or requested_digits.endswith(avail_digits) or avail_digits.endswith(requested_digits):
                logger.error(f"Found similar number: {avail_num} (requested: {request.from_phone_number})")
                # Use the matching number instead
                request.from_phone_number = avail_num
                break
        else:
            # No match found - provide helpful error
            raise HTTPException(
                status_code=400, 
                detail=f"Phone number {request.from_phone_number} is not registered for SIP calls. Available: {available}. Check if the phone has SIP credentials configured (sip_websocket_url, sip_username, sip_password, sip_domain)."
            )
    
    # Make the outbound call with optional script
    result = await sip_call_handler.make_outbound_call(
        from_phone_number=request.from_phone_number,
        to_number=request.to_number,
        agent_id=request.agent_id,
        user_id=current_user.id,
        script_data=script_data
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to initiate outbound call")
    
    logger.info(f"Outbound call initiated: {result}")
    
    return OutboundCallResponse(
        success=True,
        message="Outbound call initiated successfully",
        call_id=result.get("call_id"),
        sip_call_id=result.get("sip_call_id"),
        status=result.get("status"),
        from_number=result.get("from_number"),
        to_number=result.get("to_number"),
        agent_id=result.get("agent_id")
    )


@router.get("/outbound/sip-status")
async def get_sip_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to check SIP handler status.
    Shows which phone numbers are registered with the SIP handler.
    """
    try:
        from app.services.sip_call_handler import sip_call_handler
        
        registered = []
        for phone_num, client in sip_call_handler.sip_clients.items():
            phone_record = sip_call_handler.phone_records.get(phone_num)
            registered.append({
                "phone_number": phone_num,
                "is_registered": getattr(client, 'is_registered', False),
                "agent_id": phone_record.agent_id if phone_record else None,
                "sip_username": phone_record.sip_username if phone_record else None,
                "sip_domain": phone_record.sip_domain if phone_record else None
            })
        
        return {
            "sip_handler_active": True,
            "registered_count": len(registered),
            "registered_phones": registered,
            "message": "SIP handler is running" if registered else "No phones registered with SIP handler"
        }
    except Exception as e:
        logger.error(f"Error checking SIP status: {e}")
        return {
            "sip_handler_active": False,
            "registered_count": 0,
            "registered_phones": [],
            "message": f"SIP handler error: {str(e)}"
        }


@router.post("/outbound/sip-reload")
async def reload_sip_registrations(
    current_user: User = Depends(get_current_active_user)
):
    """
    Reload SIP phone registrations.
    Use this after adding/updating phone numbers with SIP credentials.
    Any authenticated user can trigger this to reload their own phone numbers.
    """
    try:
        from app.services.sip_call_handler import sip_call_handler
        
        await sip_call_handler.reload_phone_numbers()
        
        # Get updated status
        registered = list(sip_call_handler.sip_clients.keys())
        
        return {
            "success": True,
            "message": f"SIP registrations reloaded. {len(registered)} phone(s) registered.",
            "registered_phones": registered
        }
    except Exception as e:
        logger.error(f"Error reloading SIP registrations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload SIP: {str(e)}")


@router.get("/outbound/phone-numbers")
async def get_available_phone_numbers(
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of phone numbers available for outbound calls.
    
    Returns phone numbers from the database that are in ACTIVE or APPROVED status.
    If agent_id is provided, only returns phone numbers assigned to that agent.
    Also indicates if they're currently registered with the SIP server.
    """
    from app.models.zadarma import PhoneNumber, PhoneNumberStatus
    
    # Get registered SIP phone numbers (runtime)
    sip_registered = set()
    try:
        from app.services.sip_call_handler import sip_call_handler
        registered = sip_call_handler.get_registered_phone_numbers()
        sip_registered = {p["phone_number"] for p in registered}
    except (ImportError, Exception) as e:
        logger.warning(f"SIP call handler not available: {e}")
    
    # Query phone numbers from database
    query = db.query(PhoneNumber).filter(
        PhoneNumber.status.in_([PhoneNumberStatus.ACTIVE, PhoneNumberStatus.APPROVED])
    )
    
    # Filter by user's phone numbers (unless admin)
    if not current_user.is_superuser:
        query = query.filter(PhoneNumber.user_id == current_user.id)
    
    # Filter by agent if specified
    if agent_id is not None:
        query = query.filter(PhoneNumber.agent_id == agent_id)
    
    db_phones = query.all()
    
    phone_numbers = []
    for phone in db_phones:
        phone_numbers.append({
            "phone_number": phone.phone_number,
            "is_registered": phone.phone_number in sip_registered,
            "agent_id": phone.agent_id,
            "status": phone.status.value if hasattr(phone.status, 'value') else phone.status,
            "country_code": phone.country_code
        })
    
    return {
        "phone_numbers": phone_numbers,
        "count": len(phone_numbers)
    }


@router.post("/{call_id}/hangup")
async def hangup_call(
    call_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Hangup an active call.
    
    This can be used for both inbound and outbound calls that are currently in progress.
    """
    # Get the call
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
    
    # Check if call is active
    if call.status not in [CallStatus.INITIATED, CallStatus.IN_PROGRESS]:
        raise HTTPException(status_code=400, detail="Call is not active")
    
    # Get the SIP call ID
    sip_call_id = call.zadarma_call_id
    if not sip_call_id:
        raise HTTPException(status_code=400, detail="No SIP call ID found")
    
    try:
        from app.services.sip_call_handler import sip_call_handler
        
        # Find the SIP client that has this call
        for phone_number, sip_client in sip_call_handler.sip_clients.items():
            if sip_call_id in sip_client.active_calls:
                success = await sip_client.hangup_call(sip_call_id)
                if success:
                    return {"message": "Call hangup initiated", "call_id": call_id}
                else:
                    raise HTTPException(status_code=500, detail="Failed to hangup call")
        
        raise HTTPException(status_code=404, detail="Active SIP call not found")
        
    except ImportError:
        raise HTTPException(status_code=500, detail="SIP call handler not available")
