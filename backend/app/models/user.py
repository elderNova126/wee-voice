from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # Admin approval required
    
    # Subscription
    subscription_tier = Column(Enum(SubscriptionTier, values_callable=lambda x: [e.value for e in x]), default=SubscriptionTier.FREE)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    # Credit Balance
    credit_balance = Column(Float, default=0.0)  # Available credits in USD
    
    # Usage tracking
    total_minutes_used = Column(Float, default=0.0)
    monthly_minutes_used = Column(Float, default=0.0)
    last_reset_date = Column(DateTime, default=datetime.utcnow)
    
    # Avatar settings
    avatar_photo_url = Column(String, nullable=True)  # URL or base64 data
    avatar_photo_type = Column(String, nullable=True)  # 'upload' or 'sample'
    avatar_enabled = Column(Boolean, default=False)  # Enable/disable avatar in calls
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    agents = relationship("VoiceAgent", back_populates="user", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    domain_allowlists = relationship("DomainAllowlist", back_populates="user", cascade="all, delete-orphan")
    ip_allowlists = relationship("IPAllowlist", back_populates="user", cascade="all, delete-orphan")
    security_logs = relationship("SecurityLog", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    phone_numbers = relationship("PhoneNumber", back_populates="user", cascade="all, delete-orphan")
    verification_documents = relationship("VerificationDocument", back_populates="user", cascade="all, delete-orphan")
    callback_requests = relationship("CallbackRequest", back_populates="user", cascade="all, delete-orphan")
    agent_collaborations = relationship("AgentCollaborator", primaryjoin="User.id == AgentCollaborator.user_id", back_populates="user", cascade="all, delete-orphan")

