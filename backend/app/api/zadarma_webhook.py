"""
Zadarma Webhook Handler
Handles incoming call notifications and events from Zadarma telephony service
"""
import logging
import hmac
import hashlib
import json
import base64
from fastapi import APIRouter, Request, HTTPException, Depends, status, Query, Form
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, Union
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
    Verify webhook signature from Zadarma (for JSON webhooks)
    
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


def verify_pbx_signature(
    caller_id: str,
    called_did: str,
    call_start: str,
    signature: str
) -> bool:
    """
    Verify PBX extension webhook signature from Zadarma
    
    For PBX extension webhooks, Zadarma uses a different signature format:
    base64(hash_hmac('sha1', caller_id + called_did + call_start, API_SECRET))
    
    Args:
        caller_id: Caller's phone number
        called_did: Called phone number
        call_start: Call start time
        signature: Base64-encoded signature from webhook
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.ZADARMA_API_SECRET:
        logger.warning("ZADARMA_API_SECRET not configured, skipping signature verification")
        return True  # In dev mode without credentials
    
    try:
        # Create the message string: caller_id + called_did + call_start
        message = str(caller_id) + str(called_did) + str(call_start)
        
        # Generate HMAC-SHA1 signature
        expected_signature_bytes = hmac.new(
            settings.ZADARMA_API_SECRET.encode(),
            message.encode(),
            hashlib.sha1
        ).digest()
        
        # Encode to base64
        expected_signature = base64.b64encode(expected_signature_bytes).decode()
        
        # Compare signatures (case-insensitive, as Zadarma may send different case)
        return hmac.compare_digest(expected_signature.lower(), signature.lower())
    except Exception as e:
        logger.error(f"Error verifying PBX signature: {e}")
        return False


def normalize_phone_for_matching(phone: str) -> str:
    """
    Normalize phone number for database matching
    Removes spaces, dashes, parentheses, and ensures consistent format
    This is used to match incoming calls with stored phone numbers
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters except +
    normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").strip()
    
    if not normalized:
        return ""
    
    # Ensure + prefix for international format
    if not normalized.startswith("+"):
        # If it starts with 00, replace with +
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
        # If it starts with country code (e.g., 32 for Belgium), add +
        # Belgian numbers: 32XXXXXXXX (10 digits total)
        elif normalized.startswith("32") and len(normalized) >= 10:
            normalized = "+" + normalized
        # For other cases without +, keep as-is for now
        # We'll do digit-only comparison later
    
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
    
    # Get all phone numbers with agents for debugging
    all_phones = db.query(PhoneNumber).filter(
        PhoneNumber.agent_id.isnot(None)
    ).all()
    
    logger.info(f"Available phone numbers in database: {[p.phone_number for p in all_phones]}")
    
    # Try exact match first
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == phone_number,
        PhoneNumber.agent_id.isnot(None)
    ).first()
    
    if phone_record and phone_record.agent:
        logger.info(f"Found agent {phone_record.agent.id} for phone {phone_number} (exact match)")
        return phone_record.agent
    
    # Try normalized match - compare with all stored numbers
    for phone in all_phones:
        normalized_stored = normalize_phone_for_matching(phone.phone_number)
        logger.debug(f"Comparing: incoming='{normalized_incoming}' with stored='{normalized_stored}' (original: '{phone.phone_number}')")
        
        # Try exact normalized match first
        if normalized_incoming == normalized_stored:
            logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (normalized exact match: stored={phone.phone_number})")
            return phone.agent
        
        # Extract digits only for comparison
        incoming_digits = ''.join(filter(str.isdigit, normalized_incoming))
        stored_digits = ''.join(filter(str.isdigit, normalized_stored))
        
        logger.debug(f"Digit comparison: incoming_digits='{incoming_digits}', stored_digits='{stored_digits}'")
        
        # Compare full digits if they match
        if incoming_digits == stored_digits:
            logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (digit match: stored={phone.phone_number})")
            return phone.agent
        
        # Compare last 9-10 digits (typical phone number length without country code)
        if len(incoming_digits) >= 9 and len(stored_digits) >= 9:
            # Try last 9 digits
            if incoming_digits[-9:] == stored_digits[-9:]:
                logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (last 9 digits match: stored={phone.phone_number})")
                return phone.agent
            # Try last 10 digits
            if len(incoming_digits) >= 10 and len(stored_digits) >= 10:
                if incoming_digits[-10:] == stored_digits[-10:]:
                    logger.info(f"Found agent {phone.agent.id} for phone {phone_number} (last 10 digits match: stored={phone.phone_number})")
                    return phone.agent
    
    logger.warning(f"No agent found for phone number: {phone_number} (normalized: {normalized_incoming})")
    logger.warning(f"Searched against {len(all_phones)} phone numbers in database")
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
        caller_phone=caller_id,  # The number calling FROM (caller's phone)
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
    logger.info(f"Call details - Caller: {caller_id}, Called: {called_did}, Stored caller_phone: {call.caller_phone}")
    return call


