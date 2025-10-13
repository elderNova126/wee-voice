from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from datetime import datetime

from app.core.security import get_current_active_user
from app.models import get_db, User, VoiceAgent, Document
from app.services.document_service import DocumentProcessingService
from app.services.web_scraper_service import WebScraperService
from app.services.rag_service import get_rag_service

router = APIRouter()
document_service = DocumentProcessingService()
web_scraper_service = WebScraperService()


class DocumentResponse(BaseModel):
    id: int
    agent_id: int
    filename: str
    original_filename: str
    file_size: Optional[int]
    status: str
    error_message: Optional[str]
    total_pages: Optional[int]
    total_chunks: int
    source_type: str
    source_url: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WebsiteUploadRequest(BaseModel):
    url: HttpUrl


@router.post("/{agent_id}/documents", response_model=DocumentResponse)
async def upload_document(
    agent_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a PDF document to an agent for RAG"""
    
    # Verify agent ownership
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Check file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Check file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    try:
        # Process document
        document = await document_service.upload_and_process_document(
            file_content=content,
            filename=file.filename,
            agent_id=agent_id,
            user_id=current_user.id
        )
        
        # Generate embeddings
        rag_service = get_rag_service()
        await rag_service.embed_document_chunks(document.id)
        
        # Enable RAG on agent if not already enabled
        if not agent.rag_enabled:
            agent.rag_enabled = True
            db.commit()
        
        # Refresh to get updated data
        db.refresh(document)
        
        return document
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.get("/{agent_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    agent_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all documents for an agent"""
    
    # Verify agent ownership
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


@router.get("/{agent_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    agent_id: int,
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get details of a specific document"""
    
    # Verify agent ownership
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.agent_id == agent_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.delete("/{agent_id}/documents/{document_id}")
async def delete_document(
    agent_id: int,
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a document and its embeddings"""
    
    # Verify agent ownership
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.agent_id == agent_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Delete embeddings first
        rag_service = get_rag_service()
        await rag_service.delete_document_embeddings(document_id)
        
        # Delete document
        await document_service.delete_document(document_id)
        
        return {"message": "Document deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.post("/{agent_id}/documents/website", response_model=DocumentResponse)
async def scrape_website(
    agent_id: int,
    request: WebsiteUploadRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Scrape a website and add it to the agent's knowledge base"""
    
    # Verify agent ownership
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        # Scrape and process website
        document = await web_scraper_service.scrape_and_process_url(
            url=str(request.url),
            agent_id=agent_id,
            user_id=current_user.id
        )
        
        # Generate embeddings
        rag_service = get_rag_service()
        await rag_service.embed_document_chunks(document.id)
        
        # Enable RAG on agent if not already enabled
        if not agent.rag_enabled:
            agent.rag_enabled = True
            db.commit()
        
        # Refresh to get updated data
        db.refresh(document)
        
        return document
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping website: {str(e)}")


@router.put("/{agent_id}/rag/toggle")
async def toggle_rag(
    agent_id: int,
    enabled: bool = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Enable or disable RAG for an agent"""
    
    # Verify agent ownership
    agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == agent_id,
        VoiceAgent.user_id == current_user.id
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.rag_enabled = enabled
    db.commit()
    
    return {
        "message": f"RAG {'enabled' if enabled else 'disabled'} for agent",
        "rag_enabled": enabled
    }

