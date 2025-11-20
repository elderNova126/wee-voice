import logging
from typing import List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.models.document import DocumentChunk

logger = logging.getLogger(__name__)

# Singleton instance
_rag_service_instance = None


def get_rag_service():
    """Get singleton RAG service instance"""
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance


class RAGService:
    """Service for RAG (Retrieval-Augmented Generation) operations"""
    
    def __init__(self):
        self.embedding_model_name = "all-MiniLM-L6-v2"
        self.embedding_model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text"""
        if not self.embedding_model:
            self._load_model()
        
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def process_chunks_embeddings(self, db: Session, document_id: int):
        """Generate embeddings for all chunks of a document"""
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        
        for chunk in chunks:
            if not chunk.embedding:  # Skip if already has embedding
                try:
                    embedding = self.generate_embedding(chunk.content)
                    chunk.embedding = embedding
                except Exception as e:
                    logger.error(f"Error generating embedding for chunk {chunk.id}: {e}")
        
        db.commit()
        logger.info(f"Embeddings generated for {len(chunks)} chunks")
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def search_similar_chunks(
        self,
        db: Session,
        agent_id: int,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks using semantic search
        
        Args:
            db: Database session
            agent_id: Agent ID to search documents for
            query: Search query text
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of matching chunks with metadata and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Get all chunks for this agent's documents
            from app.models.document import Document
            chunks = db.query(DocumentChunk).join(Document).filter(
                Document.agent_id == agent_id,
                Document.status == "completed",
                DocumentChunk.embedding.isnot(None)
            ).all()
            
            if not chunks:
                logger.info(f"No chunks found for agent {agent_id}")
                return []
            
            # Calculate similarities
            results = []
            for chunk in chunks:
                if chunk.embedding:
                    similarity = self.cosine_similarity(query_embedding, chunk.embedding)
                    
                    if similarity >= min_similarity:
                        results.append({
                            'chunk_id': chunk.id,
                            'document_id': chunk.document_id,
                            'content': chunk.content,
                            'similarity': similarity,
                            'page_number': chunk.page_number,
                            'chunk_metadata': chunk.chunk_metadata
                        })
            
            # Sort by similarity and return top k
            results.sort(key=lambda x: x['similarity'], reverse=True)
            top_results = results[:top_k]
            
            logger.info(f"Found {len(top_results)} relevant chunks for query")
            return top_results
            
        except Exception as e:
            logger.error(f"Error searching chunks: {e}", exc_info=True)
            return []
    
    def format_context_for_llm(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into context for LLM"""
        if not chunks:
            return ""
        
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"[Source {i}] {chunk['content']}")
        
        return "\n\n".join(context_parts)
