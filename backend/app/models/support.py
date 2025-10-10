from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TicketCategory(str, enum.Enum):
    TECHNICAL = "technical"
    BILLING = "billing"
    GENERAL = "general"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for non-authenticated users
    ticket_number = Column(String, unique=True, nullable=False, index=True)
    
    # Contact Information
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    
    # Ticket Details
    subject = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    category = Column(Enum(TicketCategory, values_callable=lambda x: [e.value for e in x]), nullable=False)
    priority = Column(Enum(TicketPriority, values_callable=lambda x: [e.value for e in x]), default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus, values_callable=lambda x: [e.value for e in x]), default=TicketStatus.OPEN)
    
    # Metadata
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", backref="support_tickets")
    responses = relationship("TicketResponse", back_populates="ticket", cascade="all, delete-orphan")

class TicketResponse(Base):
    __tablename__ = "ticket_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    
    # Response Details
    message = Column(Text, nullable=False)
    is_staff_response = Column(Boolean, default=False)
    staff_name = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    ticket = relationship("SupportTicket", back_populates="responses")

