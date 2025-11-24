"""
Optimized Database Queries for Calls API
Prevents N+1 queries and uses proper indexing
"""
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc, func, and_, or_
from typing import List, Optional
from app.models import Call, VoiceAgent, User, CallMessage


def get_calls_optimized(
    db: Session,
    user_id: int,
    agent_id: Optional[int] = None,
    status: Optional[str] = None,
    action_required: Optional[bool] = None,
    favorite: Optional[bool] = None,
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 10
) -> tuple[List[Call], int]:
    """
    Optimized call query with proper joins and indexing
    Prevents N+1 query problem
    """
    # Base query with eager loading
    query = db.query(Call).options(
        joinedload(Call.agent),  # Eager load agent data
        joinedload(Call.user)   # Eager load user data
    ).filter(Call.user_id == user_id)
    
    # Apply filters
    if agent_id:
        query = query.filter(Call.agent_id == agent_id)
    
    if status:
        query = query.filter(Call.status == status)
    
    if action_required is not None:
        if action_required:
            # Calls with action items/tags
            query = query.filter(
                or_(
                    func.json_array_length(Call.action_items) > 0,
                    func.json_array_length(Call.action_tags) > 0
                )
            )
        else:
            # Calls without action items/tags
            query = query.filter(
                and_(
                    or_(
                        Call.action_items.is_(None),
                        func.json_array_length(Call.action_items) == 0
                    ),
                    or_(
                        Call.action_tags.is_(None),
                        func.json_array_length(Call.action_tags) == 0
                    )
                )
            )
    
    if favorite is not None:
        query = query.filter(Call.is_favorite == favorite)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Call.transcript.ilike(search_term),
                Call.summary.ilike(search_term),
                Call.caller_name.ilike(search_term),
                Call.caller_phone.ilike(search_term)
            )
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    calls = query.order_by(desc(Call.created_at)).offset(offset).limit(limit).all()
    
    return calls, total


def get_call_with_messages(db: Session, call_id: int, user_id: int) -> Optional[Call]:
    """
    Get a single call with messages in one query
    """
    return db.query(Call).options(
        joinedload(Call.agent),
        joinedload(Call.user),
        selectinload(Call.messages).options(
            joinedload(CallMessage.call)
        )
    ).filter(
        Call.id == call_id,
        Call.user_id == user_id
    ).first()


def get_call_stats_optimized(db: Session, user_id: int, days: int = 30):
    """
    Optimized stats query using database aggregation
    """
    from datetime import datetime, timedelta
    
    since_date = datetime.utcnow() - timedelta(days=days)
    
    # Single aggregation query
    stats = db.query(
        func.count(Call.id).label('total_calls'),
        func.sum(Call.duration_seconds).label('total_duration'),
        func.sum(Call.cost).label('total_cost'),
        func.avg(Call.duration_seconds).label('avg_duration')
    ).filter(
        Call.user_id == user_id,
        Call.created_at >= since_date
    ).first()
    
    return {
        'total_calls': stats.total_calls or 0,
        'total_duration': float(stats.total_duration or 0),
        'total_cost': float(stats.total_cost or 0),
        'avg_duration': float(stats.avg_duration or 0)
    }

