from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime

from app.models import get_db, User
from app.core.security import get_current_user, get_password_hash, verify_password

router = APIRouter()


# Pydantic models
class ProfileResponse(BaseModel):
    id: int
    email: str
    full_name: str
    subscription_tier: str
    credit_balance: float
    total_minutes_used: float
    monthly_minutes_used: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class AccountStatsResponse(BaseModel):
    total_agents: int
    total_calls: int
    total_minutes: float
    total_cost: float
    account_age_days: int


# Get current user profile
@router.get("/me", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile"""
    return current_user


# Update user profile
@router.put("/me", response_model=ProfileResponse)
async def update_profile(
    profile_data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    
    # Check if email is already taken by another user
    if profile_data.email and profile_data.email != current_user.email:
        existing_user = db.query(User).filter(
            User.email == profile_data.email,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        current_user.email = profile_data.email
    
    if profile_data.full_name:
        current_user.full_name = profile_data.full_name
    
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(current_user)
    
    return current_user


# Change password
@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"success": True, "message": "Password changed successfully"}


# Get account statistics
@router.get("/stats", response_model=AccountStatsResponse)
async def get_account_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get account statistics"""
    from app.models import VoiceAgent, Call, UsageRecord
    from sqlalchemy import func
    
    # Count agents
    total_agents = db.query(func.count(VoiceAgent.id)).filter(
        VoiceAgent.user_id == current_user.id
    ).scalar() or 0
    
    # Count calls
    total_calls = db.query(func.count(Call.id)).filter(
        Call.user_id == current_user.id
    ).scalar() or 0
    
    # Sum usage
    usage_result = db.query(
        func.sum(UsageRecord.minutes_used).label("total_minutes"),
        func.sum(UsageRecord.cost).label("total_cost")
    ).filter(
        UsageRecord.user_id == current_user.id
    ).first()
    
    total_minutes = float(usage_result.total_minutes or 0)
    total_cost = float(usage_result.total_cost or 0)
    
    # Calculate account age
    account_age = (datetime.utcnow() - current_user.created_at).days
    
    return AccountStatsResponse(
        total_agents=total_agents,
        total_calls=total_calls,
        total_minutes=total_minutes,
        total_cost=total_cost,
        account_age_days=account_age
    )


# Delete account
@router.delete("/me")
async def delete_account(
    password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete user account (requires password confirmation)"""
    
    # Verify password
    if not verify_password(password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect"
        )
    
    # Soft delete - deactivate account
    current_user.is_active = False
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"success": True, "message": "Account deactivated successfully"}

