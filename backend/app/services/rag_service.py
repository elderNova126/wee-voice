import logging
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from pathlib import Path

from app.models import Document, DocumentChunk
from app.models.database import SessionLocal

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG: embeddings, vector storage, and retrieval"""
    
    def __init__(self, collection_name: str = "voice_agent_docs"):
        # Initialize embedding model
        self.embedding_model_name = "all-MiniLM-L6-v2"
        logger.info(f"Loading embedding model: {self.embedding_model_name}")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
        # Initialize ChromaDB
        chroma_path = Path("data/chroma")
        chroma_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"ChromaDB initialized with collection: {collection_name}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a text"""
        try:
            embedding = self.embedding_model.encode(text, show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            raise
    
    async def embed_document_chunks(self, document_id: int):
        """Generate and store embeddings for all chunks of a document"""
        db = SessionLocal()
        
        try:
            # Get all chunks for the document
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).all()
            
            if not chunks:
                logger.warning(f"No chunks found for document {document_id}")
                return
            
            logger.info(f"Embedding {len(chunks)} chunks for document {document_id}")
            
            # Prepare data for ChromaDB
            texts = [chunk.content for chunk in chunks]
            ids = [f"doc_{document_id}_chunk_{chunk.id}" for chunk in chunks]
            metadatas = [
                {
                    "document_id": document_id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number or 0
                }
                for chunk in chunks
            ]
            
            # Generate embeddings
            embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
            
            # Store in ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=texts,
                metadatas=metadatas
            )
            
            # Also store embeddings in database for backup
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding.tolist()
                chunk.embedding_model = self.embedding_model_name
            
            db.commit()
            
            logger.info(f"Successfully embedded {len(chunks)} chunks for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error embedding document chunks: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    async def retrieve_relevant_chunks(
        self, 
        query: str, 
        agent_id: int, 
        top_k: int = 5,
        score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Retrieve most relevant chunks for a query"""
        db = SessionLocal()
        
        try:
            # Get all document IDs for this agent
            documents = db.query(Document).filter(
                Document.agent_id == agent_id,
                Document.status == "completed"
            ).all()
            
            if not documents:
                logger.info(f"No documents found for agent {agent_id}")
                return []
            
            document_ids = [doc.id for doc in documents]
            
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Search in ChromaDB with filter for agent's documents
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,  # Get more results to filter
                where={"document_id": {"$in": document_ids}}
            )
            
            # Process results
            relevant_chunks = []
            
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i, (doc_id, distance, metadata, document) in enumerate(zip(
                    results['ids'][0],
                    results['distances'][0],
                    results['metadatas'][0],
                    results['documents'][0]
                )):
                    # Convert distance to similarity score (cosine similarity)
                    similarity = 1 - distance
                    
                    if similarity >= score_threshold:
                        chunk_data = {
                            'content': document,
                            'similarity': float(similarity),
                            'document_id': metadata['document_id'],
                            'chunk_id': metadata['chunk_id'],
                            'chunk_index': metadata['chunk_index'],
                            'page_number': metadata.get('page_number', 0)
                        }
                        relevant_chunks.append(chunk_data)
                        
                        if len(relevant_chunks) >= top_k:
                            break
            
            logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks for query")
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"Error retrieving chunks: {e}", exc_info=True)
            return []
        finally:
            db.close()
    
    async def delete_document_embeddings(self, document_id: int):
        """Delete all embeddings for a document"""
        try:
            # Get all chunk IDs for this document
            db = SessionLocal()
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).all()
            
            if not chunks:
                return
            
            # Delete from ChromaDB
            ids = [f"doc_{document_id}_chunk_{chunk.id}" for chunk in chunks]
            
            try:
                self.collection.delete(ids=ids)
                logger.info(f"Deleted embeddings for document {document_id}")
            except Exception as e:
                logger.warning(f"Error deleting from ChromaDB: {e}")
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error deleting document embeddings: {e}", exc_info=True)
    
    async def build_rag_context(
        self, 
        query: str, 
        agent_id: int, 
        max_chunks: int = 3
    ) -> str:
        """Build context string from retrieved chunks for RAG"""
        try:
            chunks = await self.retrieve_relevant_chunks(
                query=query,
                agent_id=agent_id,
                top_k=max_chunks,
                score_threshold=0.3
            )
            
            if not chunks:
                return ""
            
            # Format context
            context_parts = []
            for i, chunk in enumerate(chunks, 1):
                context_parts.append(
                    f"[Document {chunk['document_id']}, Page {chunk['page_number']}]:\n{chunk['content']}"
                )
            
            context = "\n\n---\n\n".join(context_parts)
            
            logger.info(f"Built RAG context from {len(chunks)} chunks ({len(context)} characters)")
            return context
            
        except Exception as e:
            logger.error(f"Error building RAG context: {e}", exc_info=True)
            return ""


# Global RAG service instance
_rag_service = None

def get_rag_service() -> RAGService:
    """Get or create RAG service singleton"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

