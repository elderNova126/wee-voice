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
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory cache for agent greetings (phone_number -> (greeting, language))
# This allows ultra-fast lookup without database queries
_agent_greeting_cache: Dict[str, tuple] = {}  # {phone_number: (greeting, language)}
_cache_last_refresh = 0
CACHE_TTL = 300  # Refresh cache every 5 minutes


def _refresh_greeting_cache_sync(db: Session):
    """Refresh the in-memory greeting cache from database (synchronous)"""
    global _agent_greeting_cache, _cache_last_refresh
    
    try:
        # Query all phone numbers with their agent greetings
        result = db.execute(text("""
            SELECT pn.phone_number, a.greeting, a.language
            FROM phone_numbers pn
            INNER JOIN voice_agents a ON pn.agent_id = a.id
            WHERE pn.agent_id IS NOT NULL AND a.greeting IS NOT NULL
        """))
        
        new_cache = {}
        for row in result:
            phone_number = row[0]
            greeting = row[1]
            language = row[2]
            if phone_number and greeting:
                # Store multiple variations for fast lookup
                new_cache[phone_number] = (greeting, language)
                # Also store normalized version
                normalized = normalize_phone_for_matching(phone_number)
                if normalized and normalized != phone_number:
                    new_cache[normalized] = (greeting, language)
                # Store without + prefix
                if phone_number.startswith("+"):
                    new_cache[phone_number[1:]] = (greeting, language)
        
        _agent_greeting_cache = new_cache
        _cache_last_refresh = time.time()
        logger.info(f"✅ Greeting cache refreshed: {len(new_cache)} entries (including variations)")
    except Exception as e:
        logger.error(f"Failed to refresh greeting cache: {e}")


async def _refresh_cache_background(db: Session):
    """Refresh cache in background (non-blocking)"""
    try:
        from app.models.database import SessionLocal
        bg_db = SessionLocal()
        try:
            _refresh_greeting_cache_sync(bg_db)
        finally:
            bg_db.close()
    except Exception as e:
        logger.debug(f"Background cache refresh failed: {e}")


