import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import hashlib

try:
    import requests
    from bs4 import BeautifulSoup
    import html2text
    SCRAPING_AVAILABLE = True
except ImportError:
    SCRAPING_AVAILABLE = False

from app.models import Document, DocumentChunk
from app.models.database import SessionLocal

logger = logging.getLogger(__name__)


class WebScraperService:
    """Service for scraping and processing web pages for RAG"""
    
    def __init__(self):
        if not SCRAPING_AVAILABLE:
            raise ImportError("Web scraping dependencies not installed. Install: pip install beautifulsoup4 requests html2text")
        
        self.chunk_size = 1000  # characters
        self.chunk_overlap = 200  # characters
        
        # Configure HTML to text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # Don't wrap text
    
    async def scrape_and_process_url(
        self,
        url: str,
        agent_id: int,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """Scrape a URL and process it for RAG"""
        db = SessionLocal()
        
        try:
            logger.info(f"Scraping URL: {url}")
            
            # Create document record
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            filename = f"web_{url_hash}.txt"
            
            document = Document(
                agent_id=agent_id,
                user_id=user_id,
                filename=filename,
                original_filename=self._extract_page_title_from_url(url),
                file_path=None,  # No file for web content
                file_size=None,
                mime_type="text/html",
                source_type="website",
                source_url=url,
                status="processing",
                doc_metadata=metadata or {}
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Scrape the content
            content = await self._scrape_url(url)
            
            if not content:
                raise ValueError("Failed to extract content from URL")
            
            # Update metadata with page info
            document.doc_metadata = {
                **(metadata or {}),
                'content_length': len(content),
                'scraped_at': datetime.utcnow().isoformat()
            }
            
            # Process the content
            await self._process_web_content(document.id, content)
            
            db.refresh(document)
            return document
            
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}", exc_info=True)
            if 'document' in locals():
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
            raise
        finally:
            db.close()
    
    def _extract_page_title_from_url(self, url: str) -> str:
        """Extract a readable name from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace('www.', '')
    
    async def _scrape_url(self, url: str) -> str:
        """Scrape content from a URL"""
        try:
            # Set user agent to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get page title
            title = soup.find('title')
            title_text = title.string if title else ""
            
            # Convert HTML to markdown/text
            html_content = str(soup)
            text_content = self.html_converter.handle(html_content)
            
            # Combine title and content
            full_content = f"# {title_text}\n\nSource: {url}\n\n{text_content}"
            
            logger.info(f"Scraped {len(full_content)} characters from {url}")
            return full_content
            
        except requests.RequestException as e:
            logger.error(f"Request error scraping {url}: {e}")
            raise ValueError(f"Failed to fetch URL: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing content from {url}: {e}")
            raise ValueError(f"Failed to parse content: {str(e)}")
    
    async def _process_web_content(self, document_id: int, content: str):
        """Process scraped content: chunk and prepare for embedding"""
        db = SessionLocal()
        
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            logger.info(f"Processing web content for document {document_id}")
            
            # Chunk the text
            chunks = self._chunk_text(content)
            
            # Create chunk records
            for idx, chunk_data in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_data['content'],
                    page_number=None,  # No pages for web content
                    chunk_metadata=chunk_data.get('metadata', {}),
                    token_count=len(chunk_data['content'].split())
                )
                db.add(chunk)
            
            # Update document status
            document.status = "completed"
            document.total_chunks = len(chunks)
            document.total_pages = 1  # Treat as single page
            document.processed_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Web document {document_id} processed: {len(chunks)} chunks created")
            
        except Exception as e:
            logger.error(f"Error processing web content {document_id}: {e}", exc_info=True)
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
            raise
        finally:
            db.close()
    
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
        
        logger.info(f"Created {len(chunks)} chunks from web content")
        return chunks
    
    async def scrape_multiple_urls(
        self,
        urls: List[str],
        agent_id: int,
        user_id: int
    ) -> List[Document]:
        """Scrape multiple URLs"""
        documents = []
        
        for url in urls:
            try:
                doc = await self.scrape_and_process_url(url, agent_id, user_id)
                documents.append(doc)
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {e}")
                # Continue with other URLs
                continue
        
        return documents

