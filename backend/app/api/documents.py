from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import logging

from app.models.database import get_db
from app.models.document import Document, DocumentChunk
from app.models.agent import VoiceAgent
from app.models.user import User
from app.core.security import get_current_active_user
from app.services.document_service import DocumentService
from app.services.web_scraper_service import WebScraperService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
document_service = DocumentService()
web_scraper_service = WebScraperService()
rag_service = RAGService()


class DocumentResponse(BaseModel):
    id: int
    agent_id: int
    original_filename: str
    source_type: str
    source_url: str | None = None
    status: str
    error_message: str | None = None
    file_size: int | None = None
    total_pages: int | None = None
    total_chunks: int
    doc_metadata: dict | None = None
    created_at: str
    processed_at: str | None = None

    class Config:
        from_attributes = True


class WebsiteUploadRequest(BaseModel):
    url: str


@router.post("/agents/{agent_id}/documents", response_model=DocumentResponse)
async def upload_document(
    agent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a PDF document to an agent's knowledge base"""
    
    # Verify agent exists and belongs to user
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Read file content
    content = await file.read()
    
    # Validate file size (10MB max)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    try:
        # Process document
        document = await document_service.upload_and_process_document(
            db=db,
            agent_id=agent_id,
            user_id=current_user.id,
            file_content=content,
            filename=file.filename
        )
        
        # Generate embeddings for chunks
        await rag_service.process_chunks_embeddings(db, document.id)
        
        # Enable RAG for agent if not already enabled
        if not agent.rag_enabled:
            agent.rag_enabled = True
            db.commit()
        
        return document
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/documents/website", response_model=DocumentResponse)
async def scrape_website(
    agent_id: int,
    request: WebsiteUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Scrape a website and add it to the agent's knowledge base"""
    
    # Verify agent exists and belongs to user
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        # Process website
        document = await web_scraper_service.scrape_and_process_url(
            db=db,
            url=request.url,
            agent_id=agent_id,
            user_id=current_user.id
        )
        
        # Generate embeddings for chunks
        await rag_service.process_chunks_embeddings(db, document.id)
        
        # Enable RAG for agent if not already enabled
        if not agent.rag_enabled:
            agent.rag_enabled = True
            db.commit()
        
        return document
        
    except Exception as e:
        logger.error(f"Error scraping website: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all documents for an agent"""
    
    # Verify agent exists and belongs to user
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    documents = db.query(Document).filter(
        Document.agent_id == agent_id
    ).order_by(Document.created_at.desc()).all()
    
    return documents


@router.delete("/agents/{agent_id}/documents/{document_id}")
async def delete_document(
    agent_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a document from an agent's knowledge base"""
    
    # Verify agent exists and belongs to user
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Find document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.agent_id == agent_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file if it exists
    if document.file_path:
        import os
        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file {document.file_path}: {e}")
    
    # Delete from database (cascades to chunks)
    db.delete(document)
    db.commit()
    
    return {"message": "Document deleted successfully"}


@router.put("/agents/{agent_id}/rag/toggle")
async def toggle_rag(
    agent_id: int,
    enabled: bool = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Enable or disable RAG for an agent"""
    
    # Verify agent exists and belongs to user
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.rag_enabled = enabled
    db.commit()
    
    return {"message": f"RAG {'enabled' if enabled else 'disabled'} successfully"}
