"""
Virtual Numbers API
Endpoints for ordering and managing virtual phone numbers via Zadarma
"""
import json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.models import get_db, User, PhoneNumber, PhoneNumberStatus
from app.core.security import get_current_user
from app.services.zadarma_numbers_service import get_zadarma_numbers_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =========================================================================
# PYDANTIC MODELS
# =========================================================================

class CountryInfo(BaseModel):
    code: str
    name: str
    prefix: str


class DestinationInfo(BaseModel):
    id: str
    name: str
    type: str  # local, mobile, toll-free, national
    monthly_fee: str
    setup_fee: str
    docs_required: bool


class AvailableNumber(BaseModel):
    id: str
    number: str
    number_formatted: str
    monthly_fee: str
    setup_fee: str
    per_minute_incoming: str


class OrderNumberRequest(BaseModel):
    number_id: str = Field(..., description="Number ID from available numbers")
    direction_id: str = Field(..., description="Destination/Direction ID")
    number: str = Field(..., description="The phone number being ordered")
    country_code: str = Field(..., description="Country code")
    city_name: str = Field(..., description="City/destination name")
    business_name: str = Field(..., description="Business name for the number")
    monthly_fee: str = Field(default="4.99")
    documents_group_id: Optional[str] = Field(None, description="Document group ID if docs required")
    purpose: str = Field(default="AI Voice Agent", description="Purpose of the number")


class OrderNumberResponse(BaseModel):
    success: bool
    message: str
    phone_number_id: Optional[int] = None
    order_id: Optional[str] = None


class DocumentGroupResponse(BaseModel):
    group_id: str
    message: str


# =========================================================================
# API ENDPOINTS
# =========================================================================

@router.get("/countries")
async def get_available_countries(
    current_user: User = Depends(get_current_user)
):
    """Get list of countries where virtual numbers are available"""
    service = get_zadarma_numbers_service()
    result = await service.get_available_countries()
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to fetch countries")
        )
    
    return {
        "countries": result.get("countries", [])
    }


@router.get("/destinations/{country_code}")
async def get_country_destinations(
    country_code: str,
    current_user: User = Depends(get_current_user)
):
    """Get available destinations (cities/regions) for a country"""
    service = get_zadarma_numbers_service()
    result = await service.get_country_destinations(country_code.upper())
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to fetch destinations")
        )
    
    return {
        "destinations": result.get("destinations", [])
    }


@router.get("/available/{direction_id}")
async def get_available_numbers(
    direction_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get available phone numbers for a specific destination"""
    service = get_zadarma_numbers_service()
    result = await service.get_available_numbers(direction_id)
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to fetch available numbers")
        )
    
    return {
        "numbers": result.get("numbers", [])
    }


@router.post("/documents/group", response_model=DocumentGroupResponse)
async def create_document_group(
    group_name: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Create a document group for number verification"""
    service = get_zadarma_numbers_service()
    
    name = group_name or f"WeeVoice_{current_user.email}_{datetime.utcnow().strftime('%Y%m%d')}"
    result = await service.create_document_group(name)
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to create document group")
        )
    
    return {
        "group_id": result.get("group_id"),
        "message": result.get("message", "Document group created successfully")
    }


@router.post("/documents/upload")
async def upload_verification_document(
    group_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a verification document to a document group"""
    # Validate document type
    valid_types = ["passport", "national_id", "company_registration", "proof_of_address", "other"]
    if document_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Must be one of: {valid_types}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 10MB)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10MB"
        )
    
    service = get_zadarma_numbers_service()
    result = await service.upload_document(
        group_id=group_id,
        document_type=document_type,
        file_content=content,
        file_name=file.filename,
        content_type=file.content_type
    )
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to upload document")
        )
    
    return {
        "success": True,
        "document_id": result.get("document_id"),
        "message": result.get("message", "Document uploaded successfully")
    }


@router.post("/order", response_model=OrderNumberResponse)
async def order_virtual_number(
    request: OrderNumberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Order a virtual phone number"""
    service = get_zadarma_numbers_service()
    
    # Check if number already exists in our database
    existing = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == request.number.replace(" ", "")
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered"
        )
    
    # Order the number via Zadarma API
    result = await service.order_number(
        number_id=request.number_id,
        direction_id=request.direction_id,
        documents_group_id=request.documents_group_id,
        purpose=request.purpose
    )
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to order number")
        )
    
    # Determine initial status based on whether docs are required
    initial_status = PhoneNumberStatus.PENDING
    if request.documents_group_id:
        initial_status = PhoneNumberStatus.DOCUMENTS_SUBMITTED
    
    # Create phone number record in database
    phone_record = PhoneNumber(
        user_id=current_user.id,
        phone_number=request.number.replace(" ", ""),
        country_code=request.country_code,
        number_type="virtual",
        status=initial_status,
        status_message="Number ordered. Awaiting activation.",
        business_name=request.business_name,
        monthly_cost=request.monthly_fee,
        per_minute_cost="0.00",
        # Store Zadarma order info for future reference
        zadarma_number_id=result.get("order_id"),
    )
    
    db.add(phone_record)
    db.commit()
    db.refresh(phone_record)
    
    logger.info(f"Virtual number {request.number} ordered for user {current_user.id}")
    
    return {
        "success": True,
        "message": result.get("message", "Number ordered successfully"),
        "phone_number_id": phone_record.id,
        "order_id": result.get("order_id")
    }


@router.get("/connected")
async def get_connected_numbers(
    current_user: User = Depends(get_current_user)
):
    """Get list of user's connected virtual numbers from Zadarma"""
    service = get_zadarma_numbers_service()
    result = await service.get_connected_numbers()
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to fetch connected numbers")
        )
    
    return {
        "numbers": result.get("numbers", [])
    }


@router.post("/{phone_number_id}/configure-sip")
async def configure_sip_routing(
    phone_number_id: int,
    sip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Configure SIP routing for a phone number"""
    # Get the phone number
    phone_record = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    service = get_zadarma_numbers_service()
    result = await service.set_sip_routing(phone_record.phone_number, sip_id)
    
    if result.get("status") != "success":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Failed to configure SIP routing")
        )
    
    # Update local record
    phone_record.sip_id = sip_id
    db.commit()
    
    return {
        "success": True,
        "message": "SIP routing configured successfully"
    }


@router.get("/pricing/{country_code}")
async def get_country_pricing(
    country_code: str,
    current_user: User = Depends(get_current_user)
):
    """Get pricing information for a country"""
    service = get_zadarma_numbers_service()
    result = await service.get_pricing(country_code.upper())
    
    return result

