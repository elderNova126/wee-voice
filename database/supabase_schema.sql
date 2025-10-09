-- ===================================================================
-- VoiceAgent SaaS - Supabase Database Schema
-- PostgreSQL Schema for French Voice Agent Platform
-- ===================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===================================================================
-- ENUMS
-- ===================================================================

-- Drop existing types if they exist (for clean re-runs)
DROP TYPE IF EXISTS subscription_tier CASCADE;
DROP TYPE IF EXISTS call_status CASCADE;

-- Subscription tiers
CREATE TYPE subscription_tier AS ENUM ('free', 'basic', 'pro', 'enterprise');

-- Call status
CREATE TYPE call_status AS ENUM ('initiated', 'in_progress', 'completed', 'failed', 'interrupted');

-- ===================================================================
-- DROP EXISTING TABLES (for clean re-runs)
-- ===================================================================

DROP TABLE IF EXISTS call_messages CASCADE;
DROP TABLE IF EXISTS calls CASCADE;
DROP TABLE IF EXISTS voice_agents CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop views
DROP VIEW IF EXISTS call_statistics CASCADE;
DROP VIEW IF EXISTS agent_performance CASCADE;

-- ===================================================================
-- USERS TABLE
-- ===================================================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    
    -- Subscription
    subscription_tier subscription_tier DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    
    -- Usage tracking
    total_minutes_used FLOAT DEFAULT 0.0,
    monthly_minutes_used FLOAT DEFAULT 0.0,
    last_reset_date TIMESTAMP DEFAULT NOW(),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index on email for faster lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription ON users(subscription_tier);
CREATE INDEX idx_users_active ON users(is_active);

-- ===================================================================
-- API KEYS TABLE
-- ===================================================================

CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Usage tracking
    total_requests INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_api_keys_key ON api_keys(key);
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);

-- ===================================================================
-- VOICE AGENTS TABLE
-- ===================================================================

CREATE TABLE voice_agents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Agent configuration
    language VARCHAR(50) DEFAULT 'fr-FR',
    voice_id VARCHAR(100) DEFAULT 'fr-FR-Neural2-A',
    system_prompt TEXT NOT NULL,
    
    -- LangGraph configuration
    agent_config JSONB,
    tools_enabled JSONB DEFAULT '[]'::JSONB,
    
    -- Model settings
    model_name VARCHAR(255) DEFAULT 'gemini-2.5-flash-preview-native-audio-dialog',
    temperature VARCHAR(10) DEFAULT '0.7',
    max_tokens INTEGER DEFAULT 1000,
    
    -- CRM Integration
    crm_webhook_url VARCHAR(500),
    crm_enabled BOOLEAN DEFAULT FALSE,
    crm_config JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_agents_user ON voice_agents(user_id);
CREATE INDEX idx_agents_active ON voice_agents(is_active);
CREATE INDEX idx_agents_public ON voice_agents(is_public);
CREATE INDEX idx_agents_language ON voice_agents(language);

-- ===================================================================
-- CALLS TABLE
-- ===================================================================

