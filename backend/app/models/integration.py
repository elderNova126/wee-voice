from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Enum, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class IntegrationType(str, enum.Enum):
    """Supported integration types"""
    CALENDAR = "calendar"
    EMAIL = "email"
    CONTACT_MANAGEMENT = "contact_management"
    DATABASE = "database"
    CRM = "crm"
    ACCOUNTING = "accounting"
    OTHER = "other"


class IntegrationProvider(str, enum.Enum):
    """Supported integration providers"""
    # Calendar
    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK_CALENDAR = "outlook_calendar"
    CALENDLY = "calendly"
    
    # Email
    GMAIL = "gmail"
    OUTLOOK_EMAIL = "outlook_email"
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    
    # Contact Management
    HUBSPOT_CONTACTS = "hubspot_contacts"
    SALESFORCE_CONTACTS = "salesforce_contacts"
    ZAPIER = "zapier"
    
    # Database
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    
    # CRM
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    PIPEDRIVE = "pipedrive"
    ZOHO_CRM = "zoho_crm"
    
    # Accounting
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    SAGE = "sage"
    WAVE = "wave"
    
    # Other
    WEBHOOK = "webhook"
    REST_API = "rest_api"
    CUSTOM = "custom"


class IntegrationStatus(str, enum.Enum):
    """Integration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING_AUTH = "pending_auth"


class Integration(Base):
    """Model for storing user integrations"""
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Integration identification
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # Use String type to match database schema (VARCHAR instead of ENUM)
    # Store enum values as strings (e.g., "calendar", "email")
    integration_type = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    
    # Configuration (encrypted credentials stored here)
    config = Column(JSON, nullable=False)  # Stores connection details, API keys, etc.
    
    # Status
    # Use String type to match database schema
    status = Column(String(50), default=IntegrationStatus.INACTIVE.value)
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Metadata
    integration_metadata = Column(JSON, nullable=True)  # Additional provider-specific metadata
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="integrations")
    agents = relationship("AgentIntegration", back_populates="integration", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Integration(id={self.id}, name='{self.name}', type='{self.integration_type}', provider='{self.provider}')>"

