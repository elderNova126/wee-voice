from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
from pydantic import BaseModel, field_serializer
from datetime import datetime, timedelta

from app.models import (
    get_db,
    User,
    VoiceAgent,
    Call,
    UsageRecord,
    Transaction,
    PaymentStatus,
    SupportTicket,
    TicketStatus,
    TicketPriority,
    TicketResponse,
)
from app.core.security import get_current_admin_user

router = APIRouter()


class UserUpdateRequest(BaseModel):
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    subscription_tier: Optional[str] = None


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    is_approved: bool
    subscription_tier: str
    total_minutes_used: float
    monthly_minutes_used: float
    credit_balance: float
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() if dt else None
    
    @field_serializer('subscription_tier')
    def serialize_subscription_tier(self, tier, _info):
        # Handle both Enum and string
        if hasattr(tier, 'value'):
            return tier.value
        return str(tier)
    
    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    is_approved: bool
    subscription_tier: str
    total_minutes_used: float
    monthly_minutes_used: float
    credit_balance: float
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime, _info):
        return dt.isoformat() if dt else None
    
    @field_serializer('subscription_tier')
    def serialize_subscription_tier(self, tier, _info):
        # Handle both Enum and string
        if hasattr(tier, 'value'):
            return tier.value
        return str(tier)
    
    class Config:
        from_attributes = True


class OverviewTotals(BaseModel):
    total_users: int
    active_users: int
    pending_users: int
    total_agents: int
    active_agents: int
    public_agents: int
    total_calls: int
    open_tickets: int


class OverviewUsageMetrics(BaseModel):
    minutes_total: float
    minutes_last_30_days: float
    calls_last_30_days: int
    calls_last_24_hours: int


class OverviewFinancialMetrics(BaseModel):
    revenue_total: float
    revenue_last_30_days: float


class RecentUser(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: datetime
    is_approved: bool

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() if dt else None


class RecentAgent(BaseModel):
    id: int
    name: str
    owner_name: str
    owner_email: str
    is_public: bool
    is_active: bool
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() if dt else None


class RecentTicket(BaseModel):
    id: int
    ticket_number: str
    subject: str
    status: str
    priority: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() if dt else None


class OverviewRecent(BaseModel):
    users: List[RecentUser]
    agents: List[RecentAgent]
    tickets: List[RecentTicket]


class AdminOverviewResponse(BaseModel):
    totals: OverviewTotals
    usage: OverviewUsageMetrics
    financial: OverviewFinancialMetrics
    recent: OverviewRecent


class AgentOwnerInfo(BaseModel):
    id: int
    full_name: str
    email: str


class AgentMetrics(BaseModel):
    calls_count: int
    minutes_used: float


class AdminAgentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    language: str
    voice_id: str
    is_active: bool
    is_public: bool
    rag_enabled: bool
    created_at: datetime
    owner: AgentOwnerInfo
    metrics: AgentMetrics

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() if dt else None


class AdminAgentUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    rag_enabled: Optional[bool] = None


class AdminSupportTicketResponse(BaseModel):
    id: int
    ticket_number: str
    subject: str
    name: str
    email: str
    status: str
    priority: str
    category: str
    created_at: datetime
    updated_at: datetime
    responses_count: int
    last_response_at: Optional[datetime]

    @field_serializer("created_at", "updated_at", "last_response_at")
    def serialize_datetime(self, dt: Optional[datetime], _info):
        return dt.isoformat() if dt else None


class AdminSupportTicketUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    response_message: Optional[str] = None


def _aggregate_agent_metrics(db: Session, agent_ids: List[int]):
    """Return aggregated usage minutes and call counts for agents."""
    if not agent_ids:
        return {}, {}

    usage_rows = (
        db.query(UsageRecord.agent_id, func.coalesce(func.sum(UsageRecord.minutes_used), 0.0))
        .filter(UsageRecord.agent_id.in_(agent_ids))
        .group_by(UsageRecord.agent_id)
        .all()
    )
    usage_map = {agent_id: float(minutes or 0.0) for agent_id, minutes in usage_rows}

    call_rows = (
        db.query(Call.agent_id, func.count(Call.id))
        .filter(Call.agent_id.in_(agent_ids))
        .group_by(Call.agent_id)
        .all()
    )
    call_map = {agent_id: count for agent_id, count in call_rows}

    # Ensure all agent IDs have entries
    for agent_id in agent_ids:
        usage_map.setdefault(agent_id, 0.0)
        call_map.setdefault(agent_id, 0)

    return usage_map, call_map


def _serialize_admin_agent(agent: VoiceAgent, owner: User, minutes_used: float, calls_count: int) -> AdminAgentResponse:
    return AdminAgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        language=agent.language,
        voice_id=agent.voice_id,
        is_active=agent.is_active,
        is_public=agent.is_public,
        rag_enabled=agent.rag_enabled,
        created_at=agent.created_at,
        owner=AgentOwnerInfo(
            id=owner.id,
            full_name=owner.full_name,
            email=owner.email,
        ),
        metrics=AgentMetrics(
            calls_count=calls_count,
            minutes_used=float(minutes_used or 0.0),
        ),
    )