CREATE TABLE calls (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    
    -- Call metadata
    session_id VARCHAR(255) UNIQUE NOT NULL,
    status call_status DEFAULT 'initiated',
    
    -- Duration and cost
    duration_seconds FLOAT DEFAULT 0.0,
    duration_minutes FLOAT DEFAULT 0.0,
    cost FLOAT DEFAULT 0.0,
    
    -- Audio files
    recording_url VARCHAR(500),
    
    -- Transcription
    transcript TEXT,
    transcript_json JSONB,
    
    -- Summary and analysis
    summary TEXT,
    sentiment VARCHAR(50),
    key_points JSONB,
    
    -- Caller information
    caller_phone VARCHAR(50),
    caller_name VARCHAR(255),
    caller_metadata JSONB,
    
    -- CRM data
    crm_synced BOOLEAN DEFAULT FALSE,
    crm_record_id VARCHAR(255),
    crm_response JSONB,
    
    -- Timestamps
    started_at TIMESTAMP,  -- Set when voice session actually starts (not when record is created)
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_calls_session ON calls(session_id);
CREATE INDEX idx_calls_user ON calls(user_id);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_created ON calls(created_at DESC);
CREATE INDEX idx_calls_sentiment ON calls(sentiment);

-- ===================================================================
-- CALL MESSAGES TABLE
-- ===================================================================

CREATE TABLE call_messages (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    
    -- Message data
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    audio_url VARCHAR(500),
    
    -- Timing
    timestamp TIMESTAMP DEFAULT NOW(),
    duration_seconds FLOAT
);

-- Create indexes
CREATE INDEX idx_messages_call ON call_messages(call_id);
CREATE INDEX idx_messages_timestamp ON call_messages(timestamp);
CREATE INDEX idx_messages_role ON call_messages(role);

-- ===================================================================
-- FUNCTIONS AND TRIGGERS
-- ===================================================================

-- Drop existing triggers first
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_agents_updated_at ON voice_agents;
DROP TRIGGER IF EXISTS calculate_call_duration_trigger ON calls;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS calculate_call_duration() CASCADE;
DROP FUNCTION IF EXISTS cleanup_old_calls(INTEGER) CASCADE;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for voice_agents table
CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON voice_agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate call duration
CREATE OR REPLACE FUNCTION calculate_call_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ended_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at));
        NEW.duration_minutes = NEW.duration_seconds / 60.0;
        NEW.cost = NEW.duration_minutes * 0.05; -- $0.05 per minute
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-calculate duration
CREATE TRIGGER calculate_call_duration_trigger
    BEFORE INSERT OR UPDATE ON calls
    FOR EACH ROW
    EXECUTE FUNCTION calculate_call_duration();

-- ===================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ===================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_messages ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (auth.uid()::text = id::text);

-- API Keys policies
CREATE POLICY api_keys_select_own ON api_keys
    FOR SELECT
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY api_keys_insert_own ON api_keys
    FOR INSERT
    WITH CHECK (user_id = (auth.uid()::text)::integer);

CREATE POLICY api_keys_delete_own ON api_keys
    FOR DELETE
    USING (user_id = (auth.uid()::text)::integer);

-- Voice Agents policies (including public agents)
CREATE POLICY agents_select_own_or_public ON voice_agents
    FOR SELECT
    USING (user_id = (auth.uid()::text)::integer OR is_public = TRUE);

CREATE POLICY agents_insert_own ON voice_agents
    FOR INSERT
    WITH CHECK (user_id = (auth.uid()::text)::integer);

CREATE POLICY agents_update_own ON voice_agents
    FOR UPDATE
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY agents_delete_own ON voice_agents
    FOR DELETE
    USING (user_id = (auth.uid()::text)::integer);

-- Calls policies
CREATE POLICY calls_select_own ON calls
    FOR SELECT
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY calls_insert_own ON calls
    FOR INSERT
    WITH CHECK (user_id = (auth.uid()::text)::integer);

CREATE POLICY calls_update_own ON calls
    FOR UPDATE
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY calls_delete_own ON calls
    FOR DELETE
    USING (user_id = (auth.uid()::text)::integer);

-- Call Messages policies (inherit from calls)
CREATE POLICY messages_select_via_call ON call_messages
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM calls
            WHERE calls.id = call_messages.call_id
            AND calls.user_id = (auth.uid()::text)::integer
        )
    );

CREATE POLICY messages_insert_via_call ON call_messages
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM calls
            WHERE calls.id = call_messages.call_id
            AND calls.user_id = (auth.uid()::text)::integer
        )
    );

-- ===================================================================
-- VIEWS
-- ===================================================================

-- View for call statistics
CREATE OR REPLACE VIEW call_statistics AS
SELECT
    u.id AS user_id,
    u.email,
    COUNT(c.id) AS total_calls,
    SUM(c.duration_minutes) AS total_minutes,
    SUM(c.cost) AS total_cost,
    AVG(c.duration_minutes) AS avg_duration_minutes,
    COUNT(CASE WHEN c.status = 'completed' THEN 1 END) AS completed_calls,
    COUNT(CASE WHEN c.status = 'failed' THEN 1 END) AS failed_calls
