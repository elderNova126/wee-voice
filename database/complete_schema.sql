-- ===================================================================
-- VoiceAgent SaaS - Complete Database Schema
-- PostgreSQL Schema for French Voice Agent Platform
-- Date: 2025-10-10
-- ===================================================================
-- 
-- This file contains the complete database schema including:
-- 1. Core tables (users, agents, calls, API keys)
-- 2. Billing & Usage tracking
-- 3. Security (domain/IP allowlists, logs)
-- 4. Support ticketing system
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

-- Drop all tables in correct order (respecting foreign keys)
DROP TABLE IF EXISTS ticket_responses CASCADE;
DROP TABLE IF EXISTS support_tickets CASCADE;
DROP TABLE IF EXISTS security_logs CASCADE;
DROP TABLE IF EXISTS ip_allowlists CASCADE;
DROP TABLE IF EXISTS domain_allowlists CASCADE;
DROP TABLE IF EXISTS usage_records CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
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
    
    -- Credit system
    credit_balance FLOAT DEFAULT 0.0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes on users
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
CREATE INDEX idx_agents_user_active ON voice_agents(user_id, is_active);

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
    started_at TIMESTAMP,
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
CREATE INDEX idx_calls_user_created ON calls(user_id, created_at DESC);
CREATE INDEX idx_calls_agent_created ON calls(agent_id, created_at DESC);
CREATE INDEX idx_calls_user_status ON calls(user_id, status);

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
-- TRANSACTIONS TABLE (Billing)
-- ===================================================================

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Transaction details
    amount FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    status VARCHAR(50) DEFAULT 'pending',
    description TEXT,
    
    -- Payment provider data
    stripe_payment_intent_id VARCHAR(255) UNIQUE,
    stripe_charge_id VARCHAR(255),
    payment_method VARCHAR(100),
    
    -- Metadata
    metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- ===================================================================
-- INVOICES TABLE (Billing)
-- ===================================================================

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Invoice details
    invoice_number VARCHAR(100) UNIQUE NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    status VARCHAR(50) DEFAULT 'draft',
    
    -- Billing period
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    
    -- Stripe data
    stripe_invoice_id VARCHAR(255) UNIQUE,
    stripe_invoice_url TEXT,
    stripe_pdf_url TEXT,
    
    -- Payment
    paid_at TIMESTAMP,
    due_date TIMESTAMP,
    
    -- Line items
    line_items JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_invoices_user_id ON invoices(user_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_created_at ON invoices(created_at);

-- ===================================================================
-- USAGE RECORDS TABLE
-- ===================================================================

CREATE TABLE IF NOT EXISTS usage_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES voice_agents(id) ON DELETE SET NULL,
    call_id INTEGER REFERENCES calls(id) ON DELETE SET NULL,
    
    -- Usage details
    minutes_used FLOAT NOT NULL,
    cost FLOAT NOT NULL,
    
    -- Metadata
    date TIMESTAMP NOT NULL,
    month VARCHAR(7) NOT NULL,  -- Format: "2025-01"
    year INTEGER NOT NULL,
    
    -- Additional metrics
    api_calls INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_records_user_id ON usage_records(user_id);
CREATE INDEX idx_usage_records_agent_id ON usage_records(agent_id);
CREATE INDEX idx_usage_records_date ON usage_records(date);
CREATE INDEX idx_usage_records_month ON usage_records(month);
CREATE INDEX idx_usage_records_year ON usage_records(year);

-- ===================================================================
-- DOMAIN ALLOWLIST TABLE (Security)
-- ===================================================================

CREATE TABLE IF NOT EXISTS domain_allowlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Domain details
    domain VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Public key for this domain
    public_key VARCHAR(255) UNIQUE NOT NULL,
    
    -- Validation
    verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    
    -- Usage stats
    total_requests INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_domain_allowlists_user_id ON domain_allowlists(user_id);
CREATE INDEX idx_domain_allowlists_domain ON domain_allowlists(domain);
CREATE INDEX idx_domain_allowlists_public_key ON domain_allowlists(public_key);
CREATE UNIQUE INDEX idx_domain_allowlists_user_domain ON domain_allowlists(user_id, domain);

-- ===================================================================
-- IP ALLOWLIST TABLE (Security)
-- ===================================================================

CREATE TABLE IF NOT EXISTS ip_allowlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- IP details
    ip_address VARCHAR(45) NOT NULL,  -- Supports IPv4 and IPv6
    ip_range VARCHAR(50),  -- CIDR notation
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Usage stats
    total_requests INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ip_allowlists_user_id ON ip_allowlists(user_id);
CREATE INDEX idx_ip_allowlists_ip_address ON ip_allowlists(ip_address);
CREATE UNIQUE INDEX idx_ip_allowlists_user_ip ON ip_allowlists(user_id, ip_address);

-- ===================================================================
-- SECURITY LOGS TABLE
-- ===================================================================

CREATE TABLE IF NOT EXISTS security_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) DEFAULT 'info',
    message TEXT NOT NULL,
    
    -- Request details
    ip_address VARCHAR(45),
    user_agent TEXT,
    endpoint VARCHAR(255),
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_security_logs_user_id ON security_logs(user_id);
CREATE INDEX idx_security_logs_event_type ON security_logs(event_type);
CREATE INDEX idx_security_logs_severity ON security_logs(severity);
CREATE INDEX idx_security_logs_created_at ON security_logs(created_at);

