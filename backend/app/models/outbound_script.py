from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base


class OutboundScript(Base):
    """Outbound call scripts/templates for AI agents"""
    __tablename__ = "outbound_scripts"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Script details
    name = Column(String, nullable=False)  # Script name/title
    description = Column(Text, nullable=True)  # Brief description
    
    # Script content
    opening_message = Column(Text, nullable=False)  # What the agent says first
    main_content = Column(Text, nullable=True)  # Main talking points/script
    closing_message = Column(Text, nullable=True)  # How to wrap up the call
    
    # Behavioral instructions for the AI
    tone = Column(String, default="professional")  # professional, friendly, casual, formal
    objective = Column(Text, nullable=True)  # Goal of the call (e.g., "Schedule a demo", "Qualify lead")
    key_points = Column(Text, nullable=True)  # Key points to cover (newline-separated)
    objection_handling = Column(Text, nullable=True)  # How to handle common objections
    
    # Status
    is_active = Column(Boolean, default=True)
    is_favorite = Column(Boolean, default=False)  # Mark as favorite for quick access
    
    # Usage stats
    use_count = Column(Integer, default=0)  # How many times this script has been used
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agent = relationship("VoiceAgent", back_populates="outbound_scripts")
    user = relationship("User", back_populates="outbound_scripts")

