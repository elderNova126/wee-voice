-- ===================================================================
-- VoiceAgent SaaS - Complete Database Schema
-- Single Comprehensive SQL File for PostgreSQL
-- Date: 2025-10-10
-- ===================================================================
-- 
-- This file contains the COMPLETE database schema including:
-- 1. Core tables (users, agents, calls, API keys)
-- 2. Billing & Usage tracking (transactions, invoices, usage_records)
-- 3. Security (domain/IP allowlists, logs)
-- 4. Support ticketing system
-- 5. Integrations (Calendar, Email, CRM, Database, Accounting, etc.)
-- 6. Views, Triggers, Functions
-- 
-- This file is IDEMPOTENT - safe to run multiple times
-- Works for both standard PostgreSQL and Supabase
-- ===================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===================================================================
-- ENUMS
-- ===================================================================

-- Drop existing types if they exist (for clean re-runs)
DROP TYPE IF EXISTS subscription_tier CASCADE;
DROP TYPE IF EXISTS call_status CASCADE;
DROP TYPE IF EXISTS ticket_status CASCADE;
DROP TYPE IF EXISTS ticket_priority CASCADE;
DROP TYPE IF EXISTS ticket_category CASCADE;
-- Note: Integration types use VARCHAR instead of ENUM to match Python SQLAlchemy model
DROP TYPE IF EXISTS integration_type CASCADE;
DROP TYPE IF EXISTS integration_provider CASCADE;
DROP TYPE IF EXISTS integration_status CASCADE;

-- Subscription tiers
CREATE TYPE subscription_tier AS ENUM ('free', 'basic', 'pro', 'enterprise');

-- Call status
CREATE TYPE call_status AS ENUM ('initiated', 'in_progress', 'completed', 'failed', 'interrupted');

-- Support ticket types
CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'resolved', 'closed');
CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE ticket_category AS ENUM ('technical', 'billing', 'feature_request', 'bug', 'other');

-- ===================================================================
-- DROP EXISTING OBJECTS (for clean re-runs)
-- ===================================================================

-- Drop views first
DROP VIEW IF EXISTS call_statistics CASCADE;
DROP VIEW IF EXISTS agent_performance CASCADE;

-- Drop tables in correct order (respecting foreign keys)
DROP TABLE IF EXISTS ticket_responses CASCADE;
DROP TABLE IF EXISTS support_tickets CASCADE;
DROP TABLE IF EXISTS security_logs CASCADE;
DROP TABLE IF EXISTS ip_allowlists CASCADE;
DROP TABLE IF EXISTS domain_allowlists CASCADE;
DROP TABLE IF EXISTS integrations CASCADE;
DROP TABLE IF EXISTS usage_records CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS call_messages CASCADE;
DROP TABLE IF EXISTS calls CASCADE;
DROP TABLE IF EXISTS voice_agents CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP TRIGGER IF EXISTS update_voice_agents_updated_at ON voice_agents;
DROP TRIGGER IF EXISTS update_integrations_updated_at ON integrations;
DROP TRIGGER IF EXISTS update_support_tickets_updated_at ON support_tickets;
DROP TRIGGER IF EXISTS calculate_call_duration_trigger ON calls;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS calculate_call_duration() CASCADE;
DROP FUNCTION IF EXISTS cleanup_old_calls(INTEGER) CASCADE;

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
    
    -- CRM Integration (legacy - now use integrations table)
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
-- INTEGRATIONS TABLE
-- ===================================================================

CREATE TABLE integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Integration identification
    name VARCHAR(255) NOT NULL,
    description TEXT,
    integration_type VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    
    -- Configuration (encrypted credentials stored here)
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'inactive',
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    last_error TEXT,
    
    -- Metadata (using integration_metadata to avoid SQLAlchemy conflict)
    integration_metadata JSONB DEFAULT '{}'::JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_integrations_user_id ON integrations(user_id);
CREATE INDEX idx_integrations_type ON integrations(integration_type);
CREATE INDEX idx_integrations_provider ON integrations(provider);
CREATE INDEX idx_integrations_status ON integrations(status);
CREATE INDEX idx_integrations_active ON integrations(is_active);
CREATE INDEX idx_integrations_user_type ON integrations(user_id, integration_type);
CREATE INDEX idx_integrations_user_active ON integrations(user_id, is_active);
CREATE INDEX idx_integrations_created ON integrations(created_at DESC);

-- Add constraints for data integrity
ALTER TABLE integrations 
ADD CONSTRAINT check_integration_type 
CHECK (integration_type IN (
    'calendar', 'email', 'contact_management', 
    'database', 'crm', 'accounting', 'other'
));