FROM users u
LEFT JOIN calls c ON u.id = c.user_id
GROUP BY u.id, u.email;

-- View for agent performance
CREATE OR REPLACE VIEW agent_performance AS
SELECT
    va.id AS agent_id,
    va.name AS agent_name,
    va.user_id,
    COUNT(c.id) AS total_calls,
    SUM(c.duration_minutes) AS total_minutes,
    AVG(c.duration_minutes) AS avg_duration,
    COUNT(CASE WHEN c.status = 'completed' THEN 1 END) AS completed_calls,
    COUNT(CASE WHEN c.sentiment = 'positive' THEN 1 END) AS positive_calls,
    COUNT(CASE WHEN c.sentiment = 'negative' THEN 1 END) AS negative_calls,
    COUNT(CASE WHEN c.sentiment = 'neutral' THEN 1 END) AS neutral_calls
FROM voice_agents va
LEFT JOIN calls c ON va.id = c.agent_id
GROUP BY va.id, va.name, va.user_id;

-- ===================================================================
-- SAMPLE DATA (Optional - for testing)
-- ===================================================================

-- Insert a test user (password is hashed 'password123')
INSERT INTO users (email, full_name, hashed_password, subscription_tier)
VALUES (
    'demo@voiceagent.com',
    'Demo User',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNk8L9Eia',
    'free'
);

-- Insert a demo agent
INSERT INTO voice_agents (
    user_id,
    name,
    description,
    language,
    system_prompt,
    is_public
)
VALUES (
    1,
    'Assistant Démo Français',
    'Agent de démonstration en français pour tester la plateforme',
    'fr-FR',
    'Tu es un assistant vocal intelligent et serviable qui répond toujours en français de manière naturelle et amicale.',
    TRUE
);

-- ===================================================================
-- COMMENTS
-- ===================================================================

COMMENT ON TABLE users IS 'Platform users with authentication and subscription info';
COMMENT ON TABLE api_keys IS 'API keys for programmatic access';
COMMENT ON TABLE voice_agents IS 'Voice agent configurations';
COMMENT ON TABLE calls IS 'Call history and analytics';
COMMENT ON TABLE call_messages IS 'Individual messages within calls';

-- ===================================================================
-- GRANTS (adjust based on your Supabase setup)
-- ===================================================================

-- Grant necessary permissions to authenticated users
-- GRANT SELECT, INSERT, UPDATE ON users TO authenticated;
-- GRANT ALL ON api_keys TO authenticated;
-- GRANT ALL ON voice_agents TO authenticated;
-- GRANT ALL ON calls TO authenticated;
-- GRANT ALL ON call_messages TO authenticated;

-- ===================================================================
-- MAINTENANCE
-- ===================================================================

-- Function to clean up old calls (optional)
CREATE OR REPLACE FUNCTION cleanup_old_calls(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM calls
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep
    AND status IN ('completed', 'failed');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ===================================================================
-- INDEXES FOR PERFORMANCE
-- ===================================================================

-- Additional indexes for common query patterns
CREATE INDEX idx_calls_user_created ON calls(user_id, created_at DESC);
CREATE INDEX idx_calls_agent_created ON calls(agent_id, created_at DESC);
CREATE INDEX idx_calls_user_status ON calls(user_id, status);
CREATE INDEX idx_agents_user_active ON voice_agents(user_id, is_active);

-- GIN index for JSONB columns
CREATE INDEX idx_agents_tools ON voice_agents USING GIN (tools_enabled);
CREATE INDEX idx_calls_key_points ON calls USING GIN (key_points);
CREATE INDEX idx_calls_transcript ON calls USING GIN (to_tsvector('french', transcript));

-- ===================================================================
-- COMPLETION
-- ===================================================================

-- Log schema creation
DO $$
BEGIN
    RAISE NOTICE 'VoiceAgent SaaS schema created successfully!';
    RAISE NOTICE 'Tables: users, api_keys, voice_agents, calls, call_messages';
    RAISE NOTICE 'Views: call_statistics, agent_performance';
    RAISE NOTICE 'Remember to configure your Supabase authentication!';
END $$;

