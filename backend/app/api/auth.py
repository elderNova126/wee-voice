from datetime import timedelta, datetime
from typing import Any
import secrets
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    get_current_active_user,
    generate_api_key,
)
from app.models import get_db, User, APIKey, SubscriptionTier
from app.services.email_service import EmailService

router = APIRouter()


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 72:
            raise ValueError('Password cannot be longer than 72 characters')
        return v


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    subscription_tier: str
    is_active: bool
    is_approved: bool
    is_superuser: bool
    
    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: Any
    
    class Config:
        from_attributes = True


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 72:
            raise ValueError('Password cannot be longer than 72 characters')
        return v


@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user exists
    user = db.query(User).filter(User.email == user_data.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Generate verification token
    verification_token = _generate_token()
    
    # Create new user (password truncation handled in get_password_hash)
    # New users require email verification and admin approval before they can login
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        subscription_tier=SubscriptionTier.FREE,
        is_approved=False,  # Requires admin approval
        email_verified=False,  # Requires email verification
        verification_token=verification_token,
        verification_token_expires=datetime.utcnow() + timedelta(hours=24)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send verification email
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    
    try:
        text_body, html_body = _load_email_template(
            "email_verification",
            full_name=user.full_name,
            verification_url=verification_url
        )
        
        EmailService.send_email(
            to_email=user.email,
            subject="Verify Your Email - WeeVoice",
            body_text=text_body,
            body_html=html_body
        )
    except Exception as e:
        # Log error but don't fail registration
        print(f"Failed to send verification email: {e}")
    
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Check if email is verified
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before logging in. Check your inbox for the verification link."
        )
    
    # Check if user is approved by admin
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval by an administrator. Please wait for approval before logging in."
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    return current_user


@router.post("/api-keys", response_model=APIKeyResponse)
def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new API key"""
    api_key = APIKey(
        user_id=current_user.id,
        key=generate_api_key(),
        name=key_data.name
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key


@router.get("/api-keys", response_model=list[APIKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all API keys for current user"""
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    return keys


@router.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an API key"""
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    db.delete(api_key)
    db.commit()
    
    return {"message": "API key deleted"}


def _generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def _load_email_template(template_name: str, **kwargs) -> tuple[str, str]:
    """Load HTML and text email templates"""
    template_dir = Path(__file__).parent.parent / "templates"
    
    # Load HTML template
    html_path = template_dir / f"{template_name}.html"
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Load text template
    txt_path = template_dir / f"{template_name}.txt"
    with open(txt_path, 'r', encoding='utf-8') as f:
        txt_content = f.read()
    
    # Replace placeholders
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        html_content = html_content.replace(placeholder, str(value))
        txt_content = txt_content.replace(placeholder, str(value))
    
    return txt_content, html_content


@router.post("/request-verification")
def request_verification_email(
    request_data: EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    """Request a new verification email"""
    user = db.query(User).filter(User.email == request_data.email).first()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If the email exists, a verification link has been sent"}
    
    if user.email_verified:
        raise HTTPException(
            status_code=400,
            detail="Email already verified"
        )
    
    # Generate new verification token
    token = _generate_token()
    user.verification_token = token
    user.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
    
    db.commit()
    
    # Send verification email
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    text_body, html_body = _load_email_template(
        "email_verification",
        full_name=user.full_name,
        verification_url=verification_url
    )
    
    EmailService.send_email(
        to_email=user.email,
        subject="Verify Your Email - WeeVoice",
        body_text=text_body,
        body_html=html_body
    )
    
    return {"message": "Verification email sent"}


@router.get("/verify-email")
def verify_email(
    token: str = Query(..., description="Verification token"),
    db: Session = Depends(get_db)
):
    """Verify email address with token"""
    user = db.query(User).filter(User.verification_token == token).first()
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    if user.email_verified:
        raise HTTPException(
            status_code=400,
            detail="Email already verified"
        )
    
    # Check token expiration
    if user.verification_token_expires and user.verification_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Verification token has expired"
        )
    
    # Verify email
    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    
    db.commit()
    
    return {"message": "Email verified successfully"}


@router.post("/forgot-password")
def forgot_password(
    request_data: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Request password reset email"""
    user = db.query(User).filter(User.email == request_data.email).first()
    
    # Don't reveal if email exists
    if not user:
        return {"message": "If the email exists, a password reset link has been sent"}
    
    # Generate reset token
    token = _generate_token()
    user.reset_password_token = token
    user.reset_password_token_expires = datetime.utcnow() + timedelta(hours=1)
    
    db.commit()
    
    # Send password reset email
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    text_body, html_body = _load_email_template(
        "password_reset",
        full_name=user.full_name,
        reset_url=reset_url
    )
    
    EmailService.send_email(
        to_email=user.email,
        subject="Reset Your Password - WeeVoice",
        body_text=text_body,
        body_html=html_body
    )
    
    return {"message": "Password reset email sent"}


@router.post("/reset-password")
def reset_password(
    request_data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password with token"""
    user = db.query(User).filter(User.reset_password_token == request_data.token).first()
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )
    
    # Check token expiration
    if user.reset_password_token_expires and user.reset_password_token_expires < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Reset token has expired"
        )
    
    # Reset password
    user.hashed_password = get_password_hash(request_data.new_password)
    user.reset_password_token = None
    user.reset_password_token_expires = None
    
    db.commit()
    
    return {"message": "Password reset successfully"}

