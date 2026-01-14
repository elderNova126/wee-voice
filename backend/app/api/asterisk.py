"""
Asterisk Configuration Management API

Endpoints for managing Asterisk PBX configuration dynamically.
Allows regeneration of pjsip.conf and extensions.conf based on
phone numbers in the database.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models import get_db, User
from app.core.security import get_current_user
from app.services.asterisk_config_service import get_asterisk_config_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ConfigRegenerateResponse(BaseModel):
    """Response for config regeneration request"""
    success: bool
    message: str
    phone_numbers_count: int = 0
    phones_with_websocket_sip: int = 0  # For pjsip_weevoice.conf
    phones_with_provider_sip: int = 0   # For pjsip_zadarma_credentials.conf
    files_written: bool = False
    zadarma_credentials_written: bool = False
    asterisk_reloaded: bool = False
    errors: list = []
    generated_at: str = ""


class ConfigStatusResponse(BaseModel):
    """Response for config status request"""
    pjsip_file: Dict[str, Any]           # pjsip_weevoice.conf (WebSocket endpoints)
    extensions_file: Dict[str, Any]       # extensions_weevoice.conf (routing)
    zadarma_credentials_file: Dict[str, Any] = {}  # pjsip_zadarma_credentials.conf


@router.post("/regenerate", response_model=ConfigRegenerateResponse)
async def regenerate_asterisk_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate Asterisk configuration files based on current phone numbers.
    
    This endpoint:
    1. Reads all phone numbers with SIP configuration from the database
    2. Generates pjsip_weevoice.conf with endpoints for each number
    3. Generates extensions_weevoice.conf with routing rules
    4. Writes the config files to Asterisk config directory
    5. Attempts to reload Asterisk to apply changes
    
    Requires admin privileges or ownership of at least one phone number.
    """
    # Check if user is admin or has phone numbers with SIP config
    if not current_user.is_superuser:
        # Check if user has any phone numbers with SIP config (either provider or WebSocket)
        from app.models import PhoneNumber
        from sqlalchemy import or_
        user_phones = db.query(PhoneNumber).filter(
            PhoneNumber.user_id == current_user.id,
            or_(
                PhoneNumber.sip_username.isnot(None),
                PhoneNumber.provider_sip_username.isnot(None)
            )
        ).count()
        
        if user_phones == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You need at least one phone number with SIP configuration (provider or WebSocket) to regenerate config"
            )
    
    logger.info(f"User {current_user.email} requesting Asterisk config regeneration")
    
    service = get_asterisk_config_service()
    result = service.regenerate_config(db)
    
    if result['success']:
        message = f"Configuration regenerated successfully for {result['phone_numbers_count']} phone number(s)"
        if not result['asterisk_reloaded']:
            message += " (Asterisk reload failed or not available)"
    else:
        message = "Configuration regeneration failed"
        if result['errors']:
            message += f": {'; '.join(result['errors'])}"
    
    return ConfigRegenerateResponse(
        success=result['success'],
        message=message,
        phone_numbers_count=result['phone_numbers_count'],
        phones_with_websocket_sip=result.get('phones_with_websocket_sip', 0),
        phones_with_provider_sip=result.get('phones_with_provider_sip', 0),
        files_written=result['files_written'],
        zadarma_credentials_written=result.get('zadarma_credentials_written', False),
        asterisk_reloaded=result['asterisk_reloaded'],
        errors=result['errors'],
        generated_at=result['generated_at']
    )


@router.get("/status", response_model=ConfigStatusResponse)
async def get_asterisk_config_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current status of Asterisk configuration files.
    
    Returns information about the generated config files including:
    - File paths
    - Whether files exist
    - Last modified timestamps
    - File sizes
    """
    service = get_asterisk_config_service()
    status_info = service.get_config_status()
    
    return ConfigStatusResponse(**status_info)


@router.post("/reload")
async def reload_asterisk(
    current_user: User = Depends(get_current_user)
):
    """
    Reload Asterisk to apply configuration changes.
    
    This triggers:
    - `asterisk -rx "pjsip reload"`
    - `asterisk -rx "dialplan reload"`
    
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reload Asterisk"
        )
    
    logger.info(f"Admin {current_user.email} requesting Asterisk reload")
    
    service = get_asterisk_config_service()
    result = service.reload_asterisk()
    
    if result['success']:
        return {
            "success": True,
            "message": "Asterisk reloaded successfully",
            "pjsip_reload": result['pjsip_reload'],
            "dialplan_reload": result['dialplan_reload']
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Asterisk reload failed: {'; '.join(result['errors'])}"
        )


@router.get("/preview/pjsip")
async def preview_pjsip_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview the PJSIP configuration that would be generated.
    
    Useful for testing without actually writing files.
    """
    service = get_asterisk_config_service()
    phones = service._get_phone_numbers_with_sip(db)
    
    config = service.generate_pjsip_config(phones)
    
    return {
        "phone_numbers_count": len(phones),
        "config": config
    }


@router.get("/preview/extensions")
async def preview_extensions_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview the extensions configuration that would be generated.
    
    Useful for testing without actually writing files.
    """
    service = get_asterisk_config_service()
    phones = service._get_phone_numbers_with_sip(db)
    
    config = service.generate_extensions_config(phones)
    
    return {
        "phone_numbers_count": len(phones),
        "config": config
    }


@router.get("/phone-numbers")
async def list_configured_phone_numbers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all phone numbers that have SIP configuration.
    
    Shows which phone numbers will be included in Asterisk config generation.
    """
    service = get_asterisk_config_service()
    phones = service._get_phone_numbers_with_sip(db)
    
    # Filter to only show user's phones unless admin
    if not current_user.is_superuser:
        phones = [p for p in phones if p['user_id'] == current_user.id]
    
    return {
        "count": len(phones),
        "phone_numbers": [
            {
                "id": p['id'],
                "phone_number": p['phone_number'],
                "agent_id": p['agent_id'],
                "business_name": p['business_name'],
                "status": p['status'],
                # Provider SIP (for Zadarma/inbound) - goes to pjsip_zadarma_credentials.conf
                "provider_sip_username": p.get('provider_sip_username'),
                "provider_sip_domain": p.get('provider_sip_domain'),
                "has_provider_sip": bool(p.get('provider_sip_username') and p.get('provider_sip_password')),
                # WebSocket SIP (for outbound) - goes to pjsip_weevoice.conf
                "sip_domain": p.get('sip_domain'),
                "sip_username": p.get('sip_username'),
                "has_websocket_sip": bool(p.get('sip_username') and p.get('sip_password') and p.get('sip_domain'))
            }
            for p in phones
        ]
    }

