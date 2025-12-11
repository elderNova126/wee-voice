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
from sqlalchemy import text
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


def verify_form_webhook_signature(
    caller_id: str,
    called_did: str,
    call_start: str,
    signature: str
) -> bool:
    """
    Verify form-encoded webhook signature from Zadarma
    
    For form-encoded webhooks, Zadarma uses a different signature format:
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
        logger.error(f"Error verifying form webhook signature: {e}")
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


async def get_agent_and_phone_for_number(db: Session, phone_number: str) -> tuple[Optional[VoiceAgent], Optional[PhoneNumber]]:
    """
    Get the voice agent and phone number record for a called phone number
    
    Args:
        db: Database session
        phone_number: Called phone number
        
    Returns:
        Tuple of (VoiceAgent, PhoneNumber) or (None, None)
    """
    # First call the helper to get just the agent
    agent = await get_agent_for_phone_number(db, phone_number)
    if agent:
        # Now find the phone number record to get SIP config
        result = db.execute(text("""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE agent_id = :agent_id
            LIMIT 1
        """), {"agent_id": agent.id}).first()
        
        if result:
            phone_record = PhoneNumber()
            phone_record.id = result[0]
            phone_record.user_id = result[1]
            phone_record.agent_id = result[2]
            phone_record.phone_number = result[3]
            phone_record.country_code = result[4]
            phone_record.number_type = result[5]
            phone_record.sip_websocket_url = result[6]
            phone_record.sip_transport = result[7]
            phone_record.sip_username = result[8]
            phone_record.sip_password = result[9]
            phone_record.sip_domain = result[10]
            phone_record.status = result[11]
            phone_record.status_message = result[12]
            phone_record.monthly_cost = result[13]
            phone_record.per_minute_cost = result[14]
            phone_record.business_name = result[15]
            phone_record.business_type = result[16]
            phone_record.business_address = result[17]
            phone_record.created_at = result[18]
            phone_record.updated_at = result[19]
            phone_record.activated_at = result[20]
            phone_record.agent = agent
            return agent, phone_record
    
    return None, None


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
    try:
        result = db.execute(text("""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE agent_id IS NOT NULL
        """))
        # Convert to PhoneNumber objects and load agent relationships
        all_phones = []
        for row in result:
            phone = PhoneNumber()
            phone.id = row[0]
            phone.user_id = row[1]
            phone.agent_id = row[2]
            phone.phone_number = row[3]
            phone.country_code = row[4]
            phone.number_type = row[5]
            phone.sip_websocket_url = row[6]
            phone.sip_transport = row[7]
            phone.sip_username = row[8]
            phone.sip_password = row[9]
            phone.sip_domain = row[10]
            phone.status = row[11]
            phone.status_message = row[12]
            phone.monthly_cost = row[13]
            phone.per_minute_cost = row[14]
            phone.business_name = row[15]
            phone.business_type = row[16]
            phone.business_address = row[17]
            phone.created_at = row[18]
            phone.updated_at = row[19]
            phone.activated_at = row[20]
            
            # Load agent if agent_id is set
            if phone.agent_id:
                try:
                    agent_result = db.execute(text("""
                        SELECT id, user_id, name, description, language, voice_id, voice_gender,
                               system_prompt, greeting, email_request_enabled, email_request_message,
                               agent_config, tools_enabled, model_name, temperature, max_tokens,
                               crm_webhook_url, crm_enabled, crm_config, is_active, is_public,
                               created_at, updated_at, rag_enabled, rag_config, embed_enabled,
                               embed_widget_color, embed_position, embed_greeting_message, embed_language,
                               allowed_domains
                        FROM voice_agents
                        WHERE id = :agent_id
                        LIMIT 1
                    """), {"agent_id": phone.agent_id}).first()
                    
                    if agent_result:
                        from app.models.agent import VoiceAgent
                        agent = VoiceAgent()
                        agent.id = agent_result[0]
                        agent.user_id = agent_result[1]
                        agent.name = agent_result[2]
                        agent.description = agent_result[3]
                        agent.language = agent_result[4]
                        agent.voice_id = agent_result[5]
                        agent.voice_gender = agent_result[6]
                        agent.system_prompt = agent_result[7]
                        agent.greeting = agent_result[8]
                        agent.email_request_enabled = agent_result[9]
                        agent.email_request_message = agent_result[10]
                        agent.agent_config = agent_result[11]
                        agent.tools_enabled = agent_result[12]
                        agent.model_name = agent_result[13]
                        agent.temperature = agent_result[14]
                        agent.max_tokens = agent_result[15]
                        agent.crm_webhook_url = agent_result[16]
                        agent.crm_enabled = agent_result[17]
                        agent.crm_config = agent_result[18]
                        agent.is_active = agent_result[19]
                        agent.is_public = agent_result[20]
                        agent.created_at = agent_result[21]
                        agent.updated_at = agent_result[22]
                        agent.rag_enabled = agent_result[23]
                        agent.rag_config = agent_result[24]
                        agent.embed_enabled = agent_result[25]
                        agent.embed_widget_color = agent_result[26]
                        agent.embed_position = agent_result[27]
                        agent.embed_greeting_message = agent_result[28]
                        agent.embed_language = agent_result[29]
                        agent.allowed_domains = agent_result[30]
                        phone.agent = agent
                except Exception as e:
                    logger.warning(f"Could not load agent {phone.agent_id} for phone {phone.phone_number}: {e}")
            
            all_phones.append(phone)
    except Exception as e:
        logger.error(f"Error querying phone numbers: {e}")
        all_phones = []
    
    logger.info(f"Available phone numbers in database: {[p.phone_number for p in all_phones]}")
    
    # Try exact match first
    result = db.execute(text("""
        SELECT id, user_id, agent_id, phone_number, country_code, number_type,
               sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
               status, status_message, monthly_cost, per_minute_cost,
               business_name, business_type, business_address,
               created_at, updated_at, activated_at
        FROM phone_numbers
        WHERE phone_number = :phone_number AND agent_id IS NOT NULL
        LIMIT 1
    """), {"phone_number": phone_number}).first()
    
    phone_record = None
    if result:
        phone_record = PhoneNumber()
        phone_record.id = result[0]
        phone_record.user_id = result[1]
        phone_record.agent_id = result[2]
        phone_record.phone_number = result[3]
        phone_record.country_code = result[4]
        phone_record.number_type = result[5]
        phone_record.sip_websocket_url = result[6]
        phone_record.sip_transport = result[7]
        phone_record.sip_username = result[8]
        phone_record.sip_password = result[9]
        phone_record.sip_domain = result[10]
        phone_record.status = result[11]
        phone_record.status_message = result[12]
        phone_record.monthly_cost = result[13]
        phone_record.per_minute_cost = result[14]
        phone_record.business_name = result[15]
        phone_record.business_type = result[16]
        phone_record.business_address = result[17]
        phone_record.created_at = result[18]
        phone_record.updated_at = result[19]
        phone_record.activated_at = result[20]
        
        # Load agent if agent_id is set
        if phone_record.agent_id:
            try:
                agent_result = db.execute(text("""
                    SELECT id, user_id, name, description, language, voice_id, voice_gender,
                           system_prompt, greeting, email_request_enabled, email_request_message,
                           agent_config, tools_enabled, model_name, temperature, max_tokens,
                           crm_webhook_url, crm_enabled, crm_config, is_active, is_public,
                           created_at, updated_at, rag_enabled, rag_config, embed_enabled,
                           embed_widget_color, embed_position, embed_greeting_message, embed_language,
                           allowed_domains
                    FROM voice_agents
                    WHERE id = :agent_id
                    LIMIT 1
                """), {"agent_id": phone_record.agent_id}).first()
                
                if agent_result:
                    from app.models.agent import VoiceAgent
                    agent = VoiceAgent()
                    agent.id = agent_result[0]
                    agent.user_id = agent_result[1]
                    agent.name = agent_result[2]
                    agent.description = agent_result[3]
                    agent.language = agent_result[4]
                    agent.voice_id = agent_result[5]
                    agent.voice_gender = agent_result[6]
                    agent.system_prompt = agent_result[7]
                    agent.greeting = agent_result[8]
                    agent.email_request_enabled = agent_result[9]
                    agent.email_request_message = agent_result[10]
                    agent.agent_config = agent_result[11]
                    agent.tools_enabled = agent_result[12]
                    agent.model_name = agent_result[13]
                    agent.temperature = agent_result[14]
                    agent.max_tokens = agent_result[15]
                    agent.crm_webhook_url = agent_result[16]
                    agent.crm_enabled = agent_result[17]
                    agent.crm_config = agent_result[18]
                    agent.is_active = agent_result[19]
                    agent.is_public = agent_result[20]
                    agent.created_at = agent_result[21]
                    agent.updated_at = agent_result[22]
                    agent.rag_enabled = agent_result[23]
                    agent.rag_config = agent_result[24]
                    agent.embed_enabled = agent_result[25]
                    agent.embed_widget_color = agent_result[26]
                    agent.embed_position = agent_result[27]
                    agent.embed_greeting_message = agent_result[28]
                    agent.embed_language = agent_result[29]
                    agent.allowed_domains = agent_result[30]
                    phone_record.agent = agent
            except Exception as e:
                logger.warning(f"Could not load agent {phone_record.agent_id} for phone {phone_record.phone_number}: {e}")
    
    if phone_record and phone_record.agent:
        logger.info(f"Found agent {phone_record.agent.id} for phone {phone_number} (exact match)")
        return phone_record.agent
    
    # Try normalized match - compare with all stored numbers
    for phone in all_phones:
        # Skip if phone doesn't have an agent assigned
        if not phone.agent_id or not phone.agent:
            logger.debug(f"Skipping phone {phone.phone_number} - no agent assigned (agent_id={phone.agent_id})")
            continue
        
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
    
    # Check if the number exists but has no agent assigned
    result = db.execute(text("""
        SELECT id, phone_number, agent_id
        FROM phone_numbers
        WHERE phone_number = :phone_number OR phone_number = :normalized
        LIMIT 1
    """), {"phone_number": phone_number, "normalized": normalized_incoming}).first()
    
    if result and result[2] is None:  # agent_id is None
        logger.warning(f"Phone number {phone_number} exists in database but has no agent assigned. Please assign an agent to this number.")
    
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
    
    Supports both JSON webhooks (standard) and form-encoded webhooks.
    
    Zadarma sends webhooks for various call events:
    - NOTIFY_START: Incoming call initiated (can return call flow control)
    - NOTIFY_INTERNAL: Internal call event
    - NOTIFY_ANSWER: Call was answered
    - NOTIFY_END: Call ended
    - NOTIFY_OUT_START: Outgoing call started
    - NOTIFY_OUT_END: Outgoing call ended
    - NOTIFY_RECORD: Call recording available
    - NOTIFY_IVR: Caller response to IVR action (can return call flow control)
    """
    # Log immediately at function entry - this should ALWAYS appear
    print("=" * 80)
    print("🔔 ZADARMA WEBHOOK RECEIVED (PRINT)")
    print(f"Request method: {request.method}")
    print(f"Request URL: {request.url}")
    logger.info("=" * 80)
    logger.info("🔔 ZADARMA WEBHOOK RECEIVED (LOGGER)")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info("=" * 80)
    
    try:
        # Get content type to determine if it's JSON or form data
        content_type = request.headers.get('content-type', '').lower()
        logger.info(f"Content-Type: {content_type}")
        is_form_data = 'application/x-www-form-urlencoded' in content_type or 'multipart/form-data' in content_type
        logger.info(f"Is form data: {is_form_data}")
        
        # Parse webhook data based on content type
        if is_form_data:
            # Form-encoded webhooks
            form_data = await request.form()
            data = dict(form_data)
            
            # Extract event and parameters
            event = data.get('event', '')
            caller_id = data.get('caller_id', '')
            called_did = data.get('called_did', data.get('destination', ''))
            call_start = data.get('call_start', '')
            zadarma_call_id = data.get('call_id', data.get('pbx_call_id', ''))
            
            print(f"🔍 Extracted event from form: '{event}'")
            print(f"🔍 Extracted call_id: '{zadarma_call_id}'")
            print(f"🔍 Full form data keys: {list(data.keys())}")
            logger.info(f"Extracted event: {event}, call_id: {zadarma_call_id}")
            logger.info(f"Full form data keys: {list(data.keys())}")
            
            # Verify signature for form-encoded webhooks
            signature = request.headers.get('X-Zadarma-Signature', '')
            if signature and not verify_form_webhook_signature(caller_id, called_did, call_start, signature):
                logger.error("Invalid form webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid signature"
                )
            
            logger.info(f"Form webhook received: {event} for call {zadarma_call_id}")
            logger.info(f"Form webhook data: {data}")
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
            
            print(f"🔍 Extracted event from JSON: '{event}'")
            print(f"🔍 Extracted call_id: '{zadarma_call_id}'")
            print(f"🔍 Full data keys: {list(data.keys())}")
            logger.info(f"Extracted event: {event}, call_id: {zadarma_call_id}")
            logger.info(f"Full webhook data keys: {list(data.keys())}")
            
            # Verify signature for JSON webhooks
            signature = request.headers.get('X-Zadarma-Signature', '')
            if signature and not verify_zadarma_signature(body_str, signature):
                print("❌ Invalid Zadarma webhook signature (PRINT)")
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
        print(f"🔍 Event type: {event}")
        logger.info(f"🔍 Event type: {event}")
        
        if event == "NOTIFY_START":
            print("📞 NOTIFY_START received - Incoming call initiated (PRINT)")
            logger.info("📞 NOTIFY_START received - Incoming call initiated")
            logger.info("ℹ️ NOTE: The call will be handled via SIP connection")
            return await handle_call_start(db, data, caller_id, called_did, zadarma_call_id)
        
        elif event == "NOTIFY_INTERNAL":
            logger.info("📞 NOTIFY_INTERNAL received - Internal call event")
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
    
    This handles incoming calls and sets up the SIP connection.
    """
    logger.info("=" * 80)
    logger.info("📞 HANDLING CALL START (NOTIFY_START)")
    logger.info(f"Caller ID: {caller_id}")
    logger.info(f"Called DID: {called_did}")
    logger.info(f"Zadarma Call ID: {zadarma_call_id}")
    logger.info(f"Data: {data}")
    logger.info("=" * 80)
    logger.info("⚠️ IMPORTANT: NOTIFY_START is just a notification. The call will only be answered")
    logger.info("   if the SIP client is registered. Using phone number's SIP configuration if available.")
    logger.info("=" * 80)
    
    """
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
    
    # Find agent and phone number configuration
    logger.info(f"🔍 Looking up agent and SIP config for phone number: {called_did}")
    agent, phone_record = await get_agent_and_phone_for_number(db, called_did)
    
    if not agent:
        logger.error(f"❌ NO AGENT FOUND for phone number {called_did}")
        logger.warning(f"No agent found for phone number {called_did}")
        # Option: Return hangup response to reject the call
        # return build_call_flow_response("hangup")
        return {
            "status": "error",
            "message": f"No agent configured for number {called_did}"
        }
    
    logger.info(f"✅ Agent found: {agent.id} ({agent.name})")
    
    # Log SIP configuration status
    if phone_record and phone_record.sip_websocket_url:
        logger.info(f"✅ SIP Configuration found:")
        logger.info(f"   WebSocket URL: {phone_record.sip_websocket_url}")
        logger.info(f"   Transport: {phone_record.sip_transport}")
        logger.info(f"   Username: {phone_record.sip_username}")
        logger.info(f"   Domain: {phone_record.sip_domain}")
    else:
        logger.warning("⚠️ No phone-specific SIP configuration found, using default settings")
    
    # Create call record
    logger.info(f"📝 Creating call record...")
    call = await create_call_record(
        db, agent, caller_id, called_did, zadarma_call_id, "NOTIFY_START"
    )
    logger.info(f"✅ Call record created: ID={call.id}, Session ID={call.session_id}")
    
    # Start voice session for phone call
    # This sets up the audio bridge between SIP server and Gemini
    try:
        from app.services.agent_service import FrenchVoiceAgentService
        from app.api.websocket import manager
        from app.services.phone_audio_bridge import phone_audio_manager
        from app.services.sip_client_service import create_sip_client_from_phone_number, SIPClientService
        
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
        
        # Create SIP client with phone number's configuration
        if phone_record and phone_record.sip_websocket_url:
            logger.info(f"🔌 Creating SIP client with phone number's configuration")
            sip_client = create_sip_client_from_phone_number(phone_record)
            
            # Connect to SIP server with phone number's credentials
            connected = await sip_client.connect()
            if connected:
                logger.info(f"✅ SIP client connected to {phone_record.sip_websocket_url}")
                logger.info(f"   Using username: {phone_record.sip_username}@{phone_record.sip_domain}")
            else:
                logger.error(f"❌ Failed to connect SIP client to {phone_record.sip_websocket_url}")
        else:
            logger.warning("⚠️ No phone-specific SIP configuration. Using default SIP settings.")
        
        # Create and start phone audio bridge
        # This handles bidirectional audio streaming between SIP and Gemini
        bridge = await phone_audio_manager.create_bridge(
            agent_service,
            str(call.id),
            zadarma_call_id
        )
        logger.info(f"Started phone audio bridge for call {call.id}")
        
        # Log SIP connection info
        if phone_record and phone_record.sip_websocket_url:
            logger.info(
                f"📞 Phone call {call.id} ready with SIP config:\n"
                f"   WebSocket: {phone_record.sip_websocket_url}\n"
                f"   Username: {phone_record.sip_username}\n"
                f"   Domain: {phone_record.sip_domain}"
            )
        else:
            logger.warning(
                "⚠️ AUDIO WARNING: No phone-specific SIP configuration. "
                "The call may not have audio unless default SIP settings are properly configured. "
                "Add SIP configuration to the phone number in the Phone Numbers page."
            )
    
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
    
    logger.info("=" * 80)
    logger.info(f"✅ CALL START HANDLING COMPLETE")
    logger.info(f"Call ID: {call.id}")
    logger.info(f"Session ID: {call.session_id}")
    logger.info(f"Agent: {agent.id} ({agent.name})")
    logger.info("=" * 80)
    logger.info("⚠️ DIAGNOSTIC: If call is not connected:")
    logger.info("   1. Check SIP configuration in the phone number settings")
    logger.info("   2. Verify SIP username and password are correct")
    logger.info("   3. Ensure WebSocket URL is accessible")
    logger.info("=" * 80)
    
    # Return response to Zadarma with audio endpoints.
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
    
    # Build SIP config info for response
    sip_info = {}
    if phone_record and phone_record.sip_websocket_url:
        sip_info = {
            "websocket_url": phone_record.sip_websocket_url,
            "transport": phone_record.sip_transport,
            "domain": phone_record.sip_domain,
            "configured": True
        }
    else:
        sip_info = {
            "configured": False,
            "message": "No phone-specific SIP configuration"
        }
    
    response = {
        "status": "ok",
        "call_id": call.id,
        "message": "Call initiated successfully, audio bridge ready",
        "session_id": call.session_id,
        # Audio streaming endpoints
        "audio": {
            "input_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/input",
            "output_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/output",
            "end_url": f"{base_url}{api_prefix}/phone/audio/{call.id}/end",
            "format": "audio/pcm;rate=16000",  # Input format (caller's voice)
            "output_format": "audio/pcm;rate=24000"  # Output format (AI responses)
        },
        "sip": sip_info,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "greeting": agent.greeting
        }
    }
    
    logger.info(f"📤 Returning response to Zadarma for call {call.id}: {json.dumps(response, indent=2)}")
    return response


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
    Handle internal call event (NOTIFY_INTERNAL)
    
    This event is triggered when a call is routed internally.
    Parameters:
    - event: NOTIFY_INTERNAL
    - call_start: Call start time
    - call_id: Call ID
    - caller_id: Caller's phone number
    - called_did: Called phone number
    - internal: (optional) Internal destination
    """
    logger.info("=" * 80)
    logger.info("📞 NOTIFY_INTERNAL - Internal call event")
    logger.info(f"Zadarma Call ID: {zadarma_call_id}")
    logger.info(f"Caller ID: {caller_id}")
    logger.info(f"Called DID: {called_did}")
    logger.info(f"Internal: {data.get('internal')}")
    logger.info("=" * 80)
    
    # Try to find agent by called number
    agent = await get_agent_for_phone_number(db, called_did)
    
    if not agent:
        logger.warning(f"No agent found for internal call - called: {called_did}")
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
        "message": "Internal call processed"
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
    
    Parameters:
    - event: NOTIFY_IVR
    - call_start: Call start time
    - call_id: Call ID
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
