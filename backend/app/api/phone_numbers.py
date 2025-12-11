"""
Phone Numbers API with SIP Configuration
"""
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
                   business_name, business_type, business_address,
                   created_at, updated_at, activated_at
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
            phone.created_at = row[18]
            phone.updated_at = row[19]
            phone.activated_at = row[20]
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
    sip_domain: Optional[str] = None
    # Note: sip_password is not returned for security
    has_sip_config: bool = False
    
    class Config:
        from_attributes = True


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


def phone_number_to_response(phone: PhoneNumber) -> dict:
    """Convert PhoneNumber object to response dict with has_sip_config"""
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
        "sip_domain": phone.sip_domain,
        "has_sip_config": bool(phone.sip_websocket_url and phone.sip_username and phone.sip_password and phone.sip_domain),
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
    
    # Check if number already exists
    existing = safe_query_phone_number(
        db, 
        "phone_number = :phone1 OR phone_number = :phone2",
        {"phone1": request.phone_number, "phone2": normalized_phone}
    )
    
    if existing:
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
    """List all phone numbers for current user"""
    phone_numbers = safe_query_phone_numbers(
        db,
        "user_id = :user_id ORDER BY created_at DESC",
        {"user_id": current_user.id}
    )
    
    return [phone_number_to_response(phone) for phone in phone_numbers]


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
