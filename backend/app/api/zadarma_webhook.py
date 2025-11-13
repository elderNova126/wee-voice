"""
Zadarma Webhook Handler
Handles incoming call notifications and events from Zadarma telephony service
"""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime

from app.models import get_db, Call, VoiceAgent, PhoneNumber, User, CallStatus
from app.core.config import settings
from app.services.notification_service import get_notification_service
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_zadarma_signature(payload: str, signature: str) -> bool:
    """
    Verify webhook signature from Zadarma
    
    Args:
        payload: Raw request body as string
        signature: Signature from X-Zadarma-Signature header
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.ZADARMA_API_SECRET:
        logger.warning("ZADARMA_API_SECRET not configured, skipping signature verification")
        return True  # In dev mode without credentials
    
    try:
        expected_signature = hmac.new(
            settings.ZADARMA_API_SECRET.encode(),
            payload.encode(),
            hashlib.sha1
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying Zadarma signature: {e}")
        return False


async def get_agent_for_phone_number(db: Session, phone_number: str) -> Optional[VoiceAgent]:
    """
    Get the voice agent assigned to a phone number
    
    Args:
        db: Database session
        phone_number: Called phone number
        
    Returns:
        VoiceAgent or None
    """
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number,
        PhoneNumber.agent_id.isnot(None)
    ).first()
    
    if phone_record and phone_record.agent:
        return phone_record.agent
    
    return None


async def create_call_record(
    db: Session,
    agent: VoiceAgent,
    caller_id: str,
    called_did: str,
    zadarma_call_id: str,
    event_type: str
) -> Call:
    """
    Create a call record in the database
    
    Args:
        db: Database session
        agent: Voice agent handling the call
        caller_id: Caller's phone number
        called_did: Called phone number (DID)
        zadarma_call_id: Zadarma's call ID
        event_type: Type of webhook event
        
    Returns:
        Created Call object
    """
    call = Call(
        user_id=agent.user_id,
        agent_id=agent.id,
        caller_phone=caller_id,
        caller_name=caller_id,  # Will be updated if caller provides name
        direction="inbound",
        status="initiated" if event_type == "NOTIFY_START" else "in_progress",
        zadarma_call_id=zadarma_call_id,
        started_at=datetime.utcnow()
    )
    
    db.add(call)
    db.commit()
    db.refresh(call)
    
    logger.info(f"Created call record: {call.id} for agent {agent.id}")
    return call


@router.post("/webhook")
async def zadarma_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle incoming webhooks from Zadarma
    
    Zadarma sends webhooks for various call events:
    - NOTIFY_START: Incoming call initiated
    - NOTIFY_ANSWER: Call was answered
    - NOTIFY_END: Call ended
    - NOTIFY_OUT_START: Outgoing call started
    - NOTIFY_OUT_END: Outgoing call ended
    - NOTIFY_RECORD: Call recording available
    """
    try:
        # Get raw body for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Verify signature
        signature = request.headers.get('X-Zadarma-Signature', '')
        if signature and not verify_zadarma_signature(body_str, signature):
            logger.error("Invalid Zadarma webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # Parse webhook data
        data = await request.json()
        event = data.get('event')
        zadarma_call_id = data.get('call_id', data.get('pbx_call_id'))
        caller_id = data.get('caller_id', data.get('from'))
        called_did = data.get('called_did', data.get('to'))
        
        logger.info(f"Zadarma webhook received: {event} for call {zadarma_call_id}")
        logger.info(f"From: {caller_id}, To: {called_did}")
        
        # Handle different event types
        if event == "NOTIFY_START":
            return await handle_call_start(db, data, caller_id, called_did, zadarma_call_id)
        
        elif event == "NOTIFY_ANSWER":
            return await handle_call_answer(db, data, zadarma_call_id)
        
        elif event == "NOTIFY_END":
            return await handle_call_end(db, data, zadarma_call_id)
        
        elif event == "NOTIFY_OUT_START":
            return await handle_outbound_start(db, data, zadarma_call_id)
        
        elif event == "NOTIFY_OUT_END":
            return await handle_outbound_end(db, data, zadarma_call_id)
        
        elif event == "NOTIFY_RECORD":
            return await handle_recording_available(db, data, zadarma_call_id)
        
        else:
            logger.warning(f"Unknown Zadarma event type: {event}")
            return {"status": "ok", "message": f"Event {event} acknowledged but not handled"}
    
    except Exception as e:
        logger.error(f"Error processing Zadarma webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


async def handle_call_start(
    db: Session,
    data: Dict[str, Any],
    caller_id: str,
    called_did: str,
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle incoming call start (NOTIFY_START)"""
    
    # Find agent assigned to this phone number
    agent = await get_agent_for_phone_number(db, called_did)
    
    if not agent:
        logger.warning(f"No agent found for phone number {called_did}")
        return {
            "status": "error",
            "message": f"No agent configured for number {called_did}"
        }
    
    # Create call record
    call = await create_call_record(
        db, agent, caller_id, called_did, zadarma_call_id, "NOTIFY_START"
    )
    
    # Send notification to user
    notification_service = get_notification_service()
    try:
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            await notification_service.send_call_notification(db, call, "incoming")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
    
    # Return response to Zadarma
    # You can include instructions for call handling here
    return {
        "status": "ok",
        "call_id": call.id,
        "message": "Call initiated successfully",
        # Optional: Provide SIP/WebRTC connection details for the agent
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "greeting": agent.greeting
        }
    }


async def handle_call_answer(
    db: Session,
    data: Dict[str, Any],
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle call answered event (NOTIFY_ANSWER)"""
    
    # Find call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if call:
        call.status = "in_progress"
        if not call.started_at:
            call.started_at = datetime.utcnow()
        db.commit()
        logger.info(f"Call {call.id} answered")
    
    return {"status": "ok", "message": "Call answer recorded"}


async def handle_call_end(
    db: Session,
    data: Dict[str, Any],
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle call end event (NOTIFY_END)"""
    
    # Find call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if not call:
        logger.warning(f"Call record not found for Zadarma call {zadarma_call_id}")
        return {"status": "ok", "message": "Call not found"}
    
    # Update call record
    call.status = CallStatus.SUMMARIZING  # Set to summarizing immediately
    call.ended_at = datetime.utcnow()
    
    # Extract call details from webhook data
    disposition = data.get('disposition', 'unknown')
    call_duration = data.get('duration', 0)
    
    call.disposition = disposition
    
    if call.started_at and call.ended_at:
        duration = (call.ended_at - call.started_at).total_seconds()
        call.duration = int(duration)
    elif call_duration:
        call.duration = int(call_duration)
    
    # Calculate cost
    if call.duration:
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == call.agent_id).first()
        if agent:
            cost_per_minute = float(getattr(settings, 'COST_PER_MINUTE', 0.05))
            call.cost = (call.duration / 60.0) * cost_per_minute
    
    db.commit()
    
    logger.info(f"Call {call.id} ended. Duration: {call.duration}s, Cost: ${call.cost}, Status set to summarizing")
    
    # Start background summarization task
    from app.api.websocket import auto_summarize_call
    asyncio.create_task(auto_summarize_call(call.id))
    logger.info(f"Started background summarization task for call {call.id}")
    
    # Send completion notification
    notification_service = get_notification_service()
    try:
        user = db.query(User).filter(User.id == call.user_id).first()
        if user and user.email:
            await notification_service.send_call_notification(db, call, "completed")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
    
    return {
        "status": "ok",
        "call_id": call.id,
        "duration": call.duration,
        "cost": call.cost
    }


async def handle_outbound_start(
    db: Session,
    data: Dict[str, Any],
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle outbound call start (NOTIFY_OUT_START)"""
    
    logger.info(f"Outbound call started: {zadarma_call_id}")
    
    # Find or create call record for outbound call
    # This would be used if you implement callback functionality
    
    return {"status": "ok", "message": "Outbound call started"}


async def handle_outbound_end(
    db: Session,
    data: Dict[str, Any],
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle outbound call end (NOTIFY_OUT_END)"""
    
    logger.info(f"Outbound call ended: {zadarma_call_id}")
    
    return {"status": "ok", "message": "Outbound call ended"}


async def handle_recording_available(
    db: Session,
    data: Dict[str, Any],
    zadarma_call_id: str
) -> Dict[str, Any]:
    """Handle call recording available (NOTIFY_RECORD)"""
    
    # Find call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if not call:
        logger.warning(f"Call record not found for recording {zadarma_call_id}")
        return {"status": "ok", "message": "Call not found"}
    
    # Get recording URL from webhook data
    recording_url = data.get('call_record', data.get('record_url'))
    
    if recording_url:
        call.recording_url = recording_url
        db.commit()
        logger.info(f"Recording URL saved for call {call.id}: {recording_url}")
        
        # Optional: Download and store recording locally
        # from app.services.storage_service import get_storage_service
        # storage_service = get_storage_service()
        # await storage_service.download_and_store_recording(call.id, recording_url)
    
    return {"status": "ok", "message": "Recording URL saved"}


@router.get("/health")
async def webhook_health():
    """Health check endpoint for Zadarma webhook"""
    return {
        "status": "healthy",
        "service": "zadarma_webhook",
        "timestamp": datetime.utcnow().isoformat()
    }

