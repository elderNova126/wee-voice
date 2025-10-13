-- Add RAG support tables
-- Run this SQL in Supabase SQL Editor to add RAG functionality

-- Add RAG columns to voice_agents table
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS rag_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS rag_config JSONB;

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- File information
    filename VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    file_path VARCHAR,
    file_size INTEGER,
    mime_type VARCHAR DEFAULT 'application/pdf',
    
    -- Source information
    source_type VARCHAR DEFAULT 'pdf',  -- pdf, website, text
    source_url VARCHAR,  -- For websites
    
    -- Processing status
    status VARCHAR DEFAULT 'pending',  -- pending, processing, completed, failed
    error_message TEXT,
    
    -- Content metadata
    total_pages INTEGER,
    total_chunks INTEGER DEFAULT 0,
    doc_metadata JSONB,  -- Renamed from metadata to avoid SQLAlchemy conflict
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    
    CONSTRAINT fk_documents_agent FOREIGN KEY (agent_id) REFERENCES voice_agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Chunk data
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    
    -- Embedding data
    embedding JSONB,  -- Vector embedding as JSON array
    embedding_model VARCHAR DEFAULT 'all-MiniLM-L6-v2',
    
    -- Metadata
    chunk_metadata JSONB,  -- Renamed from metadata to avoid SQLAlchemy conflict
    token_count INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_chunks_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_agent_id ON documents(agent_id);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_documents_updated_at();

-- Add comments for documentation
COMMENT ON TABLE documents IS 'Stores RAG knowledge sources (PDFs, websites, etc.)';
COMMENT ON TABLE document_chunks IS 'Text chunks from documents with embeddings for semantic search';
COMMENT ON COLUMN documents.doc_metadata IS 'Document metadata (renamed from metadata to avoid SQLAlchemy conflict)';
COMMENT ON COLUMN document_chunks.chunk_metadata IS 'Chunk metadata (renamed from metadata to avoid SQLAlchemy conflict)';
COMMENT ON COLUMN document_chunks.embedding IS 'Vector embedding as JSON array for semantic search';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'RAG tables created successfully!';
    RAISE NOTICE 'Tables: documents, document_chunks';
    RAISE NOTICE 'Updated: voice_agents (added rag_enabled, rag_config)';
END $$;
