from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, validator
import ipaddress
import re

from app.models import get_db, User, DomainAllowlist, IPAllowlist, SecurityLog
from app.core.security import get_current_user

router = APIRouter()


# Pydantic models
class DomainAllowlistCreate(BaseModel):
    domain: str
    description: Optional[str] = None
    
    @validator('domain')
    def validate_domain(cls, v):
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, v.lower()):
            raise ValueError('Invalid domain format')
        return v.lower()


class DomainAllowlistUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DomainAllowlistResponse(BaseModel):
    id: int
    domain: str
    description: Optional[str]
    is_active: bool
    public_key: str
    verified: bool
    verification_token: Optional[str]
    total_requests: int
    last_used_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class IPAllowlistCreate(BaseModel):
    ip_address: str
    ip_range: Optional[str] = None
    description: Optional[str] = None
    
    @validator('ip_address')
    def validate_ip(cls, v):
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError('Invalid IP address format')
        return v
    
    @validator('ip_range')
    def validate_ip_range(cls, v):
        if v:
            try:
                ipaddress.ip_network(v, strict=False)
            except ValueError:
                raise ValueError('Invalid IP range format (use CIDR notation)')
        return v


class IPAllowlistUpdate(BaseModel):
    description: Optional[str] = None
    is_active: Optional[bool] = None


class IPAllowlistResponse(BaseModel):
    id: int
    ip_address: str
    ip_range: Optional[str]
    description: Optional[str]
    is_active: bool
    total_requests: int
    last_used_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class SecurityLogResponse(BaseModel):
    id: int
    event_type: str
    severity: str
    message: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    endpoint: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Domain Allowlist endpoints

@router.get("/domains", response_model=List[DomainAllowlistResponse])
async def get_domain_allowlists(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all domain allowlists for the current user"""
    domains = db.query(DomainAllowlist).filter(
        DomainAllowlist.user_id == current_user.id
    ).order_by(DomainAllowlist.created_at.desc()).offset(skip).limit(limit).all()
    
    return domains


@router.post("/domains", response_model=DomainAllowlistResponse)
async def create_domain_allowlist(
    domain_data: DomainAllowlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a domain to the allowlist and generate a public key"""
    
    # Check if domain already exists for this user
    existing = db.query(DomainAllowlist).filter(
        DomainAllowlist.user_id == current_user.id,
        DomainAllowlist.domain == domain_data.domain
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain already in allowlist"
        )
    
    # Generate public key and verification token
    public_key = DomainAllowlist.generate_public_key()
    verification_token = DomainAllowlist.generate_verification_token()
    
    # Create domain allowlist entry
    domain_allowlist = DomainAllowlist(
        user_id=current_user.id,
        domain=domain_data.domain,
        description=domain_data.description,
        public_key=public_key,
        verification_token=verification_token,
        is_active=True,
        verified=False
    )
    
    db.add(domain_allowlist)
    db.commit()
    db.refresh(domain_allowlist)
    
    # Log security event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="domain_added",
        severity="info",
        message=f"Domain added to allowlist: {domain_data.domain}"
    )
    db.add(log)
    db.commit()
    
    return domain_allowlist


