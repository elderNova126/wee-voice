"""
API endpoints for avatar photo management
"""
import logging
import base64
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models import get_db, User
from app.core.security import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class AvatarPhotoRequest(BaseModel):
    photo_url: str
    photo_type: str  # 'upload' or 'sample'


class AvatarPhotoResponse(BaseModel):
    id: int
    user_id: int
    photo_url: str
    photo_type: str
    is_active: bool
    created_at: datetime


@router.post("/upload")
async def upload_avatar_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a custom avatar photo
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Validate file size (max 5MB)
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 5MB")
        
        # Convert to base64 for storage
        base64_image = base64.b64encode(contents).decode('utf-8')
        photo_url = f"data:{file.content_type};base64,{base64_image}"
        
        # Store in user profile (we'll add this to the User model)
        current_user.avatar_photo_url = photo_url
        current_user.avatar_photo_type = 'upload'
        current_user.avatar_enabled = True
        db.commit()
        
        return {
            "message": "Avatar photo uploaded successfully",
            "photo_url": photo_url,
            "photo_type": "upload"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload avatar photo")


@router.post("/select")
async def select_avatar_photo(
    request: AvatarPhotoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Select an avatar photo (sample or uploaded)
    """
    try:
        current_user.avatar_photo_url = request.photo_url
        current_user.avatar_photo_type = request.photo_type
        current_user.avatar_enabled = True
        db.commit()
        
        return {
            "message": "Avatar photo selected successfully",
            "photo_url": request.photo_url,
            "photo_type": request.photo_type
        }
    
    except Exception as e:
        logger.error(f"Error selecting avatar photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to select avatar photo")


@router.get("/current")
async def get_current_avatar(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's avatar photo
    """
    return {
        "photo_url": getattr(current_user, 'avatar_photo_url', None),
        "photo_type": getattr(current_user, 'avatar_photo_type', None),
        "enabled": getattr(current_user, 'avatar_enabled', False)
    }


@router.delete("/remove")
async def remove_avatar_photo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove the current avatar photo
    """
    try:
        current_user.avatar_photo_url = None
        current_user.avatar_photo_type = None
        current_user.avatar_enabled = False
        db.commit()
        
        return {"message": "Avatar photo removed successfully"}
    
    except Exception as e:
        logger.error(f"Error removing avatar photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove avatar photo")


@router.put("/toggle")
async def toggle_avatar(
    enabled: bool = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable or disable avatar for calls
    """
    try:
        current_user.avatar_enabled = enabled
        db.commit()
        
        return {
            "message": f"Avatar {'enabled' if enabled else 'disabled'} successfully",
            "enabled": enabled
        }
    
    except Exception as e:
        logger.error(f"Error toggling avatar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to toggle avatar")

