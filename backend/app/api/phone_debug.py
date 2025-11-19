"""
Phone Number Debugging API
Helps diagnose phone number matching issues
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import get_db, PhoneNumber, VoiceAgent
from app.core.security import get_current_user
from app.api.zadarma_webhook import normalize_phone_for_matching

logger = logging.getLogger(__name__)

router = APIRouter()


def safe_query_phone_numbers_for_user(db: Session, user_id: int) -> list:
    """Safely query PhoneNumber objects without loading sip_id column"""
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
            WHERE user_id = :user_id
        """), {"user_id": user_id})
        
        phones = []
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
            phone.sip_id = None
            phones.append(phone)
        return phones
    except Exception as e:
        logger.error(f"Error in safe_query_phone_numbers_for_user: {e}")
        return []


@router.get("/debug/phone-numbers")
async def debug_phone_numbers(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to see all phone numbers and their normalized forms
    Helps diagnose phone number matching issues
    """
    # Use safe query to avoid sip_id column issue
    phone_numbers = safe_query_phone_numbers_for_user(db, current_user.id)
    
    result = []
    for phone in phone_numbers:
        normalized = normalize_phone_for_matching(phone.phone_number)
        digits_only = ''.join(filter(str.isdigit, normalized))
        
        agent_info = None
        if phone.agent_id:
            agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
            if agent:
                agent_info = {
                    "id": agent.id,
                    "name": agent.name
                }
        
        result.append({
            "id": phone.id,
            "phone_number": phone.phone_number,
            "normalized": normalized,
            "digits_only": digits_only,
            "last_9_digits": digits_only[-9:] if len(digits_only) >= 9 else digits_only,
            "last_10_digits": digits_only[-10:] if len(digits_only) >= 10 else digits_only,
            "agent": agent_info,
            "zadarma_number_id": phone.zadarma_number_id
        })
    
    return {
        "phone_numbers": result,
        "total": len(result),
        "with_agents": len([p for p in phone_numbers if p.agent_id])
    }


@router.get("/debug/test-match/{phone_number}")
async def test_phone_match(
    phone_number: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test if a phone number would match any stored numbers
    Useful for debugging webhook matching issues
    """
    normalized = normalize_phone_for_matching(phone_number)
    digits_only = ''.join(filter(str.isdigit, normalized))
    
    # Use safe query to avoid sip_id column issue
    all_phones_result = db.execute(text("""
        SELECT id, user_id, agent_id, phone_number, country_code, number_type,
               zadarma_number_id, zadarma_status, zadarma_config,
               pbx_enabled, pbx_scenario_id, pbx_extension,
               business_hours, menu_options, after_hours_routing,
               status, status_message, monthly_cost, per_minute_cost,
               business_name, business_type, business_address,
               created_at, updated_at, activated_at
        FROM phone_numbers
        WHERE user_id = :user_id AND agent_id IS NOT NULL
    """), {"user_id": current_user.id})
    
    all_phones = []
    for row in all_phones_result:
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
        phone.sip_id = None
        all_phones.append(phone)
    
    matches = []
    for phone in all_phones:
        normalized_stored = normalize_phone_for_matching(phone.phone_number)
        stored_digits = ''.join(filter(str.isdigit, normalized_stored))
        
        match_info = {
            "stored_number": phone.phone_number,
            "normalized_stored": normalized_stored,
            "stored_digits": stored_digits,
            "matches": []
        }
        
        # Check different matching strategies
        if normalized == normalized_stored:
            match_info["matches"].append("exact_normalized_match")
        
        if digits_only == stored_digits:
            match_info["matches"].append("exact_digit_match")
        
        if len(digits_only) >= 9 and len(stored_digits) >= 9:
            if digits_only[-9:] == stored_digits[-9:]:
                match_info["matches"].append("last_9_digits_match")
        
        if len(digits_only) >= 10 and len(stored_digits) >= 10:
            if digits_only[-10:] == stored_digits[-10:]:
                match_info["matches"].append("last_10_digits_match")
        
        if match_info["matches"]:
            agent = db.query(VoiceAgent).filter(VoiceAgent.id == phone.agent_id).first()
            match_info["agent"] = {
                "id": agent.id,
                "name": agent.name
            } if agent else None
            matches.append(match_info)
    
    return {
        "input": phone_number,
        "normalized": normalized,
        "digits_only": digits_only,
        "last_9_digits": digits_only[-9:] if len(digits_only) >= 9 else digits_only,
        "last_10_digits": digits_only[-10:] if len(digits_only) >= 10 else digits_only,
        "matches": matches,
        "total_phones_checked": len(all_phones)
    }

