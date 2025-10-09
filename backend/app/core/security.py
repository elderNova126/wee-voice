from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets

from app.core.config import settings
from app.models import get_db, User, APIKey

security = HTTPBearer()


def truncate_password(password: str) -> bytes:
    """Truncate password to 72 bytes for bcrypt compatibility"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes safely
        return password_bytes[:72]
    return password_bytes


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    password_bytes = truncate_password(plain_password)
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    password_bytes = truncate_password(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"vak_{secrets.token_urlsafe(32)}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from JWT token"""
    try:
        token = credentials.credentials
        print(f"DEBUG: Received token: {token[:20]}...")  # Log first 20 chars
        
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        payload = decode_token(token)
        print(f"DEBUG: Decoded payload: {payload}")
        
        if payload is None:
            print("DEBUG: Payload is None")
            raise credentials_exception
        
        user_id: str = payload.get("sub")
        print(f"DEBUG: User ID from token: {user_id}")
        
        if user_id is None:
            print("DEBUG: User ID is None")
            raise credentials_exception
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        print(f"DEBUG: User found: {user is not None}")
        
        if user is None:
            print("DEBUG: User not found in database")
            raise credentials_exception
        
        if not user.is_active:
            print("DEBUG: User is not active")
            raise HTTPException(status_code=400, detail="Inactive user")
        
        print(f"DEBUG: Authentication successful for user {user.email}")
        return user
    except Exception as e:
        print(f"DEBUG: Exception in get_current_user: {type(e).__name__}: {e}")
        raise


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def verify_api_key(
    api_key: str,
    db: Session
) -> Optional[User]:
    """Verify API key and return associated user"""
    key_obj = db.query(APIKey).filter(
        APIKey.key == api_key,
        APIKey.is_active == True
    ).first()
    
    if not key_obj:
        return None
    
    # Check expiration
    if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
        return None
    
    # Update usage stats
    key_obj.total_requests += 1
    key_obj.last_used_at = datetime.utcnow()
    db.commit()
    
    return key_obj.user

