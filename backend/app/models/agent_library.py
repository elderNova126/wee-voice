from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class LibraryCategory(str, enum.Enum):
    """Categories for agent libraries"""
    REAL_ESTATE = "real_estate"
    CUSTOMER_SERVICE = "customer_service"
    SALES = "sales"
    SUPPORT = "support"
    MARKETING = "marketing"
    HR = "hr"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    FINANCE = "finance"
    LEGAL = "legal"
    GENERAL = "general"


class AgentLibrary(Base):
    """Library of agent templates/prompts that users can use to create agents"""
    __tablename__ = "agent_libraries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # None for public libraries
    is_public = Column(Boolean, default=False, index=True)  # Public libraries are managed by admins
    
    # Library metadata
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(LibraryCategory, values_callable=lambda x: [e.value for e in x]), default=LibraryCategory.GENERAL)
    tags = Column(JSON, default=list)  # List of tags for filtering/searching
    icon = Column(String, nullable=True)  # Icon name or emoji
    language = Column(String, default="fr-FR")  # Primary language
    
    # Agent configuration template
    system_prompt = Column(Text, nullable=False)
    greeting = Column(Text, nullable=True)
    voice_id = Column(String, default="Charon")
    voice_gender = Column(String, default="male")
    
    # Advanced configuration
    agent_config = Column(JSON, nullable=True)  # LangGraph workflow config
    tools_enabled = Column(JSON, default=list)  # List of enabled tools
    model_name = Column(String, default="gemini-2.5-flash-native-audio-preview-09-2025")
    temperature = Column(String, default="0.7")
    max_tokens = Column(Integer, default=1000)
    
    # RAG Configuration
    rag_enabled = Column(Boolean, default=False)
    rag_config = Column(JSON, nullable=True)
    
    # CRM Integration template
    crm_enabled = Column(Boolean, default=False)
    crm_config = Column(JSON, nullable=True)
    
    # Usage statistics
    usage_count = Column(Integer, default=0)  # How many times this library was used to create agents
    saved_count = Column(Integer, default=0)  # How many users saved this to their libraries
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Original creator
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="saved_libraries")
    creator = relationship("User", foreign_keys=[created_by_user_id], backref="created_libraries")

