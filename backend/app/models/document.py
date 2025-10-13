from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base


class Document(Base):
    """Model for storing uploaded documents (PDFs) for RAG"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("voice_agents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Document metadata
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)  # Path to stored file (nullable for web sources)
    file_size = Column(Integer, nullable=True)  # Size in bytes (nullable for web sources)
    mime_type = Column(String, default="application/pdf")
    
    # Source information
    source_type = Column(String, default="pdf")  # pdf, website, text
    source_url = Column(String, nullable=True)  # Original URL if from web
    
    # Processing status
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Document content
    total_pages = Column(Integer, nullable=True)
    total_chunks = Column(Integer, default=0)
    
    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    doc_metadata = Column(JSON, nullable=True)  # Additional metadata (author, title, etc.)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Relationships
    agent = relationship("VoiceAgent", back_populates="documents")
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Model for storing document chunks with embeddings"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    # Chunk content
    chunk_index = Column(Integer, nullable=False)  # Order within document
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    
    # Embedding (stored as JSON array for flexibility)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String, default="all-MiniLM-L6-v2")
    
    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    chunk_metadata = Column(JSON, nullable=True)
    token_count = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")

