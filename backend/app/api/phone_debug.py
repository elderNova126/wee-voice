"""
Phone Number Debugging API
Helps diagnose phone number matching issues
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models import get_db, PhoneNumber, VoiceAgent
from app.core.security import get_current_user
from app.api.zadarma_webhook import normalize_phone_for_matching

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debug/phone-numbers")
async def debug_phone_numbers(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to see all phone numbers and their normalized forms
    Helps diagnose phone number matching issues
    """
    phone_numbers = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id
    ).all()
    
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
    
    all_phones = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id,
        PhoneNumber.agent_id.isnot(None)
    ).all()
    
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

