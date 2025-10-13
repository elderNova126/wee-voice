import uuid
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import base64
from io import BytesIO

try:
    import fitz  # PyMuPDF
    from PIL import Image
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    raise ImportError("PyMuPDF is required. Install with: pip install pymupdf")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.models import Document, DocumentChunk
from app.models.database import SessionLocal
from app.core.config import settings

# Initialize logger
logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service for processing PDF documents for RAG"""
    
    def __init__(self, upload_dir: str = "uploads/documents"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Default chunking configuration
        self.chunk_size = 1000  # characters
        self.chunk_overlap = 200  # characters
        
        # OpenAI client for OCR
        self.openai_client = None
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized for OCR")
        else:
            logger.warning("OpenAI not configured. Scanned PDFs will not be processed.")
    
    async def upload_and_process_document(
        self, 
        file_content: bytes, 
        filename: str, 
        agent_id: int, 
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Upload and process a PDF document"""
        db = SessionLocal()
        
        try:
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_extension = Path(filename).suffix
            stored_filename = f"{file_id}{file_extension}"
            file_path = self.upload_dir / stored_filename
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            file_size = len(file_content)
            
            # Create document record
            document = Document(
                agent_id=agent_id,
                user_id=user_id,
                filename=stored_filename,
                original_filename=filename,
                file_path=str(file_path),
                file_size=file_size,
                status="processing",
                doc_metadata=metadata or {}
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"Document uploaded: {filename} (ID: {document.id})")
            
            # Process document in background (for now, process synchronously)
            await self._process_document(document.id, str(file_path))
            
            return document
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}", exc_info=True)
            if 'document' in locals():
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
            raise
        finally:
            db.close()
    
    async def _process_document(self, document_id: int, file_path: str):
        """Process document: extract text, chunk, and prepare for embedding"""
        db = SessionLocal()
        
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            logger.info(f"Processing document {document_id}: {document.original_filename}")
            
            # Extract text from PDF
            text_content, total_pages = self._extract_text_from_pdf(file_path)
            
            # Update document with page count
            document.total_pages = total_pages
            
            # Chunk the text
            chunks = self._chunk_text(text_content)
            
            # Create chunk records
            for idx, chunk_data in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_data['content'],
                    page_number=chunk_data.get('page_number'),
                    chunk_metadata=chunk_data.get('metadata', {}),
                    token_count=len(chunk_data['content'].split())  # Simple token estimate
                )
                db.add(chunk)
            
            # Update document status
            document.status = "completed"
            document.total_chunks = len(chunks)
            document.processed_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Document {document_id} processed successfully: {len(chunks)} chunks created")
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
            raise
        finally:
            db.close()
    
    def _is_scanned_pdf(self, doc: fitz.Document, text: str) -> bool:
        """Detect if PDF is scanned (image-based) by checking text density and images"""
        total_pages = len(doc)
        
        if not text or len(text.strip()) < 100:
            return True
        
        # Calculate text density (chars per page)
        chars_per_page = len(text) / max(total_pages, 1)
        
        # Check if pages contain mostly images
        image_heavy = False
        if total_pages > 0:
            # Sample first few pages
            sample_pages = min(3, total_pages)
            images_found = 0
            for page_num in range(sample_pages):
                page = doc[page_num]
                image_list = page.get_images()
                if len(image_list) > 0:
                    images_found += 1
            
            # If most sampled pages have images and low text, likely scanned
            if images_found >= sample_pages * 0.7:
                image_heavy = True
        
        # If less than 200 chars per page on average, likely scanned
        if chars_per_page < 200 or image_heavy:
            logger.info(f"PDF appears to be scanned ({chars_per_page:.0f} chars/page, image_heavy={image_heavy})")
            return True
        
        return False
    
    def _ocr_page_with_openai(self, page_image_bytes: bytes, page_num: int) -> str:
        """Use OpenAI Vision API to extract text from page image"""
        if not self.openai_client:
            logger.error("OpenAI client not available for OCR")
            return ""
        
        try:
            # Convert bytes to base64
            img_base64 = base64.b64encode(page_image_bytes).decode()
            
            # Call OpenAI Vision API
            response = self.openai_client.chat.completions.create(
                model=settings.OPENAI_OCR_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text from this document page. Return ONLY the text content, preserving formatting and structure. Do not add any commentary or explanations."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0
            )
            
            text = response.choices[0].message.content
            logger.info(f"OCR extracted {len(text)} characters from page {page_num}")
            return text
            
        except Exception as e:
            logger.error(f"OpenAI OCR failed for page {page_num}: {e}")
            return ""
    
    def _extract_text_from_scanned_pdf(self, doc: fitz.Document) -> tuple[str, int]:
        """Extract text from scanned PDF using OpenAI Vision OCR"""
        if not self.openai_client:
            raise ValueError("OpenAI API key required for scanned PDF OCR")
        
        try:
            total_pages = len(doc)
            logger.info(f"Processing scanned PDF with {total_pages} pages using OCR")
            
            # Process each page with OpenAI Vision
            text_parts = []
            for page_num in range(total_pages):
                logger.info(f"OCR processing page {page_num + 1}/{total_pages}...")
                page = doc[page_num]
                
                # Render page to image (PNG format)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                img_bytes = pix.tobytes("png")
                
                # OCR with OpenAI
                page_text = self._ocr_page_with_openai(img_bytes, page_num + 1)
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"OCR extracted {len(full_text)} characters from {total_pages} pages")
            
            return full_text, total_pages
            
        except Exception as e:
            logger.error(f"Error processing scanned PDF: {e}", exc_info=True)
            raise
    
    def _extract_text_from_pdf(self, file_path: str) -> tuple[str, int]:
        """Extract text from PDF file using PyMuPDF (handles both regular and scanned PDFs)"""
        try:
            logger.info("Opening PDF with PyMuPDF...")
            
            # Open PDF with PyMuPDF
            doc = fitz.open(file_path)
            total_pages = len(doc)
            
            # Extract text from all pages
            text_parts = []
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                if text and text.strip():
                    text_parts.append(text)
            
            full_text = "\n\n".join(text_parts)
            
            # Check if PDF is scanned (image-based)
            if self._is_scanned_pdf(doc, full_text):
                logger.info("PDF detected as scanned. Using OpenAI OCR...")
                result = self._extract_text_from_scanned_pdf(doc)
                doc.close()
                return result
            
            doc.close()
            logger.info(f"Extracted {len(full_text)} characters from {total_pages} pages")
            return full_text, total_pages
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise
    
    def _chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks"""
        chunks = []
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        chunk_index = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph exceeds chunk size, save current chunk
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append({
                    'content': current_chunk.strip(),
                    'chunk_index': chunk_index,
                    'metadata': {'length': len(current_chunk)}
                })
                
                # Add overlap from previous chunk
                words = current_chunk.split()
                overlap_text = ' '.join(words[-self.chunk_overlap:]) if len(words) > self.chunk_overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + paragraph
                chunk_index += 1
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                'content': current_chunk.strip(),
                'chunk_index': chunk_index,
                'metadata': {'length': len(current_chunk)}
            })
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
    
    async def delete_document(self, document_id: int) -> bool:
        """Delete document and associated chunks"""
        db = SessionLocal()
        
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                return False
            
            # Delete file from disk
            try:
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete file {document.file_path}: {e}")
            
            # Delete from database (cascades to chunks)
            db.delete(document)
            db.commit()
            
            logger.info(f"Document {document_id} deleted")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    async def get_document(self, document_id: int) -> Optional[Document]:
        """Get document by ID"""
        db = SessionLocal()
        try:
            return db.query(Document).filter(Document.id == document_id).first()
        finally:
            db.close()
    
    async def list_documents_for_agent(self, agent_id: int) -> List[Document]:
        """List all documents for an agent"""
        db = SessionLocal()
        try:
            return db.query(Document).filter(Document.agent_id == agent_id).all()
        finally:
            db.close()

