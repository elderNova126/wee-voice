import os
import logging
import base64
import tempfile
from datetime import datetime
from typing import List, Tuple
import fitz  # PyMuPDF
from sqlalchemy.orm import Session
from openai import OpenAI

from app.models.document import Document, DocumentChunk
from app.core.config import settings
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for handling document upload, processing, and text extraction"""
    
    def __init__(self):
        # Use storage service instead of local directory
        # Keep upload_dir for backward compatibility with local fallback
        self.upload_dir = "uploads/documents"
        self.use_storage = storage_service.is_storage_enabled()
        
        if not self.use_storage:
            # Fallback to local storage if storage is not configured
            os.makedirs(self.upload_dir, exist_ok=True)
            logger.warning("⚠️ Storage service not configured. Using local file storage as fallback.")
        else:
            logger.info("✅ Using storage service for document uploads")
        
        # Initialize OpenAI client for OCR if API key is available
        self.openai_client = None
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            try:
                self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized for OCR")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
    
    def _is_scanned_pdf(self, doc: fitz.Document, text: str) -> bool:
        """
        Detect if a PDF is scanned (image-based) by analyzing text density
        and image presence
        """
        total_pages = len(doc)
        
        # If very little text extracted, likely scanned
        if not text or len(text.strip()) < 100:
            return True
        
        # Check text density (characters per page)
        chars_per_page = len(text) / max(total_pages, 1)
        
        # Check for images in first few pages
        image_heavy = False
        if total_pages > 0:
            sample_pages = min(3, total_pages)
            images_found = 0
            for page_num in range(sample_pages):
                page = doc[page_num]
                image_list = page.get_images()
                if len(image_list) > 0:
                    images_found += 1
            
            if images_found >= sample_pages * 0.7:  # 70% of pages have images
                image_heavy = True
        
        # If low text density or heavy images, consider it scanned
        if chars_per_page < 200 or image_heavy:
            logger.info(f"PDF appears to be scanned ({chars_per_page:.0f} chars/page, image_heavy={image_heavy})")
            return True
        
        return False
    
    def _ocr_page_with_openai(self, page_image_bytes: bytes, page_num: int) -> str:
        """Use OpenAI Vision API to extract text from a page image"""
        if not self.openai_client:
            logger.warning("OpenAI client not available for OCR")
            return ""
        
        try:
            # Convert image bytes to base64
            img_base64 = base64.b64encode(page_image_bytes).decode()
            
            # Call OpenAI Vision API
            response = self.openai_client.chat.completions.create(
                model=getattr(settings, 'OPENAI_OCR_MODEL', 'gpt-4o'),
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
    
    def _extract_text_from_scanned_pdf(self, doc: fitz.Document) -> Tuple[str, int]:
        """Extract text from scanned PDF using OCR"""
        if not self.openai_client:
            raise ValueError("OpenAI API key required for OCR. Please set OPENAI_API_KEY in .env")
        
        logger.info(f"Processing scanned PDF with {len(doc)} pages using OpenAI OCR...")
        text_parts = []
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            try:
                page = doc[page_num]
                
                # Render page to image at 200 DPI for good OCR quality
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom = ~200 DPI
                img_bytes = pix.pil_tobytes(format="PNG")
                
                # OCR the page
                page_text = self._ocr_page_with_openai(img_bytes, page_num + 1)
                if page_text:
                    text_parts.append(page_text)
                
                logger.info(f"OCR progress: {page_num + 1}/{total_pages} pages")
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
                continue
        
        full_text = "\n\n".join(text_parts)
        logger.info(f"OCR completed: {len(full_text)} characters extracted from {total_pages} pages")
        return full_text, total_pages
    
    def _extract_text_from_pdf(self, file_path: str) -> Tuple[str, int]:
        """Extract text from PDF, with automatic scanned PDF detection and OCR"""
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            
            # First, try standard text extraction
            text_parts = []
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                if text and text.strip():
                    text_parts.append(text)
            
            full_text = "\n\n".join(text_parts)
            
            # Check if PDF is scanned
            if self._is_scanned_pdf(doc, full_text):
                logger.info("PDF detected as scanned. Using OpenAI OCR...")
                result = self._extract_text_from_scanned_pdf(doc)
                doc.close()
                return result
            
            # Standard PDF with text
            doc.close()
            logger.info(f"Extracted {len(full_text)} characters from {total_pages} pages")
            return full_text, total_pages
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            raise
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[dict]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            if chunk_text.strip():
                chunks.append({
                    'content': chunk_text,
                    'metadata': {
                        'start_word': i,
                        'end_word': i + len(chunk_words),
                        'word_count': len(chunk_words)
                    }
                })
        
        return chunks
    
    async def upload_and_process_document(
        self,
        db: Session,
        agent_id: int,
        user_id: int,
        file_content: bytes,
        filename: str
    ) -> Document:
        """Upload and process a PDF document"""
        
        # Create document record
        document = Document(
            agent_id=agent_id,
            user_id=user_id,
            filename=f"{datetime.utcnow().timestamp()}_{filename}",
            original_filename=filename,
            file_size=len(file_content),
            mime_type="application/pdf",
            source_type="pdf",
            status="processing"
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        temp_file_path = None
        
        try:
            if self.use_storage:
                # Upload to storage service
                logger.info(f"Uploading {filename} to storage service...")
                file_path = await storage_service.upload_file(
                    file_content=file_content,
                    filename=document.filename,
                    agent_id=agent_id,
                    user_id=user_id,
                    mime_type="application/pdf"
                )
                
                document.file_path = file_path
                # Generate public URL if needed
                if storage_service.is_storage_enabled():
                    try:
                        public_url = storage_service.get_public_url(file_path)
                        document.file_url = public_url
                    except Exception as e:
                        logger.warning(f"Could not generate public URL: {e}")
                
                # Create temporary file for PDF processing
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                
                pdf_file_path = temp_file_path
                
            else:
                # Fallback to local storage
                file_path = os.path.join(self.upload_dir, document.filename)
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                
                document.file_path = file_path
                pdf_file_path = file_path
            
            # Extract text
            logger.info(f"Extracting text from {filename}...")
            text, total_pages = self._extract_text_from_pdf(pdf_file_path)
            
            if not text or len(text.strip()) < 50:
                raise ValueError("No text could be extracted from PDF")
            
            document.total_pages = total_pages
            document.doc_metadata = {
                'text_length': len(text),
                'extraction_method': 'ocr' if self._is_scanned_pdf(fitz.open(pdf_file_path), text) else 'standard',
                'storage_type': 'storage' if self.use_storage else 'local'
            }
            
            # Chunk text
            logger.info("Chunking text...")
            chunks = self._chunk_text(text)
            document.total_chunks = len(chunks)
            
            # Save chunks
            for idx, chunk_data in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_data['content'],
                    chunk_metadata=chunk_data.get('metadata', {}),
                    token_count=len(chunk_data['content'].split())
                )
                db.add(chunk)
            
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(document)
            
            logger.info(f"Document processed successfully: {document.id}, {len(chunks)} chunks")
            return document
            
        except Exception as e:
            logger.error(f"Error processing document: {e}", exc_info=True)
            document.status = "failed"
            document.error_message = str(e)
            db.commit()
            raise
            
        finally:
            # Clean up temporary file if created
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_file_path}: {e}")
