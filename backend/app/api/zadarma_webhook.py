"""
Zadarma Webhook Handler
Handles incoming call notifications and events from Zadarma telephony service
"""
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime

from app.models import get_db, Call, VoiceAgent, PhoneNumber, User
from app.models.call import CallStatus
from app.core.config import settings
from app.core.security import get_current_user
from app.services.notification_service import get_notification_service
from app.api.websocket import call_monitor_manager
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


def normalize_phone_for_matching(phone: str) -> str:
    """
    Normalize phone number for database matching
    Removes spaces, dashes, parentheses, and ensures consistent format
    """
    if not phone:
        return ""
    # Remove all non-digit characters except +
    normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    # Ensure + prefix for international format
    if normalized and not normalized.startswith("+"):
        # If it starts with 00, replace with +
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
    return normalized


async def get_agent_for_phone_number(db: Session, phone_number: str) -> Optional[VoiceAgent]:
    """
    Get the voice agent assigned to a phone number
    
    Args:
        db: Database session
        phone_number: Called phone number
        
    Returns:
        VoiceAgent or None
    """
    # Normalize the incoming phone number
    normalized_incoming = normalize_phone_for_matching(phone_number)
    logger.info(f"Looking up agent for phone number: {phone_number} (normalized: {normalized_incoming})")
    
    # Try exact match first
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number,
        PhoneNumber.agent_id.isnot(None)
    ).first()
    
    if phone_record and phone_record.agent:
        logger.info(f"Found agent {phone_record.agent.id} for phone {phone_number} (exact match)")
        return phone_record.agent
    
    # Try normalized match
    if normalized_incoming != phone_number:
        # Get all phone numbers and compare normalized versions
        all_phones = db.query(PhoneNumber).filter(
            PhoneNumber.agent_id.isnot(None)
        ).all()
        
        for phone in all_phones:
            normalized_stored = normalize_phone_for_matching(phone.phone_number)
            # Compare last 9-10 digits (typical phone number length without country code)
            incoming_digits = ''.join(filter(str.isdigit, normalized_incoming))
            stored_digits = ''.join(filter(str.isdigit, normalized_stored))
            
            if len(incoming_digits) >= 9 and len(stored_digits) >= 9:
                # Compare last 9-10 digits
                if incoming_digits[-9:] == stored_digits[-9:] or incoming_digits[-10:] == stored_digits[-10:]:
                    logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (normalized match: {phone.phone_number})")
                    return phone.agent
            
            # Also try exact normalized match
            if normalized_incoming == normalized_stored:
                logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (normalized exact match: {phone.phone_number})")
                return phone.agent
    
    logger.warning(f"No agent found for phone number: {phone_number} (normalized: {normalized_incoming})")
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
        
        # Extract phone numbers - Zadarma may send them in different fields
        # Try multiple possible field names
        caller_id = (
            data.get('caller_id') or 
            data.get('from') or 
            data.get('caller') or 
            data.get('caller_number') or
            data.get('callerid') or
            ''
        )
        called_did = (
            data.get('called_did') or 
            data.get('to') or 
            data.get('called') or 
            data.get('called_number') or
            data.get('did') or
            ''
        )
        
        # Log all webhook data for debugging
        logger.info(f"Zadarma webhook received: {event} for call {zadarma_call_id}")
        logger.info(f"Full webhook data: {data}")
        logger.info(f"Extracted - From: {caller_id}, To: {called_did}")
        
        # Normalize phone numbers
        def normalize_phone_number(phone: str) -> str:
            """Normalize phone number to E.164 format"""
            if not phone:
                return ""
            # Remove all non-digit characters except +
            normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
            # Ensure + prefix for international format
            if normalized and not normalized.startswith("+"):
                # If it starts with 00, replace with +
                if normalized.startswith("00"):
                    normalized = "+" + normalized[2:]
                # Otherwise, try to add country code (this is a fallback)
                # For now, just return as-is if no + prefix
            return normalized
        
        caller_id = normalize_phone_number(caller_id)
        called_did = normalize_phone_number(called_did)
        
        logger.info(f"Normalized - From: {caller_id}, To: {called_did}")
        
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
    
    # Start voice session for phone call
    # This sets up the audio bridge between Zadarma and Gemini
    try:
        from app.services.agent_service import FrenchVoiceAgentService
        from app.api.websocket import manager
        from app.services.phone_audio_bridge import phone_audio_manager
        
        # Generate a session ID for this phone call
        import uuid
        session_id = call.session_id or f"phone_{zadarma_call_id}_{uuid.uuid4().hex[:8]}"
        call.session_id = session_id
        db.commit()
        db.refresh(call)
        
        # Initialize agent service
        agent_service = FrenchVoiceAgentService(agent, call)
        manager.agent_services[session_id] = agent_service
        
        # Start the voice session (this will trigger the greeting)
        await agent_service.start_session()
        logger.info(f"Started voice session for phone call {call.id} with session {session_id}")
        
        # Create and start phone audio bridge
        # This handles bidirectional audio streaming between Zadarma and Gemini
        bridge = await phone_audio_manager.create_bridge(
            agent_service,
            str(call.id),
            zadarma_call_id
        )
        logger.info(f"Started phone audio bridge for call {call.id}")
        
    except Exception as e:
        logger.error(f"Failed to start voice session for phone call {call.id}: {e}", exc_info=True)
        # Continue anyway - the call record is created
    
    # Send notification to user
    notification_service = get_notification_service()
    try:
        user = db.query(User).filter(User.id == agent.user_id).first()
        if user and user.email:
            await notification_service.send_call_notification(db, call, "incoming")
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
    
    # Return response to Zadarma with audio streaming endpoints
    from app.core.config import settings
    
    # Provide audio streaming endpoints for Zadarma to use
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    api_prefix = settings.API_V1_STR
    
    return {
        "status": "ok",
        "call_id": call.id,
        "message": "Call initiated successfully, audio bridge ready",
        "session_id": call.session_id,
        # Audio streaming endpoints for Zadarma
        "audio": {
            "input_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/input",
            "output_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/output",
            "end_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/end",
            "format": "audio/pcm;rate=16000",  # Input format (caller's voice)
            "output_format": "audio/pcm;rate=24000"  # Output format (AI responses)
        },
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
    
    # Stop phone audio bridge
    try:
        from app.services.phone_audio_bridge import phone_audio_manager
        await phone_audio_manager.end_bridge(str(call.id))
        logger.info(f"Stopped phone audio bridge for call {call.id}")
    except Exception as e:
        logger.error(f"Error stopping phone audio bridge: {e}", exc_info=True)
    
    # Update call record
    call.status = CallStatus.SUMMARIZING  # Set to summarizing immediately
    call.ended_at = datetime.utcnow()
    
    # Extract call details from webhook data
    disposition = data.get('disposition', 'unknown')
    call_duration = data.get('duration', 0)
    
    call.disposition = disposition
    
    if call.started_at and call.ended_at:
        duration = (call.ended_at - call.started_at).total_seconds()
        # Ensure duration is never negative
        duration = max(0.0, duration)
        call.duration = int(duration)
        call.duration_seconds = duration
        call.duration_minutes = duration / 60.0
    elif call_duration:
        call_duration = max(0, int(call_duration))
        call.duration = call_duration
        call.duration_seconds = float(call_duration)
        call.duration_minutes = call.duration_seconds / 60.0
    
    # Calculate cost
    if call.duration and call.duration > 0:
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == call.agent_id).first()
        if agent:
            cost_per_minute = float(getattr(settings, 'COST_PER_MINUTE', 0.05))
            call.cost = max(0.0, call.duration_minutes * cost_per_minute)
    
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


