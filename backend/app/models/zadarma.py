from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, Enum
from sqlalchemy.orm import relationship, deferred
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
import enum
from app.models.database import Base


class PhoneNumberStatus(str, enum.Enum):
    """Status of phone number provisioning"""
    PENDING = "pending"  # Waiting for documents
    DOCUMENTS_SUBMITTED = "documents_submitted"  # Documents uploaded, awaiting review
    UNDER_REVIEW = "under_review"  # Being reviewed by Zadarma
    APPROVED = "approved"  # Approved and active
    REJECTED = "rejected"  # Rejected by Zadarma
    ACTIVE = "active"  # Number is active and in use
    SUSPENDED = "suspended"  # Temporarily suspended
    CANCELLED = "cancelled"  # Cancelled


class DocumentType(str, enum.Enum):
    """Types of verification documents"""
    COMPANY_REGISTRATION = "company_registration"
    PROOF_OF_ADDRESS = "proof_of_address"
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    OTHER = "other"


class VerificationStatus(str, enum.Enum):
    """Status of document verification"""
    PENDING = "pending"  # Not yet uploaded
    RECEIVED = "received"  # Uploaded, not yet reviewed
    IN_REVIEW = "in_review"  # Being reviewed
    ACCEPTED = "accepted"  # Accepted
    REJECTED = "rejected"  # Rejected, needs resubmission


class BusyAction(str, enum.Enum):
    """Action when line is busy"""
    BUSY_TONE = "busy_tone"  # Play standard busy signal
    VOICEMAIL = "voicemail"  # Play custom voicemail message


class PhoneNumber(Base):
    """Phone numbers with SIP configuration for AI agent calls"""
    __tablename__ = "phone_numbers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=True)  # Can be unassigned initially
    
    # Phone number details
    phone_number = Column(String, unique=True, nullable=False, index=True)
    country_code = Column(String, nullable=False)  # e.g., "US", "FR", "UK"
    number_type = Column(String, nullable=False)  # "local", "toll-free", "mobile"
    
    # SIP Configuration for incoming calls
    sip_websocket_url = Column(String, nullable=True)
    sip_transport = Column(String, default='WSS', nullable=True)
    sip_username = Column(String, nullable=True)
    sip_password = Column(String, nullable=True)
    sip_domain = Column(String, nullable=True)
    
    # Status
    status = Column(Enum(PhoneNumberStatus, values_callable=lambda x: [e.value for e in x]), default=PhoneNumberStatus.PENDING)
    status_message = Column(Text, nullable=True)  # Details about current status
    
    # Pricing
    monthly_cost = Column(String, default="0.00")  # Monthly rental cost
    per_minute_cost = Column(String, default="0.00")  # Cost per minute for calls
    
    # Business information
    business_name = Column(String, nullable=True)
    business_type = Column(String, nullable=True)  # "company" or "individual"
    business_address = Column(Text, nullable=True)
    
    # Busy line behavior
    busy_action = Column(String, default="busy_tone")  # "busy_tone" or "voicemail"
    busy_voicemail_message = Column(Text, nullable=True)  # Custom message when busy (deprecated, use audio file)
    busy_audio_file_url = Column(String, nullable=True)  # URL to uploaded audio file for busy message
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="phone_numbers")
    agent = relationship("VoiceAgent", back_populates="phone_number")
    verification_documents = relationship("VerificationDocument", back_populates="phone_number", cascade="all, delete-orphan")


class VerificationDocument(Base):
    """Documents uploaded for phone number verification"""
    __tablename__ = "verification_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Document details
    document_type = Column(Enum(DocumentType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    document_name = Column(String, nullable=False)  # Original filename
    file_path = Column(String, nullable=False)  # Storage path
    file_url = Column(String, nullable=True)  # Public URL if applicable
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    
    # Verification status
    status = Column(Enum(VerificationStatus, values_callable=lambda x: [e.value for e in x]), default=VerificationStatus.RECEIVED)
    
    # Review details
    reviewed_by = Column(String, nullable=True)  # Admin who reviewed
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Metadata
    document_metadata = Column(JSON, nullable=True)  # Additional metadata
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    phone_number = relationship("PhoneNumber", back_populates="verification_documents")
    user = relationship("User", back_populates="verification_documents")


class CallbackRequest(Base):
    """Requests for human callback when agent determines human intervention needed"""
    __tablename__ = "callback_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=False)
    
    # Callback details
    reason = Column(Text, nullable=False)  # Why callback is needed
    priority = Column(String, default="normal")  # "urgent", "high", "normal", "low"
    
    # Caller information
    caller_name = Column(String, nullable=True)
    caller_phone = Column(String, nullable=True)
    caller_email = Column(String, nullable=True)
    preferred_callback_time = Column(String, nullable=True)
    
    # Status
    status = Column(String, default="pending")  # "pending", "contacted", "completed", "cancelled"
    assigned_to = Column(String, nullable=True)  # Who should handle the callback
    
    # Notes and follow-up
    notes = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    contacted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    call = relationship("Call", back_populates="callback_request")
    user = relationship("User", back_populates="callback_requests")
    agent = relationship("VoiceAgent", back_populates="callback_requests")

