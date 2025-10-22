from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base


class VoiceAgent(Base):
    __tablename__ = "voice_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Agent configuration
    language = Column(String, default="fr-FR")  # French by default
    voice_id = Column(String, default="fr-FR-Neural2-A")
    system_prompt = Column(Text, nullable=False)
    
    # LangGraph configuration
    agent_config = Column(JSON, nullable=True)  # Store LangGraph workflow config
    tools_enabled = Column(JSON, default=list)  # List of enabled tools
    
    # Model settings
    model_name = Column(String, default="gemini-2.5-flash-native-audio-preview-09-2025")
    temperature = Column(String, default="0.7")
    max_tokens = Column(Integer, default=1000)
    
    # CRM Integration
    crm_webhook_url = Column(String, nullable=True)
    crm_enabled = Column(Boolean, default=False)
    crm_config = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # For demo agents
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # RAG Configuration
    rag_enabled = Column(Boolean, default=False)
    rag_config = Column(JSON, nullable=True)  # RAG-specific settings (chunk size, retrieval count, etc.)
    
    # Relationships
    user = relationship("User", back_populates="agents")
    calls = relationship("Call", back_populates="agent", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="agent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="agent", cascade="all, delete-orphan")

