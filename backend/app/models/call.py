from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.models.database import Base


class CallStatus(str, enum.Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=False)
    
    # Call metadata
    session_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(Enum(CallStatus, values_callable=lambda x: [e.value for e in x]), default=CallStatus.INITIATED)
    
    # Duration and cost
    duration_seconds = Column(Float, default=0.0)
    duration_minutes = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    
    # Audio files
    recording_url = Column(String, nullable=True)
    
    # Transcription
    transcript = Column(Text, nullable=True)
    transcript_json = Column(JSON, nullable=True)  # Detailed transcript with timestamps
    
    # Summary and analysis
    summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)
    key_points = Column(JSON, nullable=True)
    
    # Caller information
    caller_phone = Column(String, nullable=True)
    caller_name = Column(String, nullable=True)
    caller_metadata = Column(JSON, nullable=True)
    
    # CRM data
    crm_synced = Column(Boolean, default=False)
    crm_record_id = Column(String, nullable=True)
    crm_response = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="calls")
    agent = relationship("VoiceAgent", back_populates="calls")
    messages = relationship("CallMessage", back_populates="call", cascade="all, delete-orphan")


class CallMessage(Base):
    __tablename__ = "call_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Message data
    role = Column(String, nullable=False)  # "user" or "agent"
    content = Column(Text, nullable=False)
    audio_url = Column(String, nullable=True)
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Float, nullable=True)
    
    # Relationships
    call = relationship("Call", back_populates="messages")