def _serialize_admin_support_ticket(ticket: SupportTicket) -> AdminSupportTicketResponse:
    responses = ticket.responses or []
    last_response_at = max((response.created_at for response in responses), default=None)

    status_value = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
    priority_value = ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority)
    category_value = ticket.category.value if hasattr(ticket.category, "value") else str(ticket.category)

    return AdminSupportTicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        name=ticket.name,
        email=ticket.email,
        status=status_value,
        priority=priority_value,
        category=category_value,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        responses_count=len(responses),
        last_response_at=last_response_at,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """High-level platform overview for administrators."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    twenty_four_hours_ago = now - timedelta(hours=24)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa: E712
    pending_users = db.query(func.count(User.id)).filter(User.is_approved == False).scalar() or 0  # noqa: E712

    total_agents = db.query(func.count(VoiceAgent.id)).scalar() or 0
    active_agents = db.query(func.count(VoiceAgent.id)).filter(VoiceAgent.is_active == True).scalar() or 0  # noqa: E712
    public_agents = db.query(func.count(VoiceAgent.id)).filter(VoiceAgent.is_public == True).scalar() or 0  # noqa: E712

    total_calls = db.query(func.count(Call.id)).scalar() or 0
    calls_last_30_days = db.query(func.count(Call.id)).filter(Call.created_at >= thirty_days_ago).scalar() or 0
    calls_last_24_hours = db.query(func.count(Call.id)).filter(Call.created_at >= twenty_four_hours_ago).scalar() or 0

    minutes_total = db.query(func.coalesce(func.sum(UsageRecord.minutes_used), 0.0)).scalar() or 0.0
    minutes_last_30_days = (
        db.query(func.coalesce(func.sum(UsageRecord.minutes_used), 0.0))
        .filter(UsageRecord.date >= thirty_days_ago)
        .scalar()
        or 0.0
    )

    revenue_total = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.status == PaymentStatus.SUCCEEDED)
        .scalar()
        or 0.0
    )
    revenue_last_30_days = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(
            Transaction.status == PaymentStatus.SUCCEEDED,
            Transaction.created_at >= thirty_days_ago,
        )
        .scalar()
        or 0.0
    )

    open_tickets = (
        db.query(func.count(SupportTicket.id))
        .filter(SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]))
        .scalar()
        or 0
    )

    recent_users = [
        RecentUser(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            created_at=user.created_at,
            is_approved=user.is_approved,
        )
        for user in db.query(User)
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    ]

    recent_agents = [
        RecentAgent(
            id=agent.id,
            name=agent.name,
            owner_name=owner.full_name,
            owner_email=owner.email,
            is_public=agent.is_public,
            is_active=agent.is_active,
            created_at=agent.created_at,
        )
        for agent, owner in (
            db.query(VoiceAgent, User)
            .join(User, VoiceAgent.user_id == User.id)
            .order_by(VoiceAgent.created_at.desc())
            .limit(5)
            .all()
        )
    ]

    recent_tickets = [
        RecentTicket(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            subject=ticket.subject,
            status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            priority=ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
            created_at=ticket.created_at,
        )
        for ticket in (
            db.query(SupportTicket)
            .order_by(SupportTicket.created_at.desc())
            .limit(5)
            .all()
        )
    ]

    totals = OverviewTotals(
        total_users=total_users,
        active_users=active_users,
        pending_users=pending_users,
        total_agents=total_agents,
        active_agents=active_agents,
        public_agents=public_agents,
        total_calls=total_calls,
        open_tickets=open_tickets,
    )

    usage = OverviewUsageMetrics(
        minutes_total=float(minutes_total),
        minutes_last_30_days=float(minutes_last_30_days),
        calls_last_30_days=calls_last_30_days,
        calls_last_24_hours=calls_last_24_hours,
    )

    financial = OverviewFinancialMetrics(
        revenue_total=float(revenue_total),
        revenue_last_30_days=float(revenue_last_30_days),
    )

    recent = OverviewRecent(
        users=recent_users,
        agents=recent_agents,
        tickets=recent_tickets,
    )

    return AdminOverviewResponse(
        totals=totals,
        usage=usage,
        financial=financial,
        recent=recent,
    )


@router.get("/users", response_model=List[UserListItem])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    is_approved: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|email|full_name)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List all users with filtering and pagination"""
    query = db.query(User)
    
    # Apply filters
    if search:
        search_filter = or_(
            User.email.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    if is_approved is not None:
        query = query.filter(User.is_approved == is_approved)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Apply sorting
    sort_column = getattr(User, sort_by)
    if order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    return users


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get user details by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.patch("/users/{user_id}", response_model=UserDetailResponse)
def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update user properties (approval, active status, etc.)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from modifying their own superuser status
    if user_id == current_admin.id and user_data.is_superuser is False:
        raise HTTPException(
            status_code=400,
            detail="You cannot revoke your own admin privileges"
        )
    
    # Update fields if provided
    if user_data.is_approved is not None:
        user.is_approved = user_data.is_approved
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.is_superuser is not None:
        user.is_superuser = user_data.is_superuser
    
    if user_data.subscription_tier is not None:
        from app.models import SubscriptionTier
        try:
            user.subscription_tier = SubscriptionTier(user_data.subscription_tier)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid subscription tier: {user_data.subscription_tier}"
            )
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Approve a user (convenience endpoint)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_approved:
        return {"message": "User is already approved", "user": user}
    
    user.is_approved = True
    db.commit()
    db.refresh(user)
    
    return {"message": "User approved successfully", "user": user}