-- ===================================================================
-- SUPPORT TICKETS TABLE
-- ===================================================================

CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Contact Information
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    
    -- Ticket Details
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'open',
    
    -- Metadata
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_support_tickets_ticket_number ON support_tickets(ticket_number);
CREATE INDEX idx_support_tickets_email ON support_tickets(email);
CREATE INDEX idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX idx_support_tickets_status ON support_tickets(status);
CREATE INDEX idx_support_tickets_created_at ON support_tickets(created_at);

-- ===================================================================
-- TICKET RESPONSES TABLE
-- ===================================================================

CREATE TABLE IF NOT EXISTS ticket_responses (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    
    -- Response Details
    message TEXT NOT NULL,
    is_staff_response BOOLEAN DEFAULT FALSE,
    staff_name VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ticket_responses_ticket_id ON ticket_responses(ticket_id);
CREATE INDEX idx_ticket_responses_created_at ON ticket_responses(created_at);

-- ===================================================================
-- FUNCTIONS AND TRIGGERS
-- ===================================================================

-- Drop existing triggers first
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_agents_updated_at ON voice_agents;
DROP TRIGGER IF EXISTS calculate_call_duration_trigger ON calls;
DROP TRIGGER IF EXISTS update_transactions_updated_at ON transactions;
DROP TRIGGER IF EXISTS update_invoices_updated_at ON invoices;
DROP TRIGGER IF EXISTS update_domain_allowlists_updated_at ON domain_allowlists;
DROP TRIGGER IF EXISTS update_ip_allowlists_updated_at ON ip_allowlists;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS calculate_call_duration() CASCADE;
DROP FUNCTION IF EXISTS cleanup_old_calls(INTEGER) CASCADE;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
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

-- Trigger for transactions
CREATE TRIGGER update_transactions_updated_at 
    BEFORE UPDATE ON transactions
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for invoices
CREATE TRIGGER update_invoices_updated_at 
    BEFORE UPDATE ON invoices
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for domain allowlists
CREATE TRIGGER update_domain_allowlists_updated_at 
    BEFORE UPDATE ON domain_allowlists
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for IP allowlists
CREATE TRIGGER update_ip_allowlists_updated_at 
    BEFORE UPDATE ON ip_allowlists
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
-- GIN INDEXES FOR JSONB COLUMNS
-- ===================================================================

CREATE INDEX idx_agents_tools ON voice_agents USING GIN (tools_enabled);
CREATE INDEX idx_calls_key_points ON calls USING GIN (key_points);
CREATE INDEX idx_calls_transcript ON calls USING GIN (to_tsvector('french', transcript));

-- ===================================================================
-- MAINTENANCE FUNCTIONS
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
-- COMMENTS
-- ===================================================================

COMMENT ON TABLE users IS 'Platform users with authentication and subscription info';
COMMENT ON TABLE api_keys IS 'API keys for programmatic access';
COMMENT ON TABLE voice_agents IS 'Voice agent configurations';
COMMENT ON TABLE calls IS 'Call history and analytics';
COMMENT ON TABLE call_messages IS 'Individual messages within calls';
COMMENT ON TABLE transactions IS 'Payment transactions and billing history';
COMMENT ON TABLE invoices IS 'Generated invoices for billing periods';
COMMENT ON TABLE usage_records IS 'Detailed usage tracking per call/agent';
COMMENT ON TABLE domain_allowlists IS 'Allowed domains for ChatKit integration';
COMMENT ON TABLE ip_allowlists IS 'IP restrictions for security';
COMMENT ON TABLE security_logs IS 'Security events and audit trail';
COMMENT ON TABLE support_tickets IS 'Support tickets submitted by users';
COMMENT ON TABLE ticket_responses IS 'Responses to support tickets from users or staff';

-- ===================================================================
-- SAMPLE DATA (Optional - for testing)
-- ===================================================================

-- Insert a test user (password is 'password123')
INSERT INTO users (email, full_name, hashed_password, subscription_tier)
VALUES (
    'demo@voiceagent.com',
    'Demo User',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNk8L9Eia',
    'free'
) ON CONFLICT (email) DO NOTHING;

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
) ON CONFLICT DO NOTHING;

-- ===================================================================
-- COMPLETION
-- ===================================================================

DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'VoiceAgent SaaS Complete Schema Created Successfully!';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Core Tables: users, api_keys, voice_agents, calls, call_messages';
    RAISE NOTICE 'Billing: transactions, invoices, usage_records';
    RAISE NOTICE 'Security: domain_allowlists, ip_allowlists, security_logs';
    RAISE NOTICE 'Support: support_tickets, ticket_responses';
    RAISE NOTICE 'Views: call_statistics, agent_performance';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Remember to configure environment variables!';
END $$;

