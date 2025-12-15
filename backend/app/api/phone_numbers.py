"""
Phone Numbers API with SIP Configuration
"""
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

from app.models import (
    get_db,
    User,
    PhoneNumber,
    PhoneNumberStatus,
    VerificationDocument,
    DocumentType,
    VerificationStatus,
)
from app.core.security import get_current_user
from pydantic import EmailStr
from app.services.storage_service import get_storage_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def safe_query_phone_number(db: Session, filter_clause: str, params: Dict = None) -> Optional[PhoneNumber]:
    """
    Safely query PhoneNumber
    
    Args:
        db: Database session
        filter_clause: SQL WHERE clause (e.g., "id = :id")
        params: Parameters for the query
        
    Returns:
        PhoneNumber object or None
    """
    params = params or {}
    try:
        result = db.execute(text(f"""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE {filter_clause}
            LIMIT 1
        """), params).first()
        
        if result:
            phone = PhoneNumber()
            phone.id = result[0]
            phone.user_id = result[1]
            phone.agent_id = result[2]
            phone.phone_number = result[3]
            phone.country_code = result[4]
            phone.number_type = result[5]
            phone.sip_websocket_url = result[6]
            phone.sip_transport = result[7]
            phone.sip_username = result[8]
            phone.sip_password = result[9]
            phone.sip_domain = result[10]
            phone.status = result[11]
            phone.status_message = result[12]
            phone.monthly_cost = result[13]
            phone.per_minute_cost = result[14]
            phone.business_name = result[15]
            phone.business_type = result[16]
            phone.business_address = result[17]
            phone.created_at = result[18]
            phone.updated_at = result[19]
            phone.activated_at = result[20]
            return phone
        return None
    except Exception as e:
        logger.error(f"Error in safe_query_phone_number: {e}")
        return None


def safe_query_phone_numbers(db: Session, filter_clause: str = "1=1", params: Dict = None) -> List[PhoneNumber]:
    """
    Safely query multiple PhoneNumber objects
    
    Args:
        db: Database session
        filter_clause: SQL WHERE clause (default: "1=1" for all records)
        params: Parameters for the query
        
    Returns:
        List of PhoneNumber objects
    """
    params = params or {}
    try:
        result = db.execute(text(f"""
            SELECT id, user_id, agent_id, phone_number, country_code, number_type,
                   sip_websocket_url, sip_transport, sip_username, sip_password, sip_domain,
                   status, status_message, monthly_cost, per_minute_cost,
                   business_name, business_type, business_address, busy_action, busy_audio_file_url,
                   restriction_mode, blocked_countries, blocked_numbers, allowed_countries,
                   collaborators, created_at, updated_at, activated_at
            FROM phone_numbers
            WHERE {filter_clause}
        """), params)
        
        phones = []
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
            phone.busy_action = row[18]
            phone.busy_audio_file_url = row[19]
            phone.restriction_mode = row[20]
            phone.blocked_countries = row[21]
            phone.blocked_numbers = row[22]
            phone.allowed_countries = row[23]
            phone.collaborators = row[24]
            phone.created_at = row[25]
            phone.updated_at = row[26]
            phone.activated_at = row[27]
            phones.append(phone)
        return phones
    except Exception as e:
        logger.error(f"Error in safe_query_phone_numbers: {e}")
        return []


# Pydantic models
class SIPConfiguration(BaseModel):
    """SIP configuration for phone number"""
    websocket_url: str = Field(..., description="WebSocket URL for SIP connection (e.g., wss://weevoice.weedoo.com:8089/ws)")
    transport: str = Field(default="WSS", description="Transport protocol (WSS)")
    username: str = Field(..., description="SIP Username")
    password: str = Field(..., description="SIP Password")
    domain: str = Field(..., description="SIP Domain/Realm")


class PhoneNumberAddExisting(BaseModel):
    phone_number: str
    country_code: str = "BE"
    business_name: Optional[str] = None
    sip_config: Optional[SIPConfiguration] = None


class CollaboratorInfo(BaseModel):
    """Collaborator information for display"""
    id: int
    user_id: int
    user_email: str
    user_name: Optional[str] = None
    permissions: str
    is_active: bool