@router.post("/users/{user_id}/reject")
def reject_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Reject/unapprove a user (convenience endpoint)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_approved:
        return {"message": "User is already not approved", "user": user}
    
    user.is_approved = False
    db.commit()
    db.refresh(user)
    
    return {"message": "User rejected successfully", "user": user}


@router.post("/users/{user_id}/activate")
def activate_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Activate a user account"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_active:
        return {"message": "User is already active", "user": user}
    
    user.is_active = True
    db.commit()
    db.refresh(user)
    
    return {"message": "User activated successfully", "user": user}


@router.post("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Deactivate a user account"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deactivating themselves
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate your own account"
        )
    
    if not user.is_active:
        return {"message": "User is already inactive", "user": user}
    
    user.is_active = False
    db.commit()
    db.refresh(user)
    
    return {"message": "User deactivated successfully", "user": user}


@router.get("/agents", response_model=List[AdminAgentResponse])
def list_admin_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_public: Optional[bool] = Query(None),
    owner_id: Optional[int] = Query(None),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List voice agents across the platform."""
    query = db.query(VoiceAgent, User).join(User, VoiceAgent.user_id == User.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                VoiceAgent.name.ilike(search_term),
                VoiceAgent.description.ilike(search_term),
                User.email.ilike(search_term),
                User.full_name.ilike(search_term),
            )
        )

    if is_active is not None:
        query = query.filter(VoiceAgent.is_active == is_active)

    if is_public is not None:
        query = query.filter(VoiceAgent.is_public == is_public)

    if owner_id is not None:
        query = query.filter(VoiceAgent.user_id == owner_id)

    agents_data = (
        query.order_by(desc(VoiceAgent.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    agent_ids = [agent.id for agent, _ in agents_data]
    usage_map, call_map = _aggregate_agent_metrics(db, agent_ids)

    return [
        _serialize_admin_agent(
            agent=agent,
            owner=owner,
            minutes_used=usage_map.get(agent.id, 0.0),
            calls_count=call_map.get(agent.id, 0),
        )
        for agent, owner in agents_data
    ]


@router.patch("/agents/{agent_id}", response_model=AdminAgentResponse)
def update_admin_agent(
    agent_id: int,
    agent_data: AdminAgentUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update agent visibility and status flags (admin only)."""
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_fields = agent_data.model_dump(exclude_unset=True)

    if not update_fields:
        owner = agent.user or db.query(User).filter(User.id == agent.user_id).first()
        usage_map, call_map = _aggregate_agent_metrics(db, [agent.id])
        return _serialize_admin_agent(
            agent=agent,
            owner=owner,
            minutes_used=usage_map.get(agent.id, 0.0),
            calls_count=call_map.get(agent.id, 0),
        )

    if agent_data.is_active is not None:
        agent.is_active = agent_data.is_active

    if agent_data.is_public is not None:
        agent.is_public = agent_data.is_public

    if agent_data.rag_enabled is not None:
        agent.rag_enabled = agent_data.rag_enabled

    db.commit()
    db.refresh(agent)

    owner = agent.user or db.query(User).filter(User.id == agent.user_id).first()
    usage_map, call_map = _aggregate_agent_metrics(db, [agent.id])

    return _serialize_admin_agent(
        agent=agent,
        owner=owner,
        minutes_used=usage_map.get(agent.id, 0.0),
        calls_count=call_map.get(agent.id, 0),
    )


