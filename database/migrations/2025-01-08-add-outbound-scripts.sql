-- Migration: Add outbound_scripts table
-- Date: 2025-01-08
-- Description: Add support for outbound call scripts/templates

-- Create outbound_scripts table
CREATE TABLE IF NOT EXISTS outbound_scripts (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Script details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Script content
    opening_message TEXT NOT NULL,
    main_content TEXT,
    closing_message TEXT,
    
    -- Behavioral instructions
    tone VARCHAR(50) DEFAULT 'professional',
    objective TEXT,
    key_points TEXT,
    objection_handling TEXT,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_favorite BOOLEAN DEFAULT FALSE,
    
    -- Usage stats
    use_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_outbound_scripts_agent_id ON outbound_scripts(agent_id);
CREATE INDEX IF NOT EXISTS idx_outbound_scripts_user_id ON outbound_scripts(user_id);
CREATE INDEX IF NOT EXISTS idx_outbound_scripts_is_active ON outbound_scripts(is_active);
CREATE INDEX IF NOT EXISTS idx_outbound_scripts_is_favorite ON outbound_scripts(is_favorite);

-- Add comment
COMMENT ON TABLE outbound_scripts IS 'Outbound call scripts/templates for AI agents';