class PhoneNumberResponse(BaseModel):
    id: int
    phone_number: str
    country_code: str
    status: str
    business_name: Optional[str]
    monthly_cost: str
    per_minute_cost: str
    agent_id: Optional[int]
    created_at: datetime
    activated_at: Optional[datetime]
    # SIP Configuration fields
    sip_websocket_url: Optional[str] = None
    sip_transport: Optional[str] = None
    sip_username: Optional[str] = None
    sip_password: Optional[str] = None
    sip_domain: Optional[str] = None
    has_sip_config: bool = False
    # Busy line behavior
    busy_action: Optional[str] = "busy_tone"
    busy_audio_file_url: Optional[str] = None
    
    # Call restrictions
    blocked_countries: Optional[List[str]] = None
    blocked_numbers: Optional[List[str]] = None
    allowed_countries: Optional[List[str]] = None
    restriction_mode: Optional[str] = "none"
    
    # Collaborators
    collaborators: Optional[List[CollaboratorInfo]] = None
    
    # Ownership info
    is_owner: Optional[bool] = True
    role: Optional[str] = "owner"  # "owner" or "collaborator"
    permissions: Optional[List[str]] = None  # User's permissions if collaborator
    owner_email: Optional[str] = None  # Email of the owner (for collaborators)
    
    class Config:
        from_attributes = True


class PhoneNumberUpdate(BaseModel):
    """Update phone number settings"""
    business_name: Optional[str] = None
    # SIP Configuration
    sip_websocket_url: Optional[str] = None
    sip_transport: Optional[str] = None
    sip_username: Optional[str] = None
    sip_password: Optional[str] = None
    sip_domain: Optional[str] = None
    # Busy settings
    busy_action: Optional[str] = None
    busy_audio_file_url: Optional[str] = None
    # Call restrictions
    blocked_countries: Optional[List[str]] = None
    blocked_numbers: Optional[List[str]] = None
    allowed_countries: Optional[List[str]] = None
    restriction_mode: Optional[str] = None


class BusySettingsUpdate(BaseModel):
    """Update busy line settings"""
    busy_action: str = Field(..., pattern="^(busy_tone|voicemail)$")
    busy_audio_file_url: Optional[str] = None


class VerificationDocumentResponse(BaseModel):
    id: int
    document_type: str
    document_name: str
    file_url: Optional[str]
    status: str
    rejection_reason: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class DocumentReviewRequest(BaseModel):
    status: str  # "accepted" or "rejected"
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None


