"""
Permission checking utilities for agent collaborators
"""
from sqlalchemy.orm import Session
from typing import Optional
from app.models import VoiceAgent, AgentCollaborator, User


def check_agent_access(
    db: Session,
    agent_id: int,
    user_id: int,
    required_permission: Optional[str] = None
) -> tuple[bool, Optional[VoiceAgent], Optional[str]]:
    """
    Check if user has access to an agent and optionally a specific permission.
    
    Returns:
        (has_access, agent, user_role)
        - has_access: True if user can access the agent
        - agent: The agent object if found
        - user_role: "owner", "collaborator", or None
    """
    # Get agent
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
    if not agent:
        return False, None, None
    
    # Check if user is owner
    if agent.user_id == user_id:
        return True, agent, "owner"
    
    # Check if user is a collaborator
    collaborator = db.query(AgentCollaborator).filter(
        AgentCollaborator.agent_id == agent_id,
        AgentCollaborator.user_id == user_id,
        AgentCollaborator.is_active == True
    ).first()
    
    if collaborator:
        # If specific permission required, check it
        if required_permission:
            has_perm = collaborator.has_permission(required_permission)
            return has_perm, agent, "collaborator" if has_perm else None
        
        return True, agent, "collaborator"
    
    return False, agent, None


def get_user_permissions(
    db: Session,
    agent_id: int,
    user_id: int
) -> list[str]:
    """Get list of permissions for a user on an agent"""
    agent = db.query(VoiceAgent).filter(VoiceAgent.id == agent_id).first()
    if not agent:
        return []
    
    # Owner has all permissions
    if agent.user_id == user_id:
        return ["view", "edit", "delete", "manage_collaborators"]
    
    # Get collaborator permissions
    collaborator = db.query(AgentCollaborator).filter(
        AgentCollaborator.agent_id == agent_id,
        AgentCollaborator.user_id == user_id,
        AgentCollaborator.is_active == True
    ).first()
    
    if collaborator:
        return collaborator.permissions.split(",")
    
    return []


def can_manage_collaborators(
    db: Session,
    agent_id: int,
    user_id: int
) -> bool:
    """Check if user can manage collaborators for an agent"""
    has_access, agent, role = check_agent_access(db, agent_id, user_id, "manage_collaborators")
    
    # Owner can always manage collaborators
    if role == "owner":
        return True
    
    return has_access and role == "collaborator"

