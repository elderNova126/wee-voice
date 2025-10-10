from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class Transaction(Base):
    """Payment transactions"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Transaction details
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    status = Column(Enum(PaymentStatus, values_callable=lambda x: [e.value for e in x]), default=PaymentStatus.PENDING)
    description = Column(String, nullable=True)
    
    # Payment provider data
    stripe_payment_intent_id = Column(String, nullable=True, unique=True)
    stripe_charge_id = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)  # card, bank_transfer, etc.
    
    # Metadata (store in DB column 'metadata' but avoid using the reserved attribute name)
    metadata_json = Column("metadata", JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="transactions")


class Invoice(Base):
    """Invoices for billing"""
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Invoice details
    invoice_number = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="usd")
    status = Column(Enum(InvoiceStatus, values_callable=lambda x: [e.value for e in x]), default=InvoiceStatus.DRAFT)
    
    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Stripe data
    stripe_invoice_id = Column(String, nullable=True, unique=True)
    stripe_invoice_url = Column(String, nullable=True)
    stripe_pdf_url = Column(String, nullable=True)
    
    # Payment
    paid_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    
    # Line items
    line_items = Column(JSON, nullable=True)  # Detailed breakdown
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="invoices")


class UsageRecord(Base):
    """Detailed usage tracking for analytics"""
    __tablename__ = "usage_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    
    # Usage details
    minutes_used = Column(Float, nullable=False)
    cost = Column(Float, nullable=False)
    
    # Metadata
    date = Column(DateTime, nullable=False, index=True)
    month = Column(String, nullable=False, index=True)  # Format: "2025-01"
    year = Column(Integer, nullable=False, index=True)
    
    # Additional metrics
    api_calls = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="usage_records")
    agent = relationship("VoiceAgent", back_populates="usage_records")
    call = relationship("Call", back_populates="usage_record")

