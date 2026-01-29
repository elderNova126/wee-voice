"""
Agent Collaborator Management API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.security import get_current_active_user
from app.core.permissions import check_agent_access, can_manage_collaborators
from app.models import get_db, User, VoiceAgent, AgentCollaborator

router = APIRouter()


class CollaboratorCreate(BaseModel):
    email: EmailStr
    permissions: str  # Comma-separated: "view,edit" or "view,edit,delete"


class CollaboratorUpdate(BaseModel):
    permissions: Optional[str] = None
    is_active: Optional[bool] = None


class CollaboratorResponse(BaseModel):
    id: int
    agent_id: int
    user_id: int
    user_email: str
    user_name: str
    permissions: str
    is_active: bool
    created_at: str
    invited_by: Optional[int] = None
    
    class Config:
        from_attributes = True


@router.get("/agents/{agent_id}/collaborators", response_model=List[CollaboratorResponse])
def list_collaborators(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all collaborators for an agent"""
    from sqlalchemy.orm import joinedload
    
    # Check if user has access to the agent
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id)
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Only owner or user with manage_collaborators permission can list
    if role != "owner" and not can_manage_collaborators(db, agent_id, current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Use joinedload to fetch users in single query (avoid N+1)
    collaborators = db.query(AgentCollaborator).options(
        joinedload(AgentCollaborator.user)
    ).filter(
        AgentCollaborator.agent_id == agent_id
    ).all()
    
    result = []
    for collab in collaborators:
        user = collab.user  # Already loaded via joinedload
        result.append({
            "id": collab.id,
            "agent_id": collab.agent_id,
            "user_id": collab.user_id,
            "user_email": user.email if user else "",
            "user_name": user.full_name if user else "",
            "permissions": collab.permissions,
            "is_active": collab.is_active,
            "created_at": collab.created_at.isoformat() if collab.created_at else "",
            "invited_by": collab.invited_by
        })
    
    return result


@router.post("/agents/{agent_id}/collaborators", response_model=CollaboratorResponse)
def add_collaborator(
    agent_id: int,
    collaborator_data: CollaboratorCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Add a collaborator to an agent"""
    # Check if user can manage collaborators
    if not can_manage_collaborators(db, agent_id, current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage collaborators")
    
    # Get agent
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Find user by email
    user = db.query(User).filter(User.email == collaborator_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is trying to add themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a collaborator")
    
    # Check if user is the owner
    if user.id == agent.user_id:
        raise HTTPException(status_code=400, detail="Owner is already a collaborator")
    
    # Check if collaborator already exists
    existing = db.query(AgentCollaborator).filter(
        AgentCollaborator.agent_id == agent_id,
        AgentCollaborator.user_id == user.id
    ).first()
    
    if existing:
        # Update existing collaborator
        existing.permissions = collaborator_data.permissions
        existing.is_active = True
        existing.invited_by = current_user.id
        db.commit()
        db.refresh(existing)
        
        return {
            "id": existing.id,
            "agent_id": existing.agent_id,
            "user_id": existing.user_id,
            "user_email": user.email,
            "user_name": user.full_name,
            "permissions": existing.permissions,
            "is_active": existing.is_active,
            "created_at": existing.created_at.isoformat() if existing.created_at else "",
            "invited_by": existing.invited_by
        }
    
    # Create new collaborator
    collaborator = AgentCollaborator(
        agent_id=agent_id,
        user_id=user.id,
        permissions=collaborator_data.permissions,
        is_active=True,
        invited_by=current_user.id
    )
    
    db.add(collaborator)
    db.commit()
    db.refresh(collaborator)
    
    return {
        "id": collaborator.id,
        "agent_id": collaborator.agent_id,
        "user_id": collaborator.user_id,
        "user_email": user.email,
        "user_name": user.full_name,
        "permissions": collaborator.permissions,
        "is_active": collaborator.is_active,
        "created_at": collaborator.created_at.isoformat() if collaborator.created_at else "",
        "invited_by": collaborator.invited_by
    }


@router.put("/agents/{agent_id}/collaborators/{collaborator_id}", response_model=CollaboratorResponse)
def update_collaborator(
    agent_id: int,
    collaborator_id: int,
    collaborator_data: CollaboratorUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a collaborator's permissions"""
    from sqlalchemy.orm import joinedload
    
    # Check if user can manage collaborators
    if not can_manage_collaborators(db, agent_id, current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage collaborators")
    
    # Fetch collaborator with user in single query
    collaborator = db.query(AgentCollaborator).options(
        joinedload(AgentCollaborator.user)
    ).filter(
        AgentCollaborator.id == collaborator_id,
        AgentCollaborator.agent_id == agent_id
    ).first()
    
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    # Update permissions if provided
    if collaborator_data.permissions is not None:
        collaborator.permissions = collaborator_data.permissions
    
    # Update active status if provided
    if collaborator_data.is_active is not None:
        collaborator.is_active = collaborator_data.is_active
    
    db.commit()
    db.refresh(collaborator)
    
    user = collaborator.user  # Already loaded via joinedload
    
    return {
        "id": collaborator.id,
        "agent_id": collaborator.agent_id,
        "user_id": collaborator.user_id,
        "user_email": user.email if user else "",
        "user_name": user.full_name if user else "",
        "permissions": collaborator.permissions,
        "is_active": collaborator.is_active,
        "created_at": collaborator.created_at.isoformat() if collaborator.created_at else "",
        "invited_by": collaborator.invited_by
    }


@router.delete("/agents/{agent_id}/collaborators/{collaborator_id}")
def remove_collaborator(
    agent_id: int,
    collaborator_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a collaborator from an agent"""
    # Check if user can manage collaborators
    if not can_manage_collaborators(db, agent_id, current_user.id):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage collaborators")
    
    collaborator = db.query(AgentCollaborator).filter(
        AgentCollaborator.id == collaborator_id,
        AgentCollaborator.agent_id == agent_id
    ).first()
    
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    db.delete(collaborator)
    db.commit()
    
    return {"message": "Collaborator removed successfully"}


@router.get("/agents/{agent_id}/my-permissions")
def get_my_permissions(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's permissions for an agent"""
    has_access, agent, role = check_agent_access(db, agent_id, current_user.id)
    
    if not has_access or not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    from app.core.permissions import get_user_permissions
    permissions = get_user_permissions(db, agent_id, current_user.id)
    
    return {
        "agent_id": agent_id,
        "role": role,
        "permissions": permissions,
        "is_owner": role == "owner"
    }

