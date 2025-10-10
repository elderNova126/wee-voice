from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
import secrets
import string

from app.models import get_db, User, SupportTicket, TicketResponse, TicketStatus, TicketPriority, TicketCategory
from app.core.security import get_current_user, get_optional_user
from app.services.email_service import EmailService

router = APIRouter()

# Pydantic Models
class SupportTicketCreate(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str
    category: str
    
    @validator('category')
    def validate_category(cls, v):
        valid_categories = [c.value for c in TicketCategory]
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {", ".join(valid_categories)}')
        return v
    
    @validator('subject')
    def validate_subject(cls, v):
        if len(v) < 5:
            raise ValueError('Subject must be at least 5 characters long')
        if len(v) > 200:
            raise ValueError('Subject must be less than 200 characters')
        return v
    
    @validator('message')
    def validate_message(cls, v):
        if len(v) < 10:
            raise ValueError('Message must be at least 10 characters long')
        if len(v) > 5000:
            raise ValueError('Message must be less than 5000 characters')
        return v

class TicketResponseCreate(BaseModel):
    message: str
    
    @validator('message')
    def validate_message(cls, v):
        if len(v) < 1:
            raise ValueError('Message cannot be empty')
        if len(v) > 5000:
            raise ValueError('Message must be less than 5000 characters')
        return v

class TicketResponseSchema(BaseModel):
    id: int
    message: str
    is_staff_response: bool
    staff_name: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class SupportTicketResponse(BaseModel):
    id: int
    ticket_number: str
    name: str
    email: str
    subject: str
    message: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    responses: List[TicketResponseSchema] = []
    
    class Config:
        from_attributes = True

def generate_ticket_number() -> str:
    """Generate a unique ticket number"""
    prefix = "TKT"
    random_part = ''.join(secrets.choice(string.digits) for _ in range(8))
    return f"{prefix}-{random_part}"

@router.post("/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    ticket_data: SupportTicketCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Create a new support ticket
    Can be used by authenticated or non-authenticated users
    """
    # Generate unique ticket number
    ticket_number = generate_ticket_number()
    while db.query(SupportTicket).filter(SupportTicket.ticket_number == ticket_number).first():
        ticket_number = generate_ticket_number()
    
    # Get user agent and IP
    user_agent = request.headers.get('user-agent', 'Unknown')
    ip_address = request.client.host if request.client else 'Unknown'
    
    # Create ticket
    ticket = SupportTicket(
        ticket_number=ticket_number,
        user_id=current_user.id if current_user else None,
        name=ticket_data.name,
        email=ticket_data.email,
        subject=ticket_data.subject,
        message=ticket_data.message,
        category=ticket_data.category,
        priority=TicketPriority.MEDIUM,  # Default priority
        user_agent=user_agent,
        ip_address=ip_address
    )
    
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # Send confirmation email to user
    try:
        EmailService.send_support_ticket_confirmation(
            to_email=ticket_data.email,
            name=ticket_data.name,
            ticket_number=ticket_number,
            subject=ticket_data.subject,
            message=ticket_data.message
        )
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")
    
    # Send notification to support team
    try:
        EmailService.send_support_ticket_notification(
            ticket_number=ticket_number,
            name=ticket_data.name,
            email=ticket_data.email,
            subject=ticket_data.subject,
            message=ticket_data.message,
            category=ticket_data.category,
            priority=TicketPriority.MEDIUM.value
        )
    except Exception as e:
        print(f"Failed to send support notification: {e}")
    
    return ticket

@router.get("/tickets", response_model=List[SupportTicketResponse])
async def get_user_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all tickets for the current user"""
    tickets = db.query(SupportTicket).filter(
        SupportTicket.user_id == current_user.id
    ).order_by(desc(SupportTicket.created_at)).all()
    
    return tickets

@router.get("/tickets/{ticket_number}", response_model=SupportTicketResponse)
async def get_ticket_by_number(
    ticket_number: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get a specific ticket by ticket number"""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.ticket_number == ticket_number
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Check access: user must own the ticket or be the email owner (for non-authenticated)
    if current_user:
        if ticket.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket"
            )
    
    return ticket

@router.post("/tickets/{ticket_number}/responses", response_model=TicketResponseSchema)
async def add_ticket_response(
    ticket_number: str,
    response_data: TicketResponseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a response to a ticket (user only)"""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.ticket_number == ticket_number
    ).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Check access
    if ticket.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this ticket"
        )
    
    # Create response
    response = TicketResponse(
        ticket_id=ticket.id,
        message=response_data.message,
        is_staff_response=False
    )
    
    db.add(response)
    
    # Update ticket status if closed
    if ticket.status == TicketStatus.CLOSED:
        ticket.status = TicketStatus.OPEN
        ticket.closed_at = None
    
    db.commit()
    db.refresh(response)
    
    return response

@router.get("/categories")
async def get_ticket_categories():
    """Get all available ticket categories"""
    return {
        "categories": [
            {"value": c.value, "label": c.value.replace('_', ' ').title()}
            for c in TicketCategory
        ]
    }