@router.post("/test-call")
async def simulate_test_call(
    phone_number: str = Query(..., description="Phone number to test (e.g., +3242833288)"),
    caller_id: str = Query("+33123456789", description="Simulated caller phone number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simulate a test call to a phone number for testing purposes.
    This creates a call record and tests the webhook flow without requiring an actual phone call.
    
    Args:
        phone_number: The phone number to test (e.g., +3242833288)
        caller_id: Simulated caller phone number (default: +33123456789)
        current_user: Current authenticated user
        db: Database session
    
    Returns:
        Call record and agent information
    """
    logger.info(f"Simulating test call to {phone_number} from {caller_id}")
    
    # Find agent assigned to this phone number
    agent = await get_agent_for_phone_number(db, phone_number)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No agent found for phone number {phone_number}. Please assign an agent to this number first."
        )
    
    # Create a simulated call ID
    zadarma_call_id = f"TEST_{datetime.utcnow().timestamp()}"
    
    # Step 1: Create call record and start audio bridge (NOTIFY_START)
    # Use handle_call_start to properly initialize the audio bridge
    call_data = {
        "caller_id": caller_id,
        "called_did": phone_number,
        "call_id": zadarma_call_id,
        "pbx_call_id": zadarma_call_id
    }
    
    # Call handle_call_start to set up the full call infrastructure
    result = await handle_call_start(db, call_data, caller_id, phone_number, zadarma_call_id)
    call = db.query(Call).filter(Call.zadarma_call_id == zadarma_call_id).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create call record"
        )
    
    logger.info(f"Test call record created: Call ID {call.id} for agent {agent.id} (status: {call.status})")
    logger.info(f"Audio bridge created: {result.get('audio', {}).get('input_url', 'N/A')}")
    
    # Broadcast initial call creation
    try:
        call_data = {
            "id": call.id,
            "status": call.status.value if hasattr(call.status, 'value') else str(call.status),
            "agent_id": call.agent_id,
            "session_id": call.session_id or "",  # Empty string instead of null for frontend compatibility
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": None,
            "duration_seconds": call.duration_seconds or 0.0,
            "duration_minutes": call.duration_minutes or 0.0,
            "cost": call.cost or 0.0,
            "is_favorite": call.is_favorite or False,
        }
        await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        logger.info(f"Broadcasted test call creation: Call ID {call.id}")
    except Exception as e:
        logger.error(f"Error broadcasting test call creation: {e}")
    
    # Step 2: Simulate call answered (NOTIFY_ANSWER) - happens after a delay
    await asyncio.sleep(2)  # 2 second delay to allow user to see "initiated" status
    call.status = CallStatus.IN_PROGRESS
    if not call.started_at:
        call.started_at = datetime.utcnow()
    db.commit()
    db.refresh(call)
    logger.info(f"Test call answered: Call ID {call.id} (status: {call.status})")
    
    # Broadcast call answered update
    try:
        call_data = {
            "id": call.id,
            "status": call.status.value if hasattr(call.status, 'value') else str(call.status),
            "agent_id": call.agent_id,
            "session_id": call.session_id or "",  # Empty string instead of null for frontend compatibility
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": None,
            "duration_seconds": call.duration_seconds or 0.0,
            "duration_minutes": call.duration_minutes or 0.0,
            "cost": call.cost or 0.0,
            "is_favorite": call.is_favorite or False,
        }
        await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        logger.info(f"Broadcasted test call answered: Call ID {call.id}")
    except Exception as e:
        logger.error(f"Error broadcasting test call answered: {e}")
    
    # Step 3: Simulate call ended (NOTIFY_END) - after a longer duration
    await asyncio.sleep(3)  # 3 second call duration so user can see "in_progress" status
    call.status = CallStatus.COMPLETED
    call.ended_at = datetime.utcnow()
    
    # Calculate duration
    if call.started_at and call.ended_at:
        duration = (call.ended_at - call.started_at).total_seconds()
        duration = max(0.0, duration)
        call.duration = int(duration)
        call.duration_seconds = duration
        call.duration_minutes = duration / 60.0
    
    # Calculate cost
    if call.duration and call.duration > 0:
        cost_per_minute = float(getattr(settings, 'COST_PER_MINUTE', 0.05))
        call.cost = max(0.0, call.duration_minutes * cost_per_minute)
    
    call.disposition = "answered"
    db.commit()
    db.refresh(call)
    logger.info(f"Test call ended: Call ID {call.id} (status: {call.status}, duration: {call.duration}s)")
    
    # Broadcast call completed update
    try:
        call_data = {
            "id": call.id,
            "status": call.status.value if hasattr(call.status, 'value') else str(call.status),
            "agent_id": call.agent_id,
            "session_id": call.session_id or "",  # Empty string instead of null for frontend compatibility
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "duration_seconds": call.duration_seconds or 0.0,
            "duration_minutes": call.duration_minutes or 0.0,
            "cost": call.cost or 0.0,
            "is_favorite": call.is_favorite or False,
            "disposition": call.disposition,
        }
        await call_monitor_manager.broadcast_call_update(call.user_id, call_data)
        logger.info(f"Broadcasted test call completed: Call ID {call.id}")
    except Exception as e:
        logger.error(f"Error broadcasting test call completed: {e}")
    
    # Get audio bridge status
    audio_status = None
    try:
        from app.services.phone_audio_bridge import phone_audio_manager
        bridge = phone_audio_manager.get_bridge(str(call.id))
        if bridge:
            audio_status = {
                "is_running": bridge.is_running,
                "queue_size": bridge.gemini_audio_queue.qsize()
            }
    except Exception as e:
        logger.warning(f"Could not get audio bridge status: {e}")
    
    # Get audio endpoints from the result
    audio_endpoints = result.get('audio', {}) if result else {}
    
    return {
        "status": "success",
        "message": "Test call simulated successfully - call progressed through all states. Audio bridge is ready for testing.",
        "call": {
            "id": call.id,
            "caller_phone": caller_id,
            "called_number": phone_number,
            "status": call.status,
            "duration": call.duration,
            "duration_seconds": call.duration_seconds,
            "cost": call.cost,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "session_id": call.session_id
        },
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "greeting": agent.greeting
        },
        "audio": {
            **audio_endpoints,
            "status": audio_status,
            "test_endpoints": {
                "input": f"/api/v1/phone/audio/{call.id}/input",
                "output": f"/api/v1/phone/audio/{call.id}/output",
                "status": f"/api/v1/phone/audio/{call.id}/status"
            }
        },
        "note": "This is a simulated call that progressed through: initiated → in_progress → completed. The audio bridge is active and ready for testing. You can test audio streaming using the endpoints above."
    }