def _get_cached_greeting(phone_number: str) -> Optional[tuple]:
    """Get greeting from cache (instant, no DB query)"""
    # Try exact match first
    if phone_number in _agent_greeting_cache:
        return _agent_greeting_cache[phone_number]
    
    # Try normalized version
    normalized = normalize_phone_for_matching(phone_number)
    if normalized and normalized != phone_number and normalized in _agent_greeting_cache:
        return _agent_greeting_cache[normalized]
    
    # Try without + prefix
    if phone_number.startswith("+"):
        without_plus = phone_number[1:]
        if without_plus in _agent_greeting_cache:
            return _agent_greeting_cache[without_plus]
    
    return None


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
    # Use raw SQL to avoid sip_id column if it doesn't exist
    try:
        result = db.execute(text("""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   zadarma_number_id, zadarma_status, zadarma_config,
                   pbx_enabled, pbx_scenario_id, pbx_extension,
                   business_hours, menu_options, after_hours_routing,
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
            phone.zadarma_number_id = row[6]
            phone.zadarma_status = row[7]
            phone.zadarma_config = row[8]
            phone.pbx_enabled = row[9]
            phone.pbx_scenario_id = row[10]
            phone.pbx_extension = row[11]
            phone.business_hours = row[12]
            phone.menu_options = row[13]
            phone.after_hours_routing = row[14]
            phone.status = row[15]
            phone.status_message = row[16]
            phone.monthly_cost = row[17]
            phone.per_minute_cost = row[18]
            phone.business_name = row[19]
            phone.business_type = row[20]
            phone.business_address = row[21]
            phone.created_at = row[22]
            phone.updated_at = row[23]
            phone.activated_at = row[24]
            phone.sip_id = None  # Set to None since column may not exist
            
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
                        # Set the agent on the phone object
                        phone.agent = agent
                except Exception as e:
                    logger.warning(f"Could not load agent {phone.agent_id} for phone {phone.phone_number}: {e}")
            
            all_phones.append(phone)
    except Exception as e:
        logger.error(f"Error querying phone numbers: {e}")
        all_phones = []
    
    logger.info(f"Available phone numbers in database: {[p.phone_number for p in all_phones]}")
    
    # Try exact match first - use raw SQL to avoid sip_id column
    result = db.execute(text("""
        SELECT id, user_id, agent_id, phone_number, country_code, number_type,
               zadarma_number_id, zadarma_status, zadarma_config,
               pbx_enabled, pbx_scenario_id, pbx_extension,
               business_hours, menu_options, after_hours_routing,
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
        phone_record.zadarma_number_id = result[6]
        phone_record.zadarma_status = result[7]
        phone_record.zadarma_config = result[8]
        phone_record.pbx_enabled = result[9]
        phone_record.pbx_scenario_id = result[10]
        phone_record.pbx_extension = result[11]
        phone_record.business_hours = result[12]
        phone_record.menu_options = result[13]
        phone_record.after_hours_routing = result[14]
        phone_record.status = result[15]
        phone_record.status_message = result[16]
        phone_record.monthly_cost = result[17]
        phone_record.per_minute_cost = result[18]
        phone_record.business_name = result[19]
        phone_record.business_type = result[20]
        phone_record.business_address = result[21]
        phone_record.created_at = result[22]
        phone_record.updated_at = result[23]
        phone_record.activated_at = result[24]
        phone_record.sip_id = None  # Set to None since column may not exist
        
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
    # Log immediately at function entry - this should ALWAYS appear
    import time
    webhook_start_time = time.time()
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
            # PBX extension webhooks use form data
            form_data = await request.form()
            data = dict(form_data)
            
            # Extract event and parameters
            event = data.get('event', '')
            caller_id = data.get('caller_id', '')
            called_did = data.get('called_did', data.get('destination', ''))
            call_start = data.get('call_start', '')
            zadarma_call_id = data.get('pbx_call_id', data.get('call_id', ''))
            
            print(f"🔍 Extracted event from form: '{event}'")
            print(f"🔍 Extracted pbx_call_id: '{zadarma_call_id}'")
            print(f"🔍 Full form data keys: {list(data.keys())}")
            logger.info(f"Extracted event: {event}, pbx_call_id: {zadarma_call_id}")
            logger.info(f"Full form data keys: {list(data.keys())}")
            
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
            pre_handler_time = (time.time() - webhook_start_time) * 1000
            print(f"📞 NOTIFY_START received - Incoming call initiated (PRINT) - {pre_handler_time:.1f}ms elapsed")
            logger.info(f"📞 NOTIFY_START received - Incoming call initiated ({pre_handler_time:.1f}ms to handler)")
            logger.info("ℹ️ NOTE: For PBX extensions, the call will only be answered if the extension is registered via SIP")
            logger.info("ℹ️ If you see NOTIFY_INTERNAL next, it means the call reached the extension")
            result = await handle_call_start(db, data, caller_id, called_did, zadarma_call_id)
            total_time = (time.time() - webhook_start_time) * 1000
            logger.info(f"✅ NOTIFY_START handled in {total_time:.1f}ms total")
            return result
        
        elif event == "NOTIFY_INTERNAL":
            logger.info("📞 NOTIFY_INTERNAL received - Call reached PBX extension")
            logger.info("✅ This means the call was successfully routed to the extension")
            logger.info("⚠️ For audio to work, the extension MUST be registered via SIP")
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
        total_time = (time.time() - webhook_start_time) * 1000
        logger.error(f"❌ ERROR processing Zadarma webhook after {total_time:.1f}ms: {e}", exc_info=True)
        print(f"❌ ERROR processing webhook after {total_time:.1f}ms: {e} (PRINT)")
        # For NOTIFY_START, still return IVR response to answer call
        # This prevents Zadarma from retrying and causing "circling error"
        if event == "NOTIFY_START":
            logger.warning("⚠️ Returning default IVR response despite error to answer call")
            return JSONResponse(
                content={"ivr_saypopular": 1, "language": "en"},
                status_code=200
            )
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
    
    CRITICAL: Must return IVR response IMMEDIATELY to answer call before timeout.
    NO database queries or blocking operations before returning response.
    Following simple_agent pattern exactly: return response first, everything else in background.
    """
    import time
    start_time = time.time()
    
    try:
        # CRITICAL: Return response IMMEDIATELY with ZERO database operations
        # Use in-memory cache for instant greeting lookup (no DB query)
        
        # Try to get agent's greeting from cache (instant lookup)
        cached = _get_cached_greeting(called_did)
        agent_greeting = None
        agent_language = "en"
        
        if cached:
            agent_greeting, agent_language = cached
            logger.info(f"✅ Cache hit: Found greeting for {called_did} ({len(agent_greeting)} chars)")
        else:
            # Cache miss - refresh cache in background if empty (non-blocking)
            if not _agent_greeting_cache:
                logger.info("Cache is empty - refreshing in background")
                asyncio.create_task(_refresh_cache_background(db))
            logger.debug(f"Cache miss: No greeting cached for {called_did}")
        
        # Determine language code
        zadarma_language_map = {"fr": "fr", "en": "en", "es": "es", "de": "de", "it": "it", "pl": "pl", "ru": "ru"}
        zadarma_lang = zadarma_language_map.get(agent_language[:2] if agent_language else "en", "en")
        
        # Use agent's greeting if available and reasonable length for IVR
        # ivr_say has limits - keep it under 200 chars for reliability
        if agent_greeting and len(agent_greeting) <= 200:
            response = {
                "ivr_say": agent_greeting,
                "language": zadarma_lang
            }
            logger.info(f"✅ Using agent's greeting via ivr_say: {agent_greeting[:50]}...")
        else:
            # Fallback to simple greeting if no cached greeting or too long
            response = {
                "ivr_saypopular": 1,
                "language": zadarma_lang
            }
            if agent_greeting:
                logger.info(f"⚠️ Agent greeting too long ({len(agent_greeting)} chars), using simple greeting")
            else:
                logger.info(f"Using simple greeting (ivr_saypopular: 1) - cache miss or no greeting")
        
        elapsed = (time.time() - start_time) * 1000
        print(f"📤 RETURNING IVR RESPONSE in {elapsed:.1f}ms (PRINT)")
        logger.info(f"📤 RETURNING IVR RESPONSE in {elapsed:.1f}ms - {json.dumps(response)}")
        logger.info(f"Called DID: {called_did}, Call ID: {zadarma_call_id}")
        
        # Start background task AFTER creating response (non-blocking)
        # This will lookup agent and use their greeting for future calls if needed
        try:
            asyncio.create_task(_handle_call_start_background(
                db, caller_id, called_did, zadarma_call_id, data, None
            ))
        except Exception as e:
            logger.warning(f"Failed to start background task (non-critical): {e}")
        
        # Return JSONResponse immediately (critical for call to be answered)
        # Match simple_agent's jsonify() behavior exactly
        return JSONResponse(content=response, status_code=200)
    
    except Exception as e:
        # If anything fails, still return IVR response to answer call
        # This prevents "circling error" from Zadarma retries
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"❌ Error in handle_call_start after {elapsed:.1f}ms: {e}", exc_info=True)
        print(f"❌ Error in handle_call_start: {e} (PRINT)")
        
        # Return default response to answer call despite error
        return JSONResponse(
            content={"ivr_saypopular": 1, "language": "en"},
            status_code=200
        )


async def _handle_call_start_background(
    db: Session,
    caller_id: str,
    called_did: str,
    zadarma_call_id: str,
    data: Dict[str, Any],
    fast_lookup_agent: Optional[Dict] = None
):
    """
    Background task to handle agent lookup and call record creation
    This runs AFTER the IVR response is returned
    
    Args:
        fast_lookup_agent: Agent info from fast lookup (if available)
    """
    try:
        from app.models.database import SessionLocal
        bg_db = SessionLocal()
        try:
            # Use fast lookup agent if available, otherwise do full lookup
            if fast_lookup_agent:
                logger.info(f"🔄 Background: Using agent from fast lookup: {fast_lookup_agent['id']}")
                # Get full agent object
                agent = bg_db.query(VoiceAgent).filter(VoiceAgent.id == fast_lookup_agent['id']).first()
            else:
                logger.info(f"🔄 Background: Looking up agent for {called_did}")
                agent = await get_agent_for_phone_number(bg_db, called_did)
            
            if not agent:
                logger.warning(f"⚠️ Background: No agent found for {called_did}")
                return
            
            logger.info(f"✅ Background: Agent found: {agent.id} ({agent.name})")
            
            # Create call record
            call = await create_call_record(
                bg_db, agent, caller_id, called_did, zadarma_call_id, "NOTIFY_START"
            )
            logger.info(f"✅ Background: Call record created: ID={call.id}")
            
            # Refresh cache if it's stale (non-blocking)
            global _cache_last_refresh
            if time.time() - _cache_last_refresh > CACHE_TTL:
                try:
                    _refresh_greeting_cache_sync(bg_db)
                except Exception as e:
                    logger.debug(f"Cache refresh failed (non-critical): {e}")
            
            # Start agent service setup in background
            asyncio.create_task(_setup_agent_service_background(
                bg_db, call, agent, zadarma_call_id
            ))
            
        finally:
            bg_db.close()
    except Exception as e:
        logger.error(f"❌ Background call start handling failed: {e}", exc_info=True)


async def _setup_agent_service_background(
    db: Session,
    call: Call,
    agent: VoiceAgent,
    zadarma_call_id: str
):
    """
    Background task to set up agent service and audio bridge
    This runs asynchronously after the IVR response is returned
    """
    try:
        logger.info(f"🔄 Starting background setup for call {call.id}")
        
        from app.services.agent_service import FrenchVoiceAgentService
        from app.api.websocket import manager
        from app.services.phone_audio_bridge import phone_audio_manager
        
        # Generate a session ID for this phone call
        import uuid
        session_id = call.session_id or f"phone_{zadarma_call_id}_{uuid.uuid4().hex[:8]}"
        call.session_id = session_id
        
        # Get a new DB session for background task
        from app.models.database import SessionLocal
        bg_db = SessionLocal()
        try:
            # Refresh call in new session
            call = bg_db.query(Call).filter(Call.id == call.id).first()
            if call:
                call.session_id = session_id
                bg_db.commit()
                bg_db.refresh(call)
            
            # Initialize agent service
            agent_service = FrenchVoiceAgentService(agent, call)
            manager.agent_services[session_id] = agent_service
            
            # Start the voice session
            # IMPORTANT: We DO trigger the greeting here because we want the agent's
            # full greeting and conversation capability, not just the simple IVR "Hello"
            # The IVR "Hello" was just to answer the call quickly - now we transition to agent
            await agent_service.start_session()
            logger.info(f"✅ Background: Started voice session for call {call.id}")
            logger.info(f"ℹ️ Agent greeting will play via audio streaming (agent's custom greeting)")
            
            # Create phone audio bridge for bidirectional audio streaming
            # This connects Zadarma phone call to Gemini agent for full conversation
            bridge = await phone_audio_manager.create_bridge(
                agent_service,
                str(call.id),
                zadarma_call_id
            )
            logger.info(f"✅ Background: Started audio bridge for call {call.id}")
            logger.info(f"ℹ️ Audio bridge ready - agent can now have full conversation with caller")
            
            # Send notification to user (non-blocking)
            try:
                from app.services.notification_service import get_notification_service
                from app.models import User
                notification_service = get_notification_service()
                user = bg_db.query(User).filter(User.id == agent.user_id).first()
                if user and user.email:
                    await notification_service.send_call_notification(bg_db, call, "incoming")
                    logger.info(f"✅ Background: Sent notification for call {call.id}")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
            
        finally:
            bg_db.close()
            
    except Exception as e:
        logger.error(f"❌ Background setup failed for call {call.id}: {e}", exc_info=True)
        # Don't fail the call - IVR greeting already played


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
    logger.info("=" * 80)
    logger.info("📞 NOTIFY_INTERNAL - Call reached PBX extension")
    logger.info(f"Zadarma Call ID: {zadarma_call_id}")
    logger.info(f"Caller ID: {caller_id}")
    logger.info(f"Called DID: {called_did}")
    logger.info(f"Extension: {data.get('internal')}, Transfer from: {data.get('transfer_from')}")
    logger.info("=" * 80)
    logger.info("✅ Call successfully routed to extension")
    logger.info("⚠️ For audio to work, the extension MUST be registered via SIP")
    logger.info("   Check: My PBX → Extensions → Your extension should show as ONLINE (green)")
    logger.info("   If offline, you need to register a SIP client to the extension")
    logger.info("=" * 80)
    
    # Extract extension number
    extension = data.get('internal', '')
    
    # Try to find agent by extension number
    agent = None
    if extension:
        # Use raw SQL to avoid sip_id column issue
        result = db.execute(text("""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   zadarma_number_id, zadarma_status, zadarma_config,
                   pbx_enabled, pbx_scenario_id, pbx_extension,
                   business_hours, menu_options, after_hours_routing,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE pbx_extension = :extension
            LIMIT 1
        """), {"extension": str(extension)}).first()
        
        phone_record = None
        if result:
            phone_record = PhoneNumber()
            phone_record.id = result[0]
            phone_record.user_id = result[1]
            phone_record.agent_id = result[2]
            phone_record.phone_number = result[3]
            phone_record.country_code = result[4]
            phone_record.number_type = result[5]
            phone_record.zadarma_number_id = result[6]
            phone_record.zadarma_status = result[7]
            phone_record.zadarma_config = result[8]
            phone_record.pbx_enabled = result[9]
            phone_record.pbx_scenario_id = result[10]
            phone_record.pbx_extension = result[11]
            phone_record.business_hours = result[12]
            phone_record.menu_options = result[13]
            phone_record.after_hours_routing = result[14]
            phone_record.status = result[15]
            phone_record.status_message = result[16]
            phone_record.monthly_cost = result[17]
            phone_record.per_minute_cost = result[18]
            phone_record.business_name = result[19]
            phone_record.business_type = result[20]
            phone_record.business_address = result[21]
            phone_record.created_at = result[22]
            phone_record.updated_at = result[23]
            phone_record.activated_at = result[24]
            phone_record.sip_id = None
        
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
    
    This event is triggered after an IVR action completes (e.g., after greeting is played).
    Following simple_agent pattern: after greeting, we acknowledge to prevent infinite loop.
    
    For wee-voice: After greeting, we want to continue with full conversation.
    However, since Zadarma IVR is limited, we acknowledge the greeting completion
    and the call will continue. The audio bridge set up in NOTIFY_START will handle
    the actual conversation if audio streaming is configured.
    
    Parameters:
    - event: NOTIFY_IVR
    - call_start: Call start time
    - pbx_call_id: Call ID
    - caller_id: Caller's phone number
    - called_did: Called phone number
    - digits: (optional) Digits entered by caller
    - wait_dtmf[digits]: (optional) DTMF digits from wait_dtmf
    - wait_dtmf[ERROR]: (optional) Error message if DTMF timeout
    - ivr_saydigits: (optional) "COMPLETE" if digits were played
    - ivr_saynumber: (optional) "COMPLETE" if number was played
    - ivr_saypopular: (optional) "COMPLETE" if popular phrase was played
    - ivr_say: (optional) "COMPLETE" if custom text was played
    """
    logger.info("=" * 80)
    logger.info("📞 HANDLING IVR RESPONSE (NOTIFY_IVR)")
    logger.info(f"Zadarma Call ID: {zadarma_call_id}")
    logger.info(f"IVR data: {data}")
    logger.info("=" * 80)
    
    # Extract IVR completion status
    digits = data.get('digits', '')
    wait_dtmf_digits = data.get('wait_dtmf[digits]', '')
    wait_dtmf_error = data.get('wait_dtmf[ERROR]', '')
    ivr_saydigits = data.get('ivr_saydigits', '')
    ivr_saynumber = data.get('ivr_saynumber', '')
    ivr_saypopular = data.get('ivr_saypopular', '')
    ivr_say = data.get('ivr_say', '')
    
    # Find call record
    call = db.query(Call).filter(
        Call.zadarma_call_id == zadarma_call_id
    ).first()
    
    if not call:
        logger.warning(f"Call record not found for IVR response {zadarma_call_id}")
        # Return empty response - call will continue with default behavior
        return {}
    
    logger.info(f"IVR response for call {call.id}")
    logger.info(f"  - Digits: {digits}")
    logger.info(f"  - Wait DTMF digits: {wait_dtmf_digits}")
    logger.info(f"  - Wait DTMF error: {wait_dtmf_error}")
    logger.info(f"  - IVR saypopular: {ivr_saypopular}")
    logger.info(f"  - IVR say: {ivr_say}")
    
    # Check if this is after greeting completion
    greeting_completed = (
        ivr_saypopular == "COMPLETE" or
        ivr_say == "COMPLETE" or
        (not wait_dtmf_error and not wait_dtmf_digits and not digits)
    )
    
    if greeting_completed:
        logger.info("✅ IVR greeting completed - transitioning to agent conversation")
        logger.info("ℹ️ Audio bridge should be active for full conversation")
        logger.info("ℹ️ Agent will now handle the conversation (like web agent)")
        
        # After IVR greeting completes, the agent service should take over
        # The audio bridge set up in background should be ready
        # Return acknowledgment - the call continues with agent via audio streaming
        # This is different from simple_agent which just ends the call
        return {"status": "ok"}
    
    # If user provided DTMF input, handle it
    if wait_dtmf_digits or digits:
        user_input = wait_dtmf_digits or digits
        logger.info(f"User provided DTMF input: {user_input}")
        
        # For now, acknowledge and continue
        # In the future, you could implement menu navigation based on digits
        # Example:
        # if user_input == "1":
        #     return build_call_flow_response("redirect", "2001")
        # elif user_input == "0":
        #     return build_call_flow_response("hangup")
        
        return {"status": "ok"}
    
    # If there was an error (timeout, etc.)
    if wait_dtmf_error:
        logger.warning(f"IVR Error: {wait_dtmf_error}")
        # On timeout or error, just acknowledge - call will continue or end
        return {"status": "ok"}
    
    # Default: acknowledge to prevent infinite loop
    logger.info("Returning acknowledgment to prevent infinite loop")
    return {"status": "ok"}


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
