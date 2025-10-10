from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import secrets
from app.models.database import Base


class DomainAllowlist(Base):
    """Domain allowlist for public keys"""
    __tablename__ = "domain_allowlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Domain details
    domain = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Public key for this domain
    public_key = Column(String, unique=True, nullable=False, index=True)
    
    # Validation
    verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    
    # Usage stats
    total_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="domain_allowlists")
    
    @staticmethod
    def generate_public_key(prefix: str = "pk") -> str:
        """Generate a secure public key"""
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_live_{random_part}"
    
    @staticmethod
    def generate_verification_token() -> str:
        """Generate a verification token"""
        return secrets.token_urlsafe(32)


class IPAllowlist(Base):
    """IP allowlist for API access"""
    __tablename__ = "ip_allowlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # IP details
    ip_address = Column(String, nullable=False, index=True)
    ip_range = Column(String, nullable=True)  # CIDR notation, e.g., 192.168.1.0/24
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Usage stats
    total_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="ip_allowlists")


class SecurityLog(Base):
    """Security event logs"""
    __tablename__ = "security_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Event details
    event_type = Column(String, nullable=False, index=True)  # access_denied, unauthorized_ip, etc.
    severity = Column(String, default="info")  # info, warning, error, critical
    message = Column(Text, nullable=False)
    
    # Request details
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    endpoint = Column(String, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="security_logs")