@router.get("/users/stats/summary")
def get_user_stats(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get user statistics summary"""
    total_users = db.query(User).count()
    approved_users = db.query(User).filter(User.is_approved == True).count()
    pending_users = db.query(User).filter(User.is_approved == False).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.is_superuser == True).count()
    
    return {
        "total_users": total_users,
        "approved_users": approved_users,
        "pending_users": pending_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "inactive_users": total_users - active_users
    }


@router.get("/support/tickets", response_model=List[AdminSupportTicketResponse])
def list_support_tickets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List support tickets for administrators."""
    query = db.query(SupportTicket).order_by(desc(SupportTicket.created_at))

    if status:
        try:
            status_enum = TicketStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status value: {status}")
        query = query.filter(SupportTicket.status == status_enum)

    if priority:
        try:
            priority_enum = TicketPriority(priority)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority value: {priority}")
        query = query.filter(SupportTicket.priority == priority_enum)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                SupportTicket.subject.ilike(search_term),
                SupportTicket.email.ilike(search_term),
                SupportTicket.ticket_number.ilike(search_term),
                SupportTicket.name.ilike(search_term),
            )
        )

    tickets = query.offset(skip).limit(limit).all()

    return [_serialize_admin_support_ticket(ticket) for ticket in tickets]


@router.patch("/support/tickets/{ticket_id}", response_model=AdminSupportTicketResponse)
def update_support_ticket(
    ticket_id: int,
    ticket_data: AdminSupportTicketUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update ticket status/priority and add staff responses."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    updated = False

    if ticket_data.status is not None:
        try:
            new_status = TicketStatus(ticket_data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status value: {ticket_data.status}")

        ticket.status = new_status
        updated = True

        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = datetime.utcnow()
            ticket.closed_at = None
        elif new_status == TicketStatus.CLOSED:
            ticket.closed_at = datetime.utcnow()
        else:
            ticket.resolved_at = None
            ticket.closed_at = None

    if ticket_data.priority is not None:
        try:
            new_priority = TicketPriority(ticket_data.priority)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority value: {ticket_data.priority}")

        ticket.priority = new_priority
        updated = True

    if ticket_data.response_message:
        response = TicketResponse(
            ticket_id=ticket.id,
            message=ticket_data.response_message,
            is_staff_response=True,
            staff_name=current_admin.full_name,
        )
        db.add(response)
        updated = True

    if updated:
        ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return _serialize_admin_support_ticket(ticket)