def normalize_phone_for_storage(phone: str) -> str:
    """
    Normalize phone number for storage in database
    Ensures consistent format: +XXXXXXXXXX (E.164 format)
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
        elif normalized.startswith("32") and len(normalized) >= 10:
            normalized = "+" + normalized
        # For other cases, try to add + if it looks like an international number
        elif len(normalized) >= 9:
            normalized = "+" + normalized
    
    return normalized


def _parse_json_field(value) -> list:
    """Parse a JSON field that might be a list, JSON string, PostgreSQL array, or None"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Handle empty strings
        if not value or value.strip() in ('', '[]', '{}'):
            return []
        # Handle PostgreSQL array format: {VN} or {VN,UK}
        if value.startswith('{') and value.endswith('}') and not value.startswith('{"'):
            inner = value[1:-1]  # Remove { and }
            if not inner:
                return []
            return [item.strip().strip('"') for item in inner.split(',') if item.strip()]
        # Handle JSON array format: ["VN"] or ["VN","UK"]
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def parse_collaborators(collaborators_json: str) -> List[dict]:
    """Parse collaborators JSON field from phone number"""
    if not collaborators_json:
        return []
    try:
        collaborators = json.loads(collaborators_json)
        return collaborators if isinstance(collaborators, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def phone_number_to_response(phone: PhoneNumber, db: Session = None, current_user_id: int = None) -> dict:
    """Convert PhoneNumber object to response dict with has_sip_config and ownership info"""
    # Parse collaborators from JSON field
    collaborators = parse_collaborators(phone.collaborators) if phone.collaborators else []
    
    # Determine ownership and role
    is_owner = current_user_id is not None and phone.user_id == current_user_id
    role = "owner"
    permissions = ["view", "edit", "delete", "manage_collaborators"] if is_owner else []
    owner_email = None
    
    if not is_owner and current_user_id:
        # Check if user is an accepted collaborator
        for collab in collaborators:
            if (collab.get("user_id") == current_user_id and 
                collab.get("is_active", True) and
                collab.get("status", "pending") == "accepted"):
                role = "collaborator"
                perm_str = collab.get("permissions", "view")
                permissions = [p.strip() for p in perm_str.split(",")]
                # Get owner email
                if db:
                    owner = db.query(User).filter(User.id == phone.user_id).first()
                    owner_email = owner.email if owner else None
                break
    
    return {
        "id": phone.id,
        "phone_number": phone.phone_number,
        "country_code": phone.country_code,
        "status": phone.status.value if hasattr(phone.status, 'value') else str(phone.status),
        "business_name": phone.business_name,
        "monthly_cost": phone.monthly_cost,
        "per_minute_cost": phone.per_minute_cost,
        "agent_id": phone.agent_id,
        "created_at": phone.created_at,
        "activated_at": phone.activated_at,
        "sip_websocket_url": phone.sip_websocket_url,
        "sip_transport": phone.sip_transport,
        "sip_username": phone.sip_username,
        "sip_password": phone.sip_password,
        "sip_domain": phone.sip_domain,
        "has_sip_config": bool(phone.sip_websocket_url and phone.sip_username and phone.sip_password and phone.sip_domain),
        # Busy line behavior
        "busy_action": phone.busy_action.value if hasattr(phone.busy_action, 'value') else (phone.busy_action or "busy_tone"),
        "busy_audio_file_url": phone.busy_audio_file_url,
        # Call restrictions (parse JSON fields that might be strings or lists)
        "restriction_mode": phone.restriction_mode or "none",
        "blocked_countries": _parse_json_field(phone.blocked_countries),
        "blocked_numbers": _parse_json_field(phone.blocked_numbers),
        "allowed_countries": _parse_json_field(phone.allowed_countries),
        # Collaborators
        "collaborators": collaborators,
        # Ownership info
        "is_owner": is_owner,
        "role": role,
        "permissions": permissions,
        "owner_email": owner_email,
    }


@router.post("/add-existing", response_model=PhoneNumberResponse)
async def add_existing_phone_number(
    request: PhoneNumberAddExisting,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an existing phone number with SIP configuration for incoming calls"""
    # Normalize phone number for storage
    normalized_phone = normalize_phone_for_storage(request.phone_number)
    
    logger.info(f"Adding existing phone number: {request.phone_number} -> normalized: {normalized_phone}")
    
    # Check if number already exists (use direct ORM query for reliability)
    existing = db.query(PhoneNumber).filter(
        (PhoneNumber.phone_number == request.phone_number) |
        (PhoneNumber.phone_number == normalized_phone)
    ).first()
    
    if existing:
        logger.warning(f"Duplicate phone number attempt: {normalized_phone} (exists as ID {existing.id})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered"
        )
    
    # Create phone number record with SIP config
    phone_record = PhoneNumber(
        user_id=current_user.id,
        phone_number=normalized_phone,
        country_code=request.country_code,
        number_type="local",
        status=PhoneNumberStatus.ACTIVE,
        business_name=request.business_name or current_user.email,
        monthly_cost="4.99",
        per_minute_cost="0.02",
        activated_at=datetime.utcnow()
    )
    
    # Add SIP configuration if provided
    if request.sip_config:
        phone_record.sip_websocket_url = request.sip_config.websocket_url
        phone_record.sip_transport = request.sip_config.transport
        phone_record.sip_username = request.sip_config.username
        phone_record.sip_password = request.sip_config.password
        phone_record.sip_domain = request.sip_config.domain
        logger.info(f"SIP configuration set for phone number: {normalized_phone}")
    
    db.add(phone_record)
    db.commit()
    db.refresh(phone_record)
    
    logger.info(f"Added phone number {normalized_phone} with SIP config: {bool(request.sip_config)}")
    
    return phone_record


@router.get("/", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all phone numbers for current user (owned and collaborated)"""
    # Get phone numbers owned by the user
    owned_phones = safe_query_phone_numbers(
        db,
        "user_id = :user_id",
        {"user_id": current_user.id}
    )
    
    # Get phone numbers where user is a collaborator
    # Query all phone numbers with collaborators and filter in Python
    all_phones_with_collabs = safe_query_phone_numbers(
        db,
        "collaborators IS NOT NULL AND collaborators != '' AND collaborators != '[]'"
    )
    
    collaborated_phones = []
    for phone in all_phones_with_collabs:
        # Skip if user owns this phone
        if phone.user_id == current_user.id:
            continue
        
        # Check if user is in collaborators with accepted status
        collaborators = parse_collaborators(phone.collaborators)
        for collab in collaborators:
            if (collab.get("user_id") == current_user.id and 
                collab.get("is_active", True) and 
                collab.get("status", "pending") == "accepted"):
                collaborated_phones.append(phone)
                break
    
    # Combine and deduplicate (owned phones first, then collaborated)
    all_phones = {phone.id: phone for phone in owned_phones}
    for phone in collaborated_phones:
        if phone.id not in all_phones:
            all_phones[phone.id] = phone
    
    # Sort by created_at descending
    sorted_phones = sorted(all_phones.values(), key=lambda p: p.created_at or datetime.min, reverse=True)
    
    return [phone_number_to_response(phone, db, current_user.id) for phone in sorted_phones]


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific phone number"""
    phone_number = safe_query_phone_number(
        db,
        "id = :id AND user_id = :user_id",
        {"id": phone_number_id, "user_id": current_user.id}
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    return phone_number


@router.post("/{phone_number_id}/activate/{agent_id}")
async def activate_phone_number_for_agent(
    phone_number_id: int,
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign phone number to an agent"""
    phone_number = safe_query_phone_number(
        db,
        "id = :id AND user_id = :user_id",
        {"id": phone_number_id, "user_id": current_user.id}
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Update phone number with agent assignment
    db.execute(
        text("UPDATE phone_numbers SET agent_id = :agent_id, status = :status WHERE id = :id"),
        {"agent_id": agent_id, "status": PhoneNumberStatus.ACTIVE.value, "id": phone_number_id}
    )
    db.commit()
    
    logger.info(f"Assigned phone number {phone_number.phone_number} to agent {agent_id}")
    
    return {"message": "Phone number activated successfully"}


@router.delete("/{phone_number_id}")
async def delete_phone_number(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a phone number"""
    phone_number = safe_query_phone_number(
        db,
        "id = :id AND user_id = :user_id",
        {"id": phone_number_id, "user_id": current_user.id}
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Delete phone number
    db.execute(
        text("DELETE FROM phone_numbers WHERE id = :id"),
        {"id": phone_number_id}
    )
    db.commit()
    
    logger.info(f"Deleted phone number {phone_number.phone_number} (ID: {phone_number_id})")
    
    return {"message": "Phone number deleted successfully"}


@router.post("/{phone_number_id}/upload-document")
async def upload_verification_document(
    phone_number_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload verification document for phone number"""
    phone_number = safe_query_phone_number(
        db,
        "id = :id AND user_id = :user_id",
        {"id": phone_number_id, "user_id": current_user.id}
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Must be one of: {[e.value for e in DocumentType]}"
        )
    
    storage_service = get_storage_service()
    file_content = await file.read()
    
    file_path = f"verification_documents/{current_user.id}/{phone_number_id}/{file.filename}"
    stored_path = await storage_service.upload_file(
        file_content=file_content,
        file_path=file_path,
        content_type=file.content_type
    )
    
    verification_doc = VerificationDocument(
        phone_number_id=phone_number_id,
        user_id=current_user.id,
        document_type=doc_type,
        document_name=file.filename,
        file_path=stored_path,
        file_size=len(file_content),
        mime_type=file.content_type,
        status=VerificationStatus.RECEIVED
    )
    
    db.add(verification_doc)
    
    if phone_number.status == PhoneNumberStatus.PENDING:
        db.execute(
            text("UPDATE phone_numbers SET status = :status WHERE id = :id"),
            {"status": PhoneNumberStatus.DOCUMENTS_SUBMITTED.value, "id": phone_number_id}
        )
    
    db.commit()
    db.refresh(verification_doc)
    
    return {
        "id": verification_doc.id,
        "message": "Document uploaded successfully",
        "status": verification_doc.status.value
    }


@router.get("/{phone_number_id}/documents", response_model=List[VerificationDocumentResponse])
async def list_verification_documents(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all verification documents for a phone number"""
    phone_number = safe_query_phone_number(
        db,
        "id = :id AND user_id = :user_id",
        {"id": phone_number_id, "user_id": current_user.id}
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    documents = db.query(VerificationDocument).filter(
        VerificationDocument.phone_number_id == phone_number_id
    ).order_by(VerificationDocument.created_at.desc()).all()
    
    return documents


@router.put("/{phone_number_id}/busy-settings")
async def update_busy_settings(
    phone_number_id: int,
    settings: BusySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update busy line behavior settings"""
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Validate audio file if action is voicemail
    if settings.busy_action == "voicemail" and not settings.busy_audio_file_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is required when busy_action is 'voicemail'"
        )
    
    phone_number.busy_action = settings.busy_action
    phone_number.busy_audio_file_url = settings.busy_audio_file_url
    db.commit()
    
    logger.info(f"Updated busy settings for phone {phone_number.phone_number}: action={settings.busy_action}")
    
    return {
        "success": True,
        "message": "Busy settings updated",
        "busy_action": settings.busy_action,
        "busy_audio_file_url": settings.busy_audio_file_url
    }


@router.put("/{phone_number_id}")
async def update_phone_number(
    phone_number_id: int,
    updates: PhoneNumberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update phone number settings including SIP config, busy settings, and restrictions"""
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Update fields if provided
    if updates.business_name is not None:
        phone_number.business_name = updates.business_name
    
    # SIP Configuration
    if updates.sip_websocket_url is not None:
        phone_number.sip_websocket_url = updates.sip_websocket_url
    if updates.sip_transport is not None:
        phone_number.sip_transport = updates.sip_transport
    if updates.sip_username is not None:
        phone_number.sip_username = updates.sip_username
    if updates.sip_password is not None:
        phone_number.sip_password = updates.sip_password
    if updates.sip_domain is not None:
        phone_number.sip_domain = updates.sip_domain
    
    # Busy settings
    if updates.busy_action is not None:
        phone_number.busy_action = updates.busy_action
    if updates.busy_audio_file_url is not None:
        phone_number.busy_audio_file_url = updates.busy_audio_file_url
    
    # Call restrictions (Text columns - need json.dumps for lists)
    if updates.restriction_mode is not None:
        phone_number.restriction_mode = updates.restriction_mode
    if updates.blocked_countries is not None:
        phone_number.blocked_countries = json.dumps(updates.blocked_countries) if updates.blocked_countries else None
    if updates.blocked_numbers is not None:
        phone_number.blocked_numbers = json.dumps(updates.blocked_numbers) if updates.blocked_numbers else None
    if updates.allowed_countries is not None:
        phone_number.allowed_countries = json.dumps(updates.allowed_countries) if updates.allowed_countries else None
    
    db.commit()
    db.refresh(phone_number)
    
    logger.info(f"Updated phone number {phone_number.phone_number}")
    
    # Parse JSON fields for response
    response = {
        "id": phone_number.id,
        "phone_number": phone_number.phone_number,
        "business_name": phone_number.business_name,
        "sip_websocket_url": phone_number.sip_websocket_url,
        "sip_transport": phone_number.sip_transport,
        "sip_username": phone_number.sip_username,
        "sip_domain": phone_number.sip_domain,
        "busy_action": phone_number.busy_action,
        "busy_audio_file_url": phone_number.busy_audio_file_url,
        "restriction_mode": phone_number.restriction_mode,
        "blocked_countries": json.loads(phone_number.blocked_countries) if phone_number.blocked_countries else [],
        "blocked_numbers": json.loads(phone_number.blocked_numbers) if phone_number.blocked_numbers else [],
        "allowed_countries": json.loads(phone_number.allowed_countries) if phone_number.allowed_countries else [],
    }
    
    return {"success": True, "message": "Phone number updated", "data": response}


@router.post("/{phone_number_id}/busy-audio")
async def upload_busy_audio(
    phone_number_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload audio file for busy voicemail message"""
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Validate file type
    allowed_types = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/ogg', 'audio/webm']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Upload to storage
    storage = get_storage_service()
    try:
        file_content = await file.read()
        file_path = f"busy-audio/{current_user.id}/{phone_number_id}/{file.filename}"
        
        file_url = await storage.upload_file(
            file_content,
            file_path,
            file.content_type
        )
        
        # Update phone number with audio URL
        phone_number.busy_audio_file_url = file_url
        db.commit()
        
        logger.info(f"Uploaded busy audio for phone {phone_number.phone_number}: {file_url}")
        
        return {
            "success": True,
            "message": "Audio file uploaded successfully",
            "file_url": file_url
        }
        
    except Exception as e:
        logger.error(f"Error uploading busy audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload audio file: {str(e)}"
        )


# ===================================================================
# PHONE NUMBER COLLABORATORS ENDPOINTS
# ===================================================================

class CollaboratorCreate(BaseModel):
    email: EmailStr
    permissions: str  # Comma-separated: "view,edit" or "view,edit,delete"


class CollaboratorUpdate(BaseModel):
    permissions: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None  # pending, accepted, rejected


class CollaboratorResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: Optional[str] = None
    permissions: str
    is_active: bool = True
    status: str = "pending"  # pending, accepted, rejected
    added_at: Optional[str] = None
    invited_by_email: Optional[str] = None
    phone_number_id: Optional[int] = None  # For invites - which phone number this invite belongs to
    phone_number_display: Optional[str] = None  # For showing in invites list
    business_name: Optional[str] = None  # For showing in invites list
    
    class Config:
        from_attributes = True


class InviteAction(BaseModel):
    action: str  # "accept" or "reject"


@router.get("/{phone_number_id}/collaborators", response_model=List[CollaboratorResponse])
async def list_phone_collaborators(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all collaborators for a phone number"""
    # Check if user owns this phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    collaborators = parse_collaborators(phone_number.collaborators)
    return collaborators


@router.post("/{phone_number_id}/collaborators", response_model=CollaboratorResponse)
async def add_phone_collaborator(
    phone_number_id: int,
    collaborator_data: CollaboratorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a collaborator to a phone number"""
    # Check if user owns this phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Find user by email
    user = db.query(User).filter(User.email == collaborator_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is trying to add themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a collaborator")
    
    # Parse existing collaborators
    collaborators = parse_collaborators(phone_number.collaborators)
    
    # Check if collaborator already exists
    existing_idx = None
    for idx, collab in enumerate(collaborators):
        if collab.get("user_id") == user.id:
            existing_idx = idx
            break
    
    # Create new collaborator entry
    new_collab = {
        "id": user.id,  # Use user_id as collaborator id for simplicity
        "user_id": user.id,
        "user_email": user.email,
        "user_name": user.full_name,
        "permissions": collaborator_data.permissions,
        "is_active": True,
        "status": "pending",  # New invites start as pending
        "added_at": datetime.utcnow().isoformat(),
        "invited_by_email": current_user.email,
        "phone_number_display": phone_number.phone_number
    }
    
    if existing_idx is not None:
        # Update existing collaborator - reset to pending
        collaborators[existing_idx] = new_collab
    else:
        # Add new collaborator
        collaborators.append(new_collab)
    
    # Save updated collaborators
    phone_number.collaborators = json.dumps(collaborators)
    db.commit()
    
    logger.info(f"Invited collaborator {user.email} to phone number {phone_number.phone_number}")
    
    return new_collab


@router.put("/{phone_number_id}/collaborators/{collaborator_id}", response_model=CollaboratorResponse)
async def update_phone_collaborator(
    phone_number_id: int,
    collaborator_id: int,
    update_data: CollaboratorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a phone number collaborator's permissions"""
    # Check if user owns this phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Parse collaborators and find the one to update
    collaborators = parse_collaborators(phone_number.collaborators)
    
    found_idx = None
    for idx, collab in enumerate(collaborators):
        if collab.get("user_id") == collaborator_id or collab.get("id") == collaborator_id:
            found_idx = idx
            break
    
    if found_idx is None:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    # Update fields
    if update_data.permissions is not None:
        collaborators[found_idx]["permissions"] = update_data.permissions
    if update_data.is_active is not None:
        collaborators[found_idx]["is_active"] = update_data.is_active
    
    # Save updated collaborators
    phone_number.collaborators = json.dumps(collaborators)
    db.commit()
    
    return collaborators[found_idx]


@router.delete("/{phone_number_id}/collaborators/{collaborator_id}")
async def remove_phone_collaborator(
    phone_number_id: int,
    collaborator_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a collaborator from a phone number"""
    # Check if user owns this phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Parse collaborators and find the one to remove
    collaborators = parse_collaborators(phone_number.collaborators)
    
    new_collaborators = [c for c in collaborators if c.get("user_id") != collaborator_id and c.get("id") != collaborator_id]
    
    if len(new_collaborators) == len(collaborators):
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    # Save updated collaborators
    phone_number.collaborators = json.dumps(new_collaborators) if new_collaborators else None
    db.commit()
    
    logger.info(f"Removed collaborator {collaborator_id} from phone number {phone_number.phone_number}")
    
    return {"message": "Collaborator removed successfully"}


# ===================================================================
# INVITE MANAGEMENT ENDPOINTS
# ===================================================================

@router.get("/invites/pending", response_model=List[CollaboratorResponse])
async def get_pending_invites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all pending collaboration invites for the current user"""
    # Query all phone numbers with collaborators
    all_phones = safe_query_phone_numbers(
        db,
        "collaborators IS NOT NULL AND collaborators != '' AND collaborators != '[]'"
    )
    
    pending_invites = []
    for phone in all_phones:
        # Skip if user owns this phone
        if phone.user_id == current_user.id:
            continue
        
        # Check if user has a pending invite
        collaborators = parse_collaborators(phone.collaborators)
        for collab in collaborators:
            if (collab.get("user_id") == current_user.id and 
                collab.get("is_active", True) and
                collab.get("status", "pending") == "pending"):
                # Add phone number info to the invite
                invite = {
                    **collab,
                    "phone_number_id": phone.id,
                    "phone_number_display": phone.phone_number,
                    "business_name": phone.business_name
                }
                pending_invites.append(invite)
                break
    
    return pending_invites


@router.post("/invites/{phone_number_id}/respond")
async def respond_to_invite(
    phone_number_id: int,
    action: InviteAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept or reject a collaboration invite"""
    if action.action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Action must be 'accept' or 'reject'")
    
    # Get the phone number
    phone_number = db.query(PhoneNumber).filter(PhoneNumber.id == phone_number_id).first()
    
    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    # Parse collaborators
    collaborators = parse_collaborators(phone_number.collaborators)
    
    # Find the user's invite
    found_idx = None
    for idx, collab in enumerate(collaborators):
        if collab.get("user_id") == current_user.id:
            found_idx = idx
            break
    
    if found_idx is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    # Check current status - use "pending" as default for backward compatibility
    current_status = collaborators[found_idx].get("status", "pending")
    if current_status not in ["pending", None, ""]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invite has already been responded to (current status: {current_status})"
        )
    
    # Update the status
    if action.action == "accept":
        collaborators[found_idx]["status"] = "accepted"
        collaborators[found_idx]["is_active"] = True
        collaborators[found_idx]["accepted_at"] = datetime.utcnow().isoformat()
        message = "Invite accepted successfully"
    else:
        collaborators[found_idx]["status"] = "rejected"
        collaborators[found_idx]["is_active"] = False
        collaborators[found_idx]["rejected_at"] = datetime.utcnow().isoformat()
        message = "Invite rejected"
    
    # Save updated collaborators
    phone_number.collaborators = json.dumps(collaborators)
    db.commit()
    
    logger.info(f"User {current_user.email} {action.action}ed invite for phone number {phone_number.phone_number}")
    
    return {"message": message, "status": collaborators[found_idx]["status"]}
