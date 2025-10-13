-- Migration: Add RAG (Documents and Document Chunks) tables
-- This script adds support for PDF document upload and RAG functionality

-- Add RAG configuration to voice_agents table
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS rag_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS rag_config JSONB;

COMMENT ON COLUMN voice_agents.rag_enabled IS 'Whether RAG (Retrieval-Augmented Generation) is enabled for this agent';
COMMENT ON COLUMN voice_agents.rag_config IS 'RAG-specific settings (chunk size, retrieval count, etc.)';

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Document metadata
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_size INTEGER,
    mime_type VARCHAR(100) DEFAULT 'application/pdf',
    
    -- Source information
    source_type VARCHAR(50) DEFAULT 'pdf',  -- pdf, website, text
    source_url TEXT,  -- Original URL if from web
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    error_message TEXT,
    
    -- Document content
    total_pages INTEGER,
    total_chunks INTEGER DEFAULT 0,
    
    -- Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    doc_metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_agent_id ON documents(agent_id);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

COMMENT ON TABLE documents IS 'Stores uploaded PDF documents for RAG';
COMMENT ON COLUMN documents.status IS 'Processing status: pending, processing, completed, failed';

-- Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Chunk content
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    
    -- Embedding (stored as JSON array)
    embedding JSONB,
    embedding_model VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    
    -- Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    chunk_metadata JSONB,
    token_count INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for document_chunks
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(document_id, chunk_index);

-- Full-text search index on chunk content
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_fts ON document_chunks USING GIN (to_tsvector('french', content));

COMMENT ON TABLE document_chunks IS 'Stores text chunks from documents with embeddings for RAG';
COMMENT ON COLUMN document_chunks.embedding IS 'Vector embedding for semantic search (stored as JSON array)';

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_updated_at_trigger
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_documents_updated_at();

-- Grant permissions (adjust based on your database user)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON document_chunks TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE documents_id_seq TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE document_chunks_id_seq TO your_app_user;

-- Create a view for document statistics
CREATE OR REPLACE VIEW document_statistics AS
SELECT 
    d.agent_id,
    COUNT(DISTINCT d.id) as total_documents,
    SUM(d.total_chunks) as total_chunks,
    SUM(d.file_size) as total_storage_bytes,
    COUNT(CASE WHEN d.status = 'completed' THEN 1 END) as completed_documents,
    COUNT(CASE WHEN d.status = 'failed' THEN 1 END) as failed_documents,
    COUNT(CASE WHEN d.status = 'processing' THEN 1 END) as processing_documents
FROM documents d
GROUP BY d.agent_id;

COMMENT ON VIEW document_statistics IS 'Statistics about documents per agent';

-- Sample query to check RAG setup
-- SELECT 
--     a.id as agent_id,
--     a.name as agent_name,
--     a.rag_enabled,
--     COALESCE(ds.total_documents, 0) as total_documents,
--     COALESCE(ds.total_chunks, 0) as total_chunks
-- FROM voice_agents a
-- LEFT JOIN document_statistics ds ON a.id = ds.agent_id
-- WHERE a.rag_enabled = TRUE;

