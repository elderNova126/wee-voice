from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from pydantic import BaseModel, field_serializer
from datetime import datetime

from app.models import get_db, User
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