@router.get("/webhook")
async def zadarma_webhook_get(
    request: Request,
    zd_echo: Optional[str] = Query(None, alias="zd_echo")
):
    """
    Handle GET requests from Zadarma for webhook verification (echo test)
    
    Zadarma sends a GET request with ?zd_echo=<value> to verify the webhook endpoint.
    We must return the same value as plain text (not JSON) to confirm the endpoint is working.
    
    This is equivalent to the PHP code:
    <?php if (isset($_GET['zd_echo'])) exit($_GET['zd_echo']); ?>
    """
    if zd_echo:
        logger.info(f"Zadarma echo verification received: {zd_echo}")
        # Return the raw string value as plain text (not JSON)
        # This is what Zadarma expects for echo verification
        return Response(content=zd_echo, media_type="text/plain")
    else:
        return {"status": "ok", "message": "Zadarma webhook endpoint is active"}


@router.post("/webhook")
async def zadarma_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle incoming webhooks from Zadarma
    
    Supports both JSON webhooks (standard) and form-encoded webhooks (PBX extensions).
    
    Zadarma sends webhooks for various call events:
    - NOTIFY_START: Incoming call initiated (can return call flow control)
    - NOTIFY_INTERNAL: Internal call to PBX extension
    - NOTIFY_ANSWER: Call was answered
    - NOTIFY_END: Call ended
    - NOTIFY_OUT_START: Outgoing call started
    - NOTIFY_OUT_END: Outgoing call ended
    - NOTIFY_RECORD: Call recording available
    - NOTIFY_IVR: Caller response to IVR action (can return call flow control)
    """
    try:
        # Get content type to determine if it's JSON or form data
        content_type = request.headers.get('content-type', '').lower()
        is_form_data = 'application/x-www-form-urlencoded' in content_type or 'multipart/form-data' in content_type
        
        # Parse webhook data based on content type
        if is_form_data:
            # PBX extension webhooks use form data
            form_data = await request.form()
            data = dict(form_data)
            
            # Extract event and parameters
            event = data.get('event', '')
            caller_id = data.get('caller_id', '')
            called_did = data.get('called_did', data.get('destination', ''))
            call_start = data.get('call_start', '')
            zadarma_call_id = data.get('pbx_call_id', data.get('call_id', ''))
            
            # Verify PBX signature
            signature = request.headers.get('X-Zadarma-Signature', '')
            if signature and not verify_pbx_signature(caller_id, called_did, call_start, signature):
                logger.error("Invalid PBX webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
            
            logger.info(f"PBX webhook received: {event} for call {zadarma_call_id}")
            logger.info(f"PBX webhook data: {data}")
        else:
            # Standard JSON webhooks
            # Get raw body for signature verification (must be done before parsing JSON)
            body_bytes = await request.body()
            body_str = body_bytes.decode('utf-8')
            
            try:
                # Parse JSON from the body string we already read
                data = json.loads(body_str)
            except json.JSONDecodeError:
                # Fallback: try to parse as form data if JSON fails
                # Note: This won't work if we already read the body, so we'll use the body_str
                # For form data, we'd need to parse it manually or use a different approach
                logger.warning("Failed to parse as JSON, attempting form data parsing")
                # Try to parse as URL-encoded form data
                from urllib.parse import parse_qs
                form_data = parse_qs(body_str)
                data = {k: v[0] if v else '' for k, v in form_data.items()}
                is_form_data = True
            
            event = data.get('event', '')
            zadarma_call_id = data.get('call_id', data.get('pbx_call_id', ''))
            
            # Verify signature for JSON webhooks
            signature = request.headers.get('X-Zadarma-Signature', '')
            if signature and not verify_zadarma_signature(body_str, signature):
                logger.error("Invalid Zadarma webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
            
            # Extract phone numbers - Zadarma may send them in different fields
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
                data.get('destination') or
                ''
            )
            call_start = data.get('call_start', '')
            
            logger.info(f"Zadarma webhook received: {event} for call {zadarma_call_id}")
            logger.info(f"Full webhook data: {json.dumps(data, indent=2)}")
        
        # Normalize phone numbers - more comprehensive normalization
        def normalize_phone_number(phone: str) -> str:
            """Normalize phone number to E.164 format"""
            if not phone:
                return ""
            
            # Remove all non-digit characters except +
            normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").strip()
            
            if not normalized:
                return ""
            
            # Handle different formats
            # If it starts with 00, replace with +
            if normalized.startswith("00"):
                normalized = "+" + normalized[2:]
            # If it starts with +, keep it
            elif normalized.startswith("+"):
                pass  # Already has +
            # If it's a number without +, check if it needs country code
            # For Belgian numbers (32), if it starts with 32 and is 10+ digits, add +
            elif normalized.startswith("32") and len(normalized) >= 10:
                normalized = "+" + normalized
            # If it's 9 digits and starts with 4 (Belgian mobile), might be missing country code
            # But we'll leave it as-is to preserve what Zadarma sent
            
            return normalized
        
        caller_id = normalize_phone_number(caller_id)
        called_did = normalize_phone_number(called_did)
        
        logger.info(f"Normalized - From: {caller_id}, To: {called_did}")
        
        # Handle different event types
        if event == "NOTIFY_START":
            return await handle_call_start(db, data, caller_id, called_did, zadarma_call_id)
        
        elif event == "NOTIFY_INTERNAL":
            return await handle_internal_call(db, data, caller_id, called_did, zadarma_call_id)
        
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
        
        elif event == "NOTIFY_IVR":
            return await handle_ivr_response(db, data, caller_id, called_did, zadarma_call_id)
        
        else:
            logger.warning(f"Unknown Zadarma event type: {event}")
            return {"status": "ok", "message": f"Event {event} acknowledged but not handled"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Zadarma webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


def build_call_flow_response(
    response_type: str,
    value: Any = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Build call flow control response for NOTIFY_START and NOTIFY_IVR
    
    Supported response types:
    - "redirect": Redirect to extension/scenario (value: extension/scenario ID)
    - "hangup": End the call (value: 1)
    - "caller_name": Set caller name (value: name string)
    - "wait_dtmf": Wait for DTMF input (value: dict with timeout, attempts, etc.)
    - "ivr_play": Play audio file (value: file ID)
    - "ivr_saypopular": Play popular phrase (value: phrase number, language: "en"/"ru"/"es"/"pl")
    - "ivr_saydigits": Play digits (value: digits string, language: "en"/"ru"/"es"/"pl")
    - "ivr_saynumber": Play number (value: number string, language: "en"/"ru"/"es"/"pl")
    
    Returns:
        Dict with appropriate response structure for Zadarma
    """
    if response_type == "redirect":
        response = {"redirect": value}
        if "return_timeout" in kwargs:
            response["return_timeout"] = kwargs["return_timeout"]
        if "rewrite_forward_number" in kwargs:
            response["rewrite_forward_number"] = kwargs["rewrite_forward_number"]
        return response
    
    elif response_type == "hangup":
        return {"hangup": 1}
    
    elif response_type == "caller_name":
        return {"caller_name": value}
    
    elif response_type == "wait_dtmf":
        return {"wait_dtmf": value if isinstance(value, dict) else kwargs}
    
    elif response_type == "ivr_play":
        return {"ivr_play": value}
    
    elif response_type == "ivr_saypopular":
        response = {"ivr_saypopular": value if value is not None else 1}
        if "language" in kwargs:
            response["language"] = kwargs["language"]
        return response
    
    elif response_type == "ivr_saydigits":
        response = {"ivr_saydigits": value}
        if "language" in kwargs:
            response["language"] = kwargs["language"]
        return response
    
    elif response_type == "ivr_saynumber":
        response = {"ivr_saynumber": value}
        if "language" in kwargs:
            response["language"] = kwargs["language"]
        return response
    
    else:
        logger.warning(f"Unknown call flow response type: {response_type}")
        return {}


