"""
Phone Numbers and Zadarma Integration API
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.models import get_db, User, PhoneNumber, PhoneNumberStatus, VerificationDocument, DocumentType, VerificationStatus
from app.core.security import get_current_user
from app.services.zadarma_service import get_zadarma_service
from app.services.storage_service import get_storage_service

router = APIRouter()


# Pydantic models
class PhoneNumberRequest(BaseModel):
    phone_number: str
    country_code: str
    business_name: str
    business_type: str  # "company" or "individual"
    business_address: str


class PhoneNumberAddExisting(BaseModel):
    phone_number: str
    country_code: str = "BE"
    business_name: Optional[str] = None


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
    
    class Config:
        from_attributes = True


class AvailableNumber(BaseModel):
    number: str
    country: str
    type: str
    monthly_cost: str
    setup_cost: str


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


@router.get("/available", response_model=List[AvailableNumber])
async def get_available_numbers(
    country_code: str = "FR",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available phone numbers for purchase"""
    zadarma_service = get_zadarma_service()
    numbers = await zadarma_service.get_available_numbers(country_code)
    return numbers


@router.post("/add-existing", response_model=PhoneNumberResponse)
async def add_existing_phone_number(
    request: PhoneNumberAddExisting,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an existing phone number that you already own on Zadarma"""
    # Check if number already exists
    existing = db.query(PhoneNumber).filter(
        PhoneNumber.phone_number == request.phone_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already registered"
        )
    
    # Create phone number record directly (already owned, no verification needed)
    phone_record = PhoneNumber(
        user_id=current_user.id,
        phone_number=request.phone_number,
        country_code=request.country_code,
        number_type="local",
        status=PhoneNumberStatus.ACTIVE,  # Already active since you own it
        business_name=request.business_name or current_user.email,
        monthly_cost="4.99",
        per_minute_cost="0.02",
        activated_at=datetime.utcnow()
    )
    
    db.add(phone_record)
    db.commit()
    db.refresh(phone_record)
    
    return phone_record


@router.post("/request", response_model=PhoneNumberResponse)
async def request_phone_number(
    request: PhoneNumberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request a new phone number from Zadarma"""
    zadarma_service = get_zadarma_service()
    
    phone_number = await zadarma_service.request_phone_number(
        db=db,
        user_id=current_user.id,
        phone_number=request.phone_number,
        country_code=request.country_code,
        business_name=request.business_name,
        business_type=request.business_type,
        business_address=request.business_address
    )
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to request phone number"
        )
    
    return phone_number


@router.get("/", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all phone numbers for current user"""
    phone_numbers = db.query(PhoneNumber).filter(
        PhoneNumber.user_id == current_user.id
    ).order_by(PhoneNumber.created_at.desc()).all()
    
    return phone_numbers


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific phone number"""
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    return phone_number


@router.post("/{phone_number_id}/upload-document")
async def upload_verification_document(
    phone_number_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload verification document for phone number"""
    # Verify phone number belongs to user
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    # Validate document type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Must be one of: {[e.value for e in DocumentType]}"
        )
    
    # Upload file
    storage_service = get_storage_service()
    file_content = await file.read()
    
    file_path = f"verification_documents/{current_user.id}/{phone_number_id}/{file.filename}"
    stored_path = await storage_service.upload_file(
        file_content=file_content,
        file_path=file_path,
        content_type=file.content_type
    )
    
    # Create verification document record
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
    
    # Update phone number status
    if phone_number.status == PhoneNumberStatus.PENDING:
        phone_number.status = PhoneNumberStatus.DOCUMENTS_SUBMITTED
    
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
    # Verify phone number belongs to user
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.user_id == current_user.id
    ).first()
    
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    documents = db.query(VerificationDocument).filter(
        VerificationDocument.phone_number_id == phone_number_id
    ).order_by(VerificationDocument.created_at.desc()).all()
    
    return documents


@router.post("/{phone_number_id}/documents/{document_id}/review")
async def review_verification_document(
    phone_number_id: int,
    document_id: int,
    review: DocumentReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Review a verification document (admin only)"""
    # TODO: Add admin check
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can review documents"
        )
    
    document = db.query(VerificationDocument).filter(
        VerificationDocument.id == document_id,
        VerificationDocument.phone_number_id == phone_number_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Update document status
    if review.status == "accepted":
        document.status = VerificationStatus.ACCEPTED
    elif review.status == "rejected":
        document.status = VerificationStatus.REJECTED
        document.rejection_reason = review.rejection_reason
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'accepted' or 'rejected'"
        )
    
    document.reviewed_by = current_user.email
    document.reviewed_at = datetime.utcnow()
    document.notes = review.notes
    
    # Check if all required documents are accepted
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id
    ).first()
    
    all_docs = db.query(VerificationDocument).filter(
        VerificationDocument.phone_number_id == phone_number_id
    ).all()
    
    # Check if we have all required documents accepted
    required_types = set()
    if phone_number.business_type == "company":
        required_types = {DocumentType.COMPANY_REGISTRATION, DocumentType.PROOF_OF_ADDRESS}
    else:
        required_types = {DocumentType.PASSPORT, DocumentType.PROOF_OF_ADDRESS}
    
    accepted_types = {doc.document_type for doc in all_docs if doc.status == VerificationStatus.ACCEPTED}
    
    if required_types.issubset(accepted_types):
        phone_number.status = PhoneNumberStatus.APPROVED
        phone_number.status_message = "All documents verified and approved"
    elif any(doc.status == VerificationStatus.REJECTED for doc in all_docs):
        phone_number.status = PhoneNumberStatus.DOCUMENTS_SUBMITTED
        phone_number.status_message = "Some documents rejected. Please resubmit."
    
    db.commit()
    
    return {
        "message": "Document reviewed successfully",
        "document_id": document.id,
        "status": document.status.value
    }


@router.post("/{phone_number_id}/activate/{agent_id}")
async def activate_phone_number_for_agent(
    phone_number_id: int,
    agent_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Activate phone number and assign to an agent"""
    zadarma_service = get_zadarma_service()
    
    success = await zadarma_service.activate_number_for_agent(
        db=db,
        phone_number_id=phone_number_id,
        agent_id=agent_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to activate phone number"
        )
    
    return {"message": "Phone number activated successfully"}


@router.get("/{phone_number_id}/status")
async def check_phone_number_status(
    phone_number_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check status of phone number with Zadarma"""
    zadarma_service = get_zadarma_service()
    
    success = await zadarma_service.check_number_status(db, phone_number_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to check phone number status"
        )
    
    # Return updated phone number
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id
    ).first()
    
    return phone_number

