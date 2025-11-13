from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Tuple
from jose import jwt, JWTError
import bcrypt
import logging
import time
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets

from app.core.config import settings
from app.models import get_db, User, APIKey

security = HTTPBearer()
logger = logging.getLogger(__name__)

# Simple in-memory cache for user objects to optimize frequent requests
# Format: {user_id: (user_object, timestamp)}
_user_cache: Dict[int, Tuple[User, float]] = {}
_CACHE_TTL = 30  # Cache user for 30 seconds


def _get_cached_user(user_id: int) -> Optional[User]:
    """Get user from cache if available and not expired"""
    if user_id not in _user_cache:
        return None
    
    user, timestamp = _user_cache[user_id]
    if time.time() - timestamp > _CACHE_TTL:
        # Cache expired
        del _user_cache[user_id]
        return None
    
    return user


def _cache_user(user: User):
    """Cache user object"""
    _user_cache[user.id] = (user, time.time())


def _invalidate_user_cache(user_id: int):
    """Invalidate cache for a specific user (e.g., when user is deactivated)"""
    if user_id in _user_cache:
        del _user_cache[user_id]


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
    """
    Get current user from JWT token.
    Uses caching to optimize frequent requests while maintaining security.
    Token signature is always validated, but user lookup is cached.
    """
    try:
        token = credentials.credentials
        logger.debug(f"Received token: {token[:20]}...")  # Log first 20 chars for debugging
        
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Always validate token signature (security requirement)
        payload = decode_token(token)
        logger.debug(f"Decoded payload: {payload}")
        
        if payload is None:
            logger.debug("Payload is None - invalid token")
            raise credentials_exception
        
        user_id: str = payload.get("sub")
        logger.debug(f"User ID from token: {user_id}")
        
        if user_id is None:
            logger.debug("User ID is None in payload")
            raise credentials_exception
        
        user_id_int = int(user_id)
        
        # Try to get user from cache first (optimization for frequent requests)
        user = _get_cached_user(user_id_int)
        
        if user is None:
            # Cache miss - query database
            user = db.query(User).filter(User.id == user_id_int).first()
            logger.debug(f"User found in DB: {user is not None}")
            
            if user is None:
                logger.warning(f"User not found in database for ID: {user_id}")
                raise credentials_exception
            
            # Cache the user for future requests
            _cache_user(user)
        else:
            logger.debug(f"User found in cache: {user.email}")
        
        # Always check if user is active (even from cache)
        if not user.is_active:
            # Invalidate cache if user is inactive
            _invalidate_user_cache(user_id_int)
            logger.warning(f"Inactive user attempted authentication: {user.email}")
            raise HTTPException(status_code=400, detail="Inactive user")
        
        logger.debug(f"Authentication successful for user {user.email}")
        return user
    except HTTPException:
        # Re-raise HTTP exceptions (authentication failures)
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error in get_current_user: {type(e).__name__}: {e}", exc_info=True)
        raise credentials_exception


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current admin user - requires superuser status"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
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

