from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Document(Base):
    """RAG Document model for storing uploaded knowledge sources"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # File information
    filename = Column(String, nullable=False)  # Stored filename
    original_filename = Column(String, nullable=False)  # User's original filename
    file_path = Column(String, nullable=True)  # Path to stored file (local path or Supabase path)
    file_url = Column(String, nullable=True)  # Public URL for Supabase storage
    file_size = Column(Integer, nullable=True)  # File size in bytes
    mime_type = Column(String, default="application/pdf")
    
    # Source information
    source_type = Column(String, default="pdf")  # pdf, website, text
    source_url = Column(String, nullable=True)  # For websites
    
    # Processing status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Content metadata
    total_pages = Column(Integer, nullable=True)  # For PDFs
    total_chunks = Column(Integer, default=0)
    doc_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy conflict
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    agent = relationship("VoiceAgent", back_populates="documents")
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Text chunks from documents with embeddings for RAG retrieval"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    # Chunk data
    chunk_index = Column(Integer, nullable=False)  # Order within document
    content = Column(Text, nullable=False)  # The actual text content
    page_number = Column(Integer, nullable=True)  # Source page (for PDFs)
    
    # Embedding data
    embedding = Column(JSON, nullable=True)  # Vector embedding as JSON array
    embedding_model = Column(String, default="all-MiniLM-L6-v2")
    
    # Metadata
    chunk_metadata = Column(JSON, nullable=True)  # Renamed from metadata to avoid SQLAlchemy conflict
    token_count = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
