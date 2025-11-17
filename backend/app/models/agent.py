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
    voice_id = Column(String, default="Charon")  # Gemini 2.5 voice (Puck, Charon, Kore, Fenrir, Aoede)
    voice_gender = Column(String, default="male")  # Voice gender: male, female, neutral
    system_prompt = Column(Text, nullable=False)
    greeting = Column(Text, nullable=True)  # Custom greeting message for the agent
    email_request_enabled = Column(Boolean, default=False)  # Request email after greeting
    email_request_message = Column(Text, nullable=True)  # Custom email request message
    
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
    
    # Website embed settings
    embed_enabled = Column(Boolean, default=False)
    embed_widget_color = Column(String, default="#4F46E5")  # Primary color for widget
    embed_position = Column(String, default="bottom-right")  # "bottom-right", "bottom-left"
    embed_greeting_message = Column(Text, nullable=True)
    embed_language = Column(String, default="en")  # UI language: en, fr, es, etc.
    allowed_domains = Column(JSON, default=list)  # List of domains where embed is allowed
    
    # Relationships
    user = relationship("User", back_populates="agents")
    calls = relationship("Call", back_populates="agent", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="agent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="agent", cascade="all, delete-orphan")
    phone_number = relationship("PhoneNumber", back_populates="agent", uselist=False)
    callback_requests = relationship("CallbackRequest", back_populates="agent", cascade="all, delete-orphan")