ALTER TABLE integrations 
ADD CONSTRAINT check_status 
CHECK (status IN ('active', 'inactive', 'error', 'pending_auth'));

-- ===================================================================
-- CALLS TABLE
-- ===================================================================

CREATE TABLE calls (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    
    -- Session identification
    session_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- Call data
    status call_status DEFAULT 'initiated',
    duration_seconds FLOAT DEFAULT 0.0,
    duration_minutes FLOAT GENERATED ALWAYS AS (duration_seconds / 60.0) STORED,
    
    -- Transcript and analysis
    transcript TEXT,
    summary TEXT,
    sentiment VARCHAR(50),
    key_points JSONB,
    
    -- Caller information
    caller_phone VARCHAR(50),
    caller_name VARCHAR(255),
    caller_metadata JSONB,
    
    -- Recording
    recording_url VARCHAR(500),
    
    -- CRM sync (legacy - now use integrations)
    crm_synced BOOLEAN DEFAULT FALSE,
    crm_record_id VARCHAR(255),
    crm_response JSONB,
    
    -- Cost tracking
    cost_usd FLOAT DEFAULT 0.0,
    
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

CREATE TABLE transactions (
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

CREATE TABLE invoices (
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
CREATE INDEX idx_invoices_invoice_number ON invoices(invoice_number);

-- ===================================================================
-- USAGE RECORDS TABLE
-- ===================================================================

CREATE TABLE usage_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES voice_agents(id) ON DELETE SET NULL,
    
    -- Usage details
    date DATE NOT NULL,
    minutes_used FLOAT DEFAULT 0.0,
    calls_count INTEGER DEFAULT 0,
    cost_usd FLOAT DEFAULT 0.0,
    
    -- Metadata
    metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_usage_user ON usage_records(user_id);
CREATE INDEX idx_usage_agent ON usage_records(agent_id);
CREATE INDEX idx_usage_date ON usage_records(date);
CREATE INDEX idx_usage_user_date ON usage_records(user_id, date DESC);

-- ===================================================================
-- SECURITY TABLES
-- ===================================================================

CREATE TABLE domain_allowlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ip_allowlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip_address VARCHAR(45) NOT NULL,  -- IPv6 max length
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE security_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    event_description TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_domain_allowlists_user ON domain_allowlists(user_id);
CREATE INDEX idx_ip_allowlists_user ON ip_allowlists(user_id);
CREATE INDEX idx_security_logs_user ON security_logs(user_id);
CREATE INDEX idx_security_logs_event ON security_logs(event_type);
CREATE INDEX idx_security_logs_created ON security_logs(created_at DESC);

-- ===================================================================
-- SUPPORT TABLES
-- ===================================================================

CREATE TABLE support_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Ticket information
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    category ticket_category NOT NULL,
    status ticket_status DEFAULT 'open',
    priority ticket_priority DEFAULT 'medium',
    
    -- Resolution
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ticket_responses (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Response data
    message TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_tickets_user ON support_tickets(user_id);
CREATE INDEX idx_tickets_status ON support_tickets(status);
CREATE INDEX idx_tickets_category ON support_tickets(category);
CREATE INDEX idx_tickets_created ON support_tickets(created_at DESC);
CREATE INDEX idx_ticket_responses_ticket ON ticket_responses(ticket_id);

-- ===================================================================
-- FUNCTIONS
-- ===================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate call duration (optional - can be computed in application)
CREATE OR REPLACE FUNCTION calculate_call_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ended_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at));
        -- cost calculation can be done here or in application
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old calls (optional maintenance)
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
-- TRIGGERS
-- ===================================================================

-- Apply triggers to tables with updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_voice_agents_updated_at 
    BEFORE UPDATE ON voice_agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integrations_updated_at 
    BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_support_tickets_updated_at 
    BEFORE UPDATE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Optional trigger for auto-calculating call duration
-- Uncomment if you want automatic duration calculation
-- CREATE TRIGGER calculate_call_duration_trigger
--     BEFORE INSERT OR UPDATE ON calls
--     FOR EACH ROW
--     EXECUTE FUNCTION calculate_call_duration();

-- ===================================================================
-- VIEWS
-- ===================================================================

-- Call statistics view
CREATE VIEW call_statistics AS
SELECT 
    u.id as user_id,
    u.email,
    COUNT(c.id) as total_calls,
    SUM(c.duration_minutes) as total_minutes,
    AVG(c.duration_minutes) as avg_call_duration,
    SUM(c.cost_usd) as total_cost,
    COUNT(CASE WHEN c.status = 'completed' THEN 1 END) as completed_calls,
    COUNT(CASE WHEN c.status = 'failed' THEN 1 END) as failed_calls
FROM users u
LEFT JOIN calls c ON u.id = c.user_id
GROUP BY u.id, u.email;

-- Agent performance view
CREATE VIEW agent_performance AS
SELECT 
    va.id as agent_id,
    va.name as agent_name,
    va.user_id,
    COUNT(c.id) as total_calls,
    SUM(c.duration_minutes) as total_minutes,
    AVG(c.duration_minutes) as avg_call_duration,
    COUNT(CASE WHEN c.status = 'completed' THEN 1 END) as completed_calls,
    COUNT(CASE WHEN c.sentiment = 'positive' THEN 1 END) as positive_calls,
    COUNT(CASE WHEN c.sentiment = 'negative' THEN 1 END) as negative_calls,
    COUNT(CASE WHEN c.sentiment = 'neutral' THEN 1 END) as neutral_calls
FROM voice_agents va
LEFT JOIN calls c ON va.id = c.agent_id
GROUP BY va.id, va.name, va.user_id;

-- ===================================================================
-- COMMENTS
-- ===================================================================

COMMENT ON TABLE users IS 'Platform users with authentication and subscription info';
COMMENT ON TABLE api_keys IS 'API keys for programmatic access';
COMMENT ON TABLE voice_agents IS 'Voice agent configurations';
COMMENT ON TABLE integrations IS 'Stores user integrations with third-party services (Calendar, Email, CRM, Database, Accounting, etc.)';
COMMENT ON TABLE calls IS 'Call history and analytics';
COMMENT ON TABLE call_messages IS 'Individual messages within calls';
COMMENT ON TABLE transactions IS 'Payment transactions';
COMMENT ON TABLE invoices IS 'Billing invoices';
COMMENT ON TABLE usage_records IS 'Usage tracking records';
COMMENT ON TABLE domain_allowlists IS 'Domain-based security allowlists';
COMMENT ON TABLE ip_allowlists IS 'IP address-based security allowlists';
COMMENT ON TABLE security_logs IS 'Security event logs';
COMMENT ON TABLE support_tickets IS 'Customer support tickets';
COMMENT ON TABLE ticket_responses IS 'Responses to support tickets';

COMMENT ON COLUMN integrations.integration_type IS 'Type: calendar, email, contact_management, database, crm, accounting, other';
COMMENT ON COLUMN integrations.provider IS 'Provider: google_calendar, gmail, hubspot, postgresql, quickbooks, webhook, etc.';
COMMENT ON COLUMN integrations.config IS 'Encrypted credentials and configuration (should be encrypted in production)';
COMMENT ON COLUMN integrations.integration_metadata IS 'Additional provider-specific metadata (JSON)';

-- ===================================================================
-- SUPABASE ROW LEVEL SECURITY (RLS) - OPTIONAL
-- ===================================================================

-- Uncomment the following section if using Supabase and want RLS policies
-- Note: Requires Supabase auth.uid() function to be available

/*
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

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

-- Integrations policies
CREATE POLICY integrations_select_own ON integrations
    FOR SELECT
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY integrations_insert_own ON integrations
    FOR INSERT
    WITH CHECK (user_id = (auth.uid()::text)::integer);

CREATE POLICY integrations_update_own ON integrations
    FOR UPDATE
    USING (user_id = (auth.uid()::text)::integer);

CREATE POLICY integrations_delete_own ON integrations
    FOR DELETE
    USING (user_id = (auth.uid()::text)::integer);
*/

-- ===================================================================
-- COMPLETION
-- ===================================================================

DO $$
BEGIN
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'VoiceAgent SaaS - Complete Database Schema Created Successfully!';
    RAISE NOTICE '====================================================================';
    RAISE NOTICE 'Tables Created:';
    RAISE NOTICE '  - users';
    RAISE NOTICE '  - api_keys';
    RAISE NOTICE '  - voice_agents';
    RAISE NOTICE '  - integrations';
    RAISE NOTICE '  - calls';
    RAISE NOTICE '  - call_messages';
    RAISE NOTICE '  - transactions';
    RAISE NOTICE '  - invoices';
    RAISE NOTICE '  - usage_records';
    RAISE NOTICE '  - domain_allowlists';
    RAISE NOTICE '  - ip_allowlists';
    RAISE NOTICE '  - security_logs';
    RAISE NOTICE '  - support_tickets';
    RAISE NOTICE '  - ticket_responses';
    RAISE NOTICE 'Views: call_statistics, agent_performance';
    RAISE NOTICE 'Triggers: Auto-update updated_at columns';
    RAISE NOTICE '====================================================================';
END $$;