@router.put("/domains/{domain_id}", response_model=DomainAllowlistResponse)
async def update_domain_allowlist(
    domain_id: int,
    domain_data: DomainAllowlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a domain allowlist entry"""
    
    domain = db.query(DomainAllowlist).filter(
        DomainAllowlist.id == domain_id,
        DomainAllowlist.user_id == current_user.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Update fields
    if domain_data.description is not None:
        domain.description = domain_data.description
    if domain_data.is_active is not None:
        domain.is_active = domain_data.is_active
    
    db.commit()
    db.refresh(domain)
    
    return domain


@router.delete("/domains/{domain_id}")
async def delete_domain_allowlist(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a domain from the allowlist"""
    
    domain = db.query(DomainAllowlist).filter(
        DomainAllowlist.id == domain_id,
        DomainAllowlist.user_id == current_user.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Log security event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="domain_removed",
        severity="info",
        message=f"Domain removed from allowlist: {domain.domain}"
    )
    db.add(log)
    
    db.delete(domain)
    db.commit()
    
    return {"success": True, "message": "Domain removed from allowlist"}


@router.post("/domains/{domain_id}/regenerate-key", response_model=DomainAllowlistResponse)
async def regenerate_domain_key(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerate the public key for a domain"""
    
    domain = db.query(DomainAllowlist).filter(
        DomainAllowlist.id == domain_id,
        DomainAllowlist.user_id == current_user.id
    ).first()
    
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Generate new key
    domain.public_key = DomainAllowlist.generate_public_key()
    domain.verification_token = DomainAllowlist.generate_verification_token()
    domain.verified = False
    
    db.commit()
    db.refresh(domain)
    
    # Log security event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="key_regenerated",
        severity="warning",
        message=f"Public key regenerated for domain: {domain.domain}"
    )
    db.add(log)
    db.commit()
    
    return domain


# IP Allowlist endpoints

@router.get("/ips", response_model=List[IPAllowlistResponse])
async def get_ip_allowlists(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all IP allowlists for the current user"""
    ips = db.query(IPAllowlist).filter(
        IPAllowlist.user_id == current_user.id
    ).order_by(IPAllowlist.created_at.desc()).offset(skip).limit(limit).all()
    
    return ips


@router.post("/ips", response_model=IPAllowlistResponse)
async def create_ip_allowlist(
    ip_data: IPAllowlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add an IP to the allowlist"""
    
    # Check if IP already exists for this user
    existing = db.query(IPAllowlist).filter(
        IPAllowlist.user_id == current_user.id,
        IPAllowlist.ip_address == ip_data.ip_address
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP address already in allowlist"
        )
    
    # Create IP allowlist entry
    ip_allowlist = IPAllowlist(
        user_id=current_user.id,
        ip_address=ip_data.ip_address,
        ip_range=ip_data.ip_range,
        description=ip_data.description,
        is_active=True
    )
    
    db.add(ip_allowlist)
    db.commit()
    db.refresh(ip_allowlist)
    
    # Log security event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="ip_added",
        severity="info",
        message=f"IP added to allowlist: {ip_data.ip_address}",
        ip_address=ip_data.ip_address
    )
    db.add(log)
    db.commit()
    
    return ip_allowlist


@router.put("/ips/{ip_id}", response_model=IPAllowlistResponse)
async def update_ip_allowlist(
    ip_id: int,
    ip_data: IPAllowlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an IP allowlist entry"""
    
    ip = db.query(IPAllowlist).filter(
        IPAllowlist.id == ip_id,
        IPAllowlist.user_id == current_user.id
    ).first()
    
    if not ip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP not found"
        )
    
    # Update fields
    if ip_data.description is not None:
        ip.description = ip_data.description
    if ip_data.is_active is not None:
        ip.is_active = ip_data.is_active
    
    db.commit()
    db.refresh(ip)
    
    return ip


@router.delete("/ips/{ip_id}")
async def delete_ip_allowlist(
    ip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove an IP from the allowlist"""
    
    ip = db.query(IPAllowlist).filter(
        IPAllowlist.id == ip_id,
        IPAllowlist.user_id == current_user.id
    ).first()
    
    if not ip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP not found"
        )
    
    # Log security event
    log = SecurityLog(
        user_id=current_user.id,
        event_type="ip_removed",
        severity="info",
        message=f"IP removed from allowlist: {ip.ip_address}",
        ip_address=ip.ip_address
    )
    db.add(log)
    
    db.delete(ip)
    db.commit()
    
    return {"success": True, "message": "IP removed from allowlist"}


# Security logs

@router.get("/logs", response_model=List[SecurityLogResponse])
async def get_security_logs(
    skip: int = 0,
    limit: int = 100,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get security logs for the current user"""
    
    query = db.query(SecurityLog).filter(SecurityLog.user_id == current_user.id)
    
    if event_type:
        query = query.filter(SecurityLog.event_type == event_type)
    
    if severity:
        query = query.filter(SecurityLog.severity == severity)
    
    logs = query.order_by(SecurityLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return logs


# Helper function to check if IP is allowed
def check_ip_allowed(ip_address: str, user_id: int, db: Session) -> bool:
    """Check if an IP address is allowed for a user"""
    
    # Get all active IP allowlists for the user
    ip_allowlists = db.query(IPAllowlist).filter(
        IPAllowlist.user_id == user_id,
        IPAllowlist.is_active == True
    ).all()
    
    # If no allowlists, allow all
    if not ip_allowlists:
        return True
    
    try:
        ip = ipaddress.ip_address(ip_address)
        
        for allowlist in ip_allowlists:
            # Check exact IP match
            if allowlist.ip_address == ip_address:
                return True
            
            # Check IP range match
            if allowlist.ip_range:
                network = ipaddress.ip_network(allowlist.ip_range, strict=False)
                if ip in network:
                    return True
        
        return False
    
    except ValueError:
        return False


# Helper function to check if domain is allowed
def check_domain_allowed(domain: str, public_key: str, db: Session) -> tuple[bool, Optional[User]]:
    """Check if a domain and public key combination is valid"""
    
    domain_allowlist = db.query(DomainAllowlist).filter(
        DomainAllowlist.domain == domain.lower(),
        DomainAllowlist.public_key == public_key,
        DomainAllowlist.is_active == True
    ).first()
    
    if domain_allowlist:
        # Update usage stats
        domain_allowlist.total_requests += 1
        domain_allowlist.last_used_at = datetime.utcnow()
        db.commit()
        
        # Get user
        user = db.query(User).filter(User.id == domain_allowlist.user_id).first()
        return True, user
    
    return False, None

