from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base


class AgentIntegration(Base):
    """Junction table for many-to-many relationship between agents and integrations"""
    __tablename__ = "agent_integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("voice_agents.id", ondelete="CASCADE"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agent = relationship("VoiceAgent", back_populates="integrations")
    integration = relationship("Integration", back_populates="agents")
    
    # Ensure unique agent-integration pairs
    __table_args__ = (
        UniqueConstraint('agent_id', 'integration_id', name='uq_agent_integration'),
    )
    
    def __repr__(self):
        return f"<AgentIntegration(agent_id={self.agent_id}, integration_id={self.integration_id})>"

