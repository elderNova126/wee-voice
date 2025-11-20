import logging
import requests
from bs4 import BeautifulSoup
import html2text
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


class WebScraperService:
    """Service for scraping and processing web content"""
    
    def __init__(self):
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
    
    def scrape_url(self, url: str) -> tuple[str, str]:
        """
        Scrape content from a URL
        
        Returns:
            Tuple of (title, content)
        """
        try:
            logger.info(f"Scraping URL: {url}")
            
            # Set user agent to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else urlparse(url).netloc
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Convert to markdown
            html_content = str(soup)
            markdown_content = self.html_converter.handle(html_content)
            
            # Clean up content
            lines = [line.strip() for line in markdown_content.split('\n')]
            lines = [line for line in lines if line and not line.startswith('#')]
            content = '\n\n'.join(lines)
            
            logger.info(f"Scraped {len(content)} characters from {url}")
            return title, content
            
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
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
    
    async def scrape_and_process_url(
        self,
        db: Session,
        url: str,
        agent_id: int,
        user_id: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """
        Scrape a URL and process it into document chunks
        """
        # Create document record
        document = Document(
            agent_id=agent_id,
            user_id=user_id,
            filename=url,
            original_filename=url,
            source_type="website",
            source_url=url,
            status="processing"
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        try:
            # Scrape content
            title, content = self.scrape_url(url)
            
            if not content or len(content.strip()) < 50:
                raise ValueError("No meaningful content could be extracted from URL")
            
            # Update document metadata
            document.doc_metadata = {
                **(metadata or {}),
                'title': title,
                'content_length': len(content),
                'scraped_at': datetime.utcnow().isoformat()
            }
            
            # Chunk text
            logger.info("Chunking website content...")
            chunks = self._chunk_text(content)
            document.total_chunks = len(chunks)
            
            # Save chunks
            for idx, chunk_data in enumerate(chunks):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_data['content'],
                    page_number=None,  # No pages for websites
                    chunk_metadata=chunk_data.get('metadata', {}),
                    token_count=len(chunk_data['content'].split())
                )
                db.add(chunk)
            
            document.status = "completed"
            document.processed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(document)
            
            logger.info(f"Website processed successfully: {document.id}, {len(chunks)} chunks")
            return document
            
        except Exception as e:
            logger.error(f"Error processing website: {e}", exc_info=True)
            document.status = "failed"
            document.error_message = str(e)
            db.commit()
            raise