async def handle_call_start(
    db: Session,
    data: Dict[str, Any],
    caller_id: str,
    called_did: str,
    zadarma_call_id: str
) -> Dict[str, Any]:
    """
    Handle incoming call start (NOTIFY_START)
    
    For PBX extension webhooks, this can return call flow control responses:
    - redirect: Redirect to extension/scenario
    - hangup: End the call
    - caller_name: Set caller name
    - wait_dtmf: Wait for DTMF input
    - ivr_play: Play audio file
    - ivr_saypopular: Play popular phrase
    - ivr_saydigits: Play digits
    - ivr_saynumber: Play number
    
    Currently, we return audio streaming endpoints for direct call handling.
    You can modify this to return call flow control responses if needed.
    """
    
    # Find agent assigned to this phone number
    agent = await get_agent_for_phone_number(db, called_did)
    
    if not agent:
        logger.warning(f"No agent found for phone number {called_did}")
        # Option: Return hangup response to reject the call
        # return build_call_flow_response("hangup")
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
    
    # Return response to Zadarma
    # For PBX extension webhooks, you can return call flow control responses.
    # For now, we return a standard response with audio endpoints.
    # 
    # Example: To redirect to an extension instead:
    # return build_call_flow_response("redirect", "2001")  # Redirect to extension 2001
    #
    # Example: To play a greeting and wait for DTMF:
    # return {
    #     "ivr_saypopular": 1,
    #     "language": "en",
    #     "wait_dtmf": {
    #         "timeout": 10,
    #         "attempts": 3,
    #         "maxdigits": 1,
    #         "name": "menu_choice"
    #     }
    # }
    
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


