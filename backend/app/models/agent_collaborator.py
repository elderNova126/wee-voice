from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class CollaboratorPermission(str, enum.Enum):
    """Permissions for agent collaborators"""
    VIEW = "view"  # Can view agent
    EDIT = "edit"  # Can edit agent
    DELETE = "delete"  # Can delete agent
    MANAGE_COLLABORATORS = "manage_collaborators"  # Can manage other collaborators


class AgentCollaborator(Base):
    """Collaborators who can access and manage agents"""
    __tablename__ = "agent_collaborators"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("voice_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Permissions (stored as JSON array of permission strings)
    permissions = Column(String, nullable=False)  # Comma-separated: "view,edit,delete" or "view,edit"
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who invited this collaborator
    
    # Relationships
    agent = relationship("VoiceAgent", back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id], back_populates="agent_collaborations")
    inviter = relationship("User", foreign_keys=[invited_by])
    
    def has_permission(self, permission: str) -> bool:
        """Check if collaborator has a specific permission"""
        if not self.is_active:
            return False
        return permission in self.permissions.split(",")
    
    def has_any_permission(self, permissions: list) -> bool:
        """Check if collaborator has any of the specified permissions"""
        if not self.is_active:
            return False
        collaborator_perms = set(self.permissions.split(","))
        return bool(collaborator_perms.intersection(set(permissions)))

