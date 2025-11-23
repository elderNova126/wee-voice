"""
Twilio Webhook Handler for SIP Trunk Calls
Maps incoming calls to agents and forwards to Railway WebSocket
"""
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging
from xml.etree.ElementTree import Element, tostring

from app.models import get_db, PhoneNumber, VoiceAgent
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def safe_query_phone_number_by_number(db: Session, phone_number: str) -> Optional[PhoneNumber]:
    """
    Safely query PhoneNumber by phone number without loading sip_id column
    """
    try:
        # Normalize phone number (remove +, spaces, dashes)
        normalized = phone_number.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        result = db.execute(text("""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   zadarma_number_id, zadarma_status, zadarma_config,
                   pbx_enabled, pbx_scenario_id, pbx_extension,
                   business_hours, menu_options, after_hours_routing,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(phone_number, '+', ''), ' ', ''), '-', ''), '(', ''), ')', '') = :normalized
            AND status = 'active'
            LIMIT 1
        """), {"normalized": normalized}).first()
        
        if not result:
            return None
        
        # Create PhoneNumber object
        phone = PhoneNumber()
        phone.id = result[0]
        phone.user_id = result[1]
        phone.agent_id = result[2]
        phone.phone_number = result[3]
        phone.country_code = result[4]
        phone.number_type = result[5]
        phone.zadarma_number_id = result[6]
        phone.zadarma_status = result[7]
        phone.zadarma_config = result[8]
        phone.pbx_enabled = result[9]
        phone.pbx_scenario_id = result[10]
        phone.pbx_extension = result[11]
        phone.business_hours = result[12]
        phone.menu_options = result[13]
        phone.after_hours_routing = result[14]
        phone.status = result[15]
        phone.status_message = result[16]
        phone.monthly_cost = result[17]
        phone.per_minute_cost = result[18]
        phone.business_name = result[19]
        phone.business_type = result[20]
        phone.business_address = result[21]
        phone.created_at = result[22]
        phone.updated_at = result[23]
        phone.activated_at = result[24]
        
        return phone
    except Exception as e:
        logger.error(f"Error querying phone number: {e}", exc_info=True)
        return None


def generate_twiml_response(websocket_url: str) -> str:
    """
    Generate TwiML XML response to connect call to WebSocket
    """
    response = Element("Response")
    
    # Connect to WebSocket stream
    connect = Element("Connect")
    stream = Element("Stream")
    stream.set("url", websocket_url)
    connect.append(stream)
    response.append(connect)
    
    # Convert to XML string
    xml_str = tostring(response, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'


@router.post("/twilio/voice")
async def twilio_voice_webhook(
    request: Request,
    Called: Optional[str] = None,  # The number that was called (To)
    Caller: Optional[str] = None,  # The caller's number (From)
    CallSid: Optional[str] = None,  # Twilio call SID
    db: Session = Depends(get_db)
):
    """
    Twilio webhook endpoint for incoming SIP calls
    Maps the called number to an agent and returns TwiML to forward to Railway WebSocket
    """
    try:
        # Get form data (Twilio sends as form-encoded)
        form_data = await request.form()
        called_number = Called or form_data.get("Called", "")
        caller_number = Caller or form_data.get("Caller", "")
        call_sid = CallSid or form_data.get("CallSid", "")
        
        logger.info(f"📞 Twilio webhook received: Called={called_number}, Caller={caller_number}, CallSid={call_sid}")
        
        if not called_number:
            logger.error("No Called number in Twilio webhook")
            # Return empty TwiML to reject call
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
                media_type="application/xml"
            )
        
        # Look up phone number to find agent_id
        phone_record = safe_query_phone_number_by_number(db, called_number)
        
        if not phone_record:
            logger.error(f"Phone number {called_number} not found in database")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
                media_type="application/xml"
            )
        
        if not phone_record.agent_id:
            logger.error(f"Phone number {called_number} has no agent_id assigned")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
                media_type="application/xml"
            )
        
        # Get agent to verify it exists
        agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone_record.agent_id).first()
        if not agent:
            logger.error(f"Agent {phone_record.agent_id} not found")
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
                media_type="application/xml"
            )
        
        logger.info(f"✅ Found agent {agent.id} ({agent.name}) for phone {called_number}")
        
        # Build Railway WebSocket URL
        # Format: wss://domain/api/v1/ws/voice/{agent_id}?api_key={api_key}
        # Use BACKEND_URL if available, otherwise BASE_URL, otherwise production URL
        backend_url = getattr(settings, 'BACKEND_URL', None) or settings.BASE_URL
        base_url = backend_url.replace("http://", "wss://").replace("https://", "wss://")
        if not base_url.startswith("wss://"):
            # Fallback: use production URL if BASE_URL is not set correctly
            base_url = "wss://weevoice-web-production.up.railway.app"
        
        # Get API key from environment variable (set TWILIO_API_KEY in Railway)
        # If not set, we'll try without API key (for public agents)
        import os
        api_key = os.getenv("TWILIO_API_KEY", "")
        
        # Build WebSocket URL
        websocket_url = f"{base_url}/api/v1/ws/voice/{phone_record.agent_id}"
        if api_key:
            websocket_url += f"?api_key={api_key}"
        
        logger.info(f"🔗 Forwarding to WebSocket: {websocket_url}")
        
        # Generate TwiML response
        twiml = generate_twiml_response(websocket_url)
        
        return Response(
            content=twiml,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {e}", exc_info=True)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
            media_type="application/xml"
        )


@router.get("/twilio/voice")
async def twilio_voice_webhook_get(
    request: Request,
    Called: Optional[str] = Query(None),
    Caller: Optional[str] = Query(None),
    CallSid: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    GET handler for Twilio webhook (some configurations use GET)
    """
    return await twilio_voice_webhook(
        request=request,
        Called=Called,
        Caller=Caller,
        CallSid=CallSid,
        db=db
    )

