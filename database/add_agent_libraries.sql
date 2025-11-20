-- ===================================================================
-- AGENT LIBRARIES TABLE
-- ===================================================================
-- Table for storing agent templates/prompts that users can use
-- Supports both public libraries (admin-managed) and user libraries

-- Drop existing type if it exists
DROP TYPE IF EXISTS library_category CASCADE;

-- Library categories enum
CREATE TYPE library_category AS ENUM (
    'real_estate',
    'customer_service',
    'sales',
    'support',
    'marketing',
    'hr',
    'healthcare',
    'education',
    'finance',
    'legal',
    'general'
);

CREATE TABLE agent_libraries (
    id SERIAL PRIMARY KEY,
    
    -- Ownership
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,  -- NULL for public libraries
    is_public BOOLEAN DEFAULT FALSE,
    
    -- Library metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category library_category DEFAULT 'general',
    tags JSONB DEFAULT '[]'::JSONB,
    icon VARCHAR(50),
    language VARCHAR(50) DEFAULT 'fr-FR',
    
    -- Agent configuration template
    system_prompt TEXT NOT NULL,
    greeting TEXT,
    voice_id VARCHAR(100) DEFAULT 'Charon',
    voice_gender VARCHAR(20) DEFAULT 'male',
    
    -- Advanced configuration
    agent_config JSONB,
    tools_enabled JSONB DEFAULT '[]'::JSONB,
    model_name VARCHAR(255) DEFAULT 'gemini-2.5-flash-native-audio-preview-09-2025',
    temperature VARCHAR(10) DEFAULT '0.7',
    max_tokens INTEGER DEFAULT 1000,
    
    -- RAG Configuration
    rag_enabled BOOLEAN DEFAULT FALSE,
    rag_config JSONB,
    
    -- CRM Integration template
    crm_enabled BOOLEAN DEFAULT FALSE,
    crm_config JSONB,
    
    -- Usage statistics
    usage_count INTEGER DEFAULT 0,
    saved_count INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Create indexes
CREATE INDEX idx_libraries_public ON agent_libraries(is_public) WHERE is_public = TRUE;
CREATE INDEX idx_libraries_user ON agent_libraries(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_libraries_category ON agent_libraries(category);
CREATE INDEX idx_libraries_active ON agent_libraries(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_libraries_name ON agent_libraries(name);
CREATE INDEX idx_libraries_tags ON agent_libraries USING GIN (tags);
CREATE INDEX idx_libraries_public_active ON agent_libraries(is_public, is_active) WHERE is_public = TRUE AND is_active = TRUE;

