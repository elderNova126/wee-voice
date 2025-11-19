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


class PhoneNumber(Base):
    """Phone numbers provisioned via Zadarma for agents"""
    __tablename__ = "phone_numbers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=True)  # Can be unassigned initially
    
    # Phone number details
    phone_number = Column(String, unique=True, nullable=False, index=True)
    country_code = Column(String, nullable=False)  # e.g., "US", "FR", "UK"
    number_type = Column(String, nullable=False)  # "local", "toll-free", "mobile"
    
    # Zadarma integration
    zadarma_number_id = Column(String, nullable=True)  # Zadarma's internal ID
    zadarma_status = Column(String, nullable=True)
    zadarma_config = Column(JSON, nullable=True)  # Zadarma-specific settings
    pbx_enabled = Column(Boolean, default=False)
    pbx_scenario_id = Column(String, nullable=True)
    pbx_extension = Column(String, nullable=True)
    # Note: sip_id column may not exist in database, so we handle it gracefully
    # We don't define it as a Column to avoid SQLAlchemy trying to SELECT it
    business_hours = Column(JSON, nullable=True)
    
    def __init__(self, **kwargs):
        # Remove sip_id from kwargs if present, store it separately
        self._sip_id = kwargs.pop('sip_id', None)
        super().__init__(**kwargs)
    
    @hybrid_property
    def sip_id(self):
        """Get sip_id, returning None if column doesn't exist"""
        return getattr(self, '_sip_id', None)
    
    @sip_id.setter
    def sip_id(self, value):
        """Set sip_id"""
        self._sip_id = value
    menu_options = Column(JSON, nullable=True)
    after_hours_routing = Column(JSON, nullable=True)
    
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