async def handle_internal_call(
    db: Session,
    data: Dict[str, Any],
    caller_id: str,
    called_did: str,
    zadarma_call_id: str
) -> Dict[str, Any]:
    """
    Handle internal call to PBX extension (NOTIFY_INTERNAL)
    
    This event is triggered when a call is routed to a PBX extension.
    Parameters:
    - event: NOTIFY_INTERNAL
    - call_start: Call start time
    - pbx_call_id: Call ID
    - caller_id: Caller's phone number
    - called_did: Called phone number
    - internal: (optional) Extension number
    - transfer_from: (optional) Transfer initiator, extension
    - transfer_type: (optional) Transfer type
    """
    logger.info(f"Internal PBX call received: {zadarma_call_id}")
    logger.info(f"Internal call details - From: {caller_id}, To: {called_did}")
    logger.info(f"Extension: {data.get('internal')}, Transfer from: {data.get('transfer_from')}")
    
    # Extract extension number
    extension = data.get('internal', '')
    
    # Try to find agent by extension number
    agent = None
    if extension:
        phone_record = db.query(PhoneNumber).filter(
            PhoneNumber.pbx_extension == str(extension)
        ).first()
        
        if phone_record and phone_record.agent:
            agent = phone_record.agent
            logger.info(f"Found agent {agent.id} for extension {extension}")
    
    # If no agent found by extension, try by called number
    if not agent:
        agent = await get_agent_for_phone_number(db, called_did)
    
    if not agent:
        logger.warning(f"No agent found for internal call - extension: {extension}, called: {called_did}")
        return {"status": "ok", "message": "Internal call received but no agent configured"}
    
    # Find or create call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if not call:
        call = await create_call_record(
            db, agent, caller_id, called_did, zadarma_call_id, "NOTIFY_INTERNAL"
        )
        logger.info(f"Created call record for internal call: {call.id}")
    else:
        logger.info(f"Using existing call record: {call.id}")
    
    return {
        "status": "ok",
        "call_id": call.id,
        "message": "Internal call processed",
        "extension": extension
    }


async def handle_ivr_response(
    db: Session,
    data: Dict[str, Any],
    caller_id: str,
    called_did: str,
    zadarma_call_id: str
) -> Dict[str, Any]:
    """
    Handle IVR response from caller (NOTIFY_IVR)
    
    This event is triggered when the caller responds to an IVR action (e.g., presses a digit).
    For NOTIFY_IVR, we can return call flow control responses similar to NOTIFY_START.
    
    Parameters:
    - event: NOTIFY_IVR
    - call_start: Call start time
    - pbx_call_id: Call ID
    - caller_id: Caller's phone number
    - called_did: Called phone number
    - digits: (optional) Digits entered by caller
    - ivr_saydigits: (optional) "COMPLETE" if digits were played
    - ivr_saynumber: (optional) "COMPLETE" if number was played
    """
    logger.info(f"IVR response received: {zadarma_call_id}")
    logger.info(f"IVR data: {data}")
    
    # Extract digits entered by caller
    digits = data.get('digits', '')
    ivr_saydigits = data.get('ivr_saydigits', '')
    ivr_saynumber = data.get('ivr_saynumber', '')
    
    # Find call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if not call:
        logger.warning(f"Call record not found for IVR response {zadarma_call_id}")
        # Return empty response - call will continue with default behavior
        return {}
    
    logger.info(f"IVR response for call {call.id}: digits={digits}, saydigits={ivr_saydigits}, saynumber={ivr_saynumber}")
    
    # For now, we return an empty response which means "continue with default behavior"
    # In the future, you can implement logic to:
    # - Redirect based on digits entered
    # - Play additional files
    # - Wait for more DTMF input
    # - Hang up the call
    
    # Example: If you want to redirect to extension based on digits
    # if digits == "1":
    #     return build_call_flow_response("redirect", "2001")  # Redirect to extension 2001
    # elif digits == "2":
    #     return build_call_flow_response("redirect", "2002")  # Redirect to extension 2002
    # elif digits == "0":
    #     return build_call_flow_response("hangup")  # Hang up the call
    
    # Example: Play a message and wait for more input
    # return {
    #     "ivr_saypopular": 1,
    #     "language": "en",
    #     "wait_dtmf": {
    #         "timeout": 10,
    #         "attempts": 3,
    #         "maxdigits": 1,
    #         "name": "menu_choice"
    #     }
    # }
    
    return {}


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
