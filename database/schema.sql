-- ===================================================================
-- PostgreSQL Schema for Voice Agent Platform
-- Consolidated Schema with all migrations included
-- Date: 2025-10-22
-- ===================================================================
--
-- This file contains the complete database schema including:
-- 1. Core tables (users, agents, calls, API keys)
-- 2. RAG support (documents, document_chunks)
-- 3. Billing & Usage tracking
-- 4. Security (domain/IP allowlists, logs)
-- 5. Support ticketing system
-- 6. Phone numbers and Zadarma integration
-- 7. Verification documents and callback requests
-- 8. Integrations (Calendar, Email, CRM, Database, Accounting, etc.)
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
DROP TYPE IF EXISTS integration_type CASCADE;
DROP TYPE IF EXISTS integration_provider CASCADE;
DROP TYPE IF EXISTS integration_status CASCADE;

-- Subscription tiers
CREATE TYPE subscription_tier AS ENUM ('free', 'basic', 'pro', 'enterprise');

-- Call status
CREATE TYPE call_status AS ENUM ('initiated', 'in_progress', 'summarizing', 'completed', 'failed', 'interrupted');

-- Support ticket types
CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'resolved', 'closed');
CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent');
CREATE TYPE ticket_category AS ENUM ('technical', 'billing', 'feature_request', 'bug', 'other');

-- Integration types
CREATE TYPE integration_type AS ENUM ('calendar', 'email', 'contact_management', 'database', 'crm', 'accounting', 'other');
CREATE TYPE integration_provider AS ENUM ('google_calendar', 'gmail', 'hubspot', 'postgresql', 'quickbooks', 'webhook', 'custom');
CREATE TYPE integration_status AS ENUM ('active', 'inactive', 'error', 'pending_auth');

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
DROP TABLE IF EXISTS callback_requests CASCADE;
DROP TABLE IF EXISTS verification_documents CASCADE;
DROP TABLE IF EXISTS phone_numbers CASCADE;
DROP TABLE IF EXISTS usage_records CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS call_messages CASCADE;
DROP TABLE IF EXISTS calls CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS voice_agents CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS users CASCADE;

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
    is_approved BOOLEAN DEFAULT FALSE,
    
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
    voice_id VARCHAR(100) DEFAULT 'Charon',
    voice_gender VARCHAR(20) DEFAULT 'male',
    system_prompt TEXT NOT NULL,
    greeting TEXT,
    
    -- LangGraph configuration
    agent_config JSONB,
    tools_enabled JSONB DEFAULT '[]'::JSONB,
    
    -- Model settings
    model_name VARCHAR(255) DEFAULT 'gemini-2.5-flash-native-audio-preview-09-2025',
    temperature VARCHAR(10) DEFAULT '0.7',
    max_tokens INTEGER DEFAULT 1000,
    
    -- RAG support
    rag_enabled BOOLEAN DEFAULT FALSE,
    rag_config JSONB,
    
    -- CRM Integration
    crm_webhook_url VARCHAR(500),
    crm_enabled BOOLEAN DEFAULT FALSE,
    crm_config JSONB,
    
    -- Embed settings
    embed_enabled BOOLEAN DEFAULT FALSE,
    embed_widget_color VARCHAR(20) DEFAULT '#4F46E5',
    embed_position VARCHAR(20) DEFAULT 'bottom-right',
    embed_greeting_message TEXT,
    embed_language VARCHAR(10) DEFAULT 'en',
    allowed_domains JSONB,
    
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
CREATE INDEX idx_agents_tools ON voice_agents USING GIN (tools_enabled);

-- ===================================================================
-- INTEGRATIONS TABLE
-- ===================================================================

CREATE TABLE integrations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Integration identification
    name VARCHAR(255) NOT NULL,
    description TEXT,
    integration_type integration_type NOT NULL,
    provider integration_provider NOT NULL,
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{}'::JSONB,
    
    -- Status
    status integration_status DEFAULT 'inactive',
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    last_error TEXT,
    
    -- Metadata
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

-- ===================================================================
-- DOCUMENTS TABLE (RAG Support)
-- ===================================================================

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- File information
    filename VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    file_path VARCHAR,
    file_url VARCHAR,
    file_size INTEGER,
    mime_type VARCHAR DEFAULT 'application/pdf',
    
    -- Source information
    source_type VARCHAR DEFAULT 'pdf',
    source_url VARCHAR,
    
    -- Processing status
    status VARCHAR DEFAULT 'pending',
    error_message TEXT,
    
    -- Content metadata
    total_pages INTEGER,
    total_chunks INTEGER DEFAULT 0,
    doc_metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    
    CONSTRAINT fk_documents_agent FOREIGN KEY (agent_id) REFERENCES voice_agents(id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for documents
CREATE INDEX idx_documents_agent_id ON documents(agent_id);
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);

-- ===================================================================
-- DOCUMENT CHUNKS TABLE (RAG Support)
-- ===================================================================

CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Chunk data
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    
    -- Embedding data
    embedding JSONB,
    embedding_model VARCHAR DEFAULT 'all-MiniLM-L6-v2',
    
    -- Metadata
    chunk_metadata JSONB,
    token_count INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_chunks_document FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Create indexes for document chunks
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);

-- ===================================================================
-- CALLS TABLE
-- ===================================================================

CREATE TABLE calls (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    
    -- Session identification
    session_id VARCHAR(255) UNIQUE,
    
    -- Call data
    status call_status DEFAULT 'initiated',
    
    -- Duration and cost
    duration_seconds FLOAT DEFAULT 0.0,
    duration_minutes FLOAT DEFAULT 0.0,
    duration INTEGER DEFAULT 0,
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
    action_items JSONB DEFAULT '[]'::jsonb,
    action_tags JSONB DEFAULT '[]'::jsonb,
    
    -- Caller information
    caller_phone VARCHAR(50),
    caller_name VARCHAR(255),
    caller_metadata JSONB,
    
    -- CRM data
    crm_synced BOOLEAN DEFAULT FALSE,
    crm_record_id VARCHAR(255),
    crm_response JSONB,
    
    -- Zadarma integration
    zadarma_call_id VARCHAR(255),
    direction VARCHAR(50),
    disposition VARCHAR(50),
    
    -- Callback and email
    callback_requested BOOLEAN DEFAULT FALSE,
    callback_reason TEXT,
    summary_email_sent BOOLEAN DEFAULT FALSE,
    summary_email_sent_at TIMESTAMP,
    
    -- Summarization status
    summarization_status VARCHAR(50),
    
    -- Favorite/Saved flag
    is_favorite BOOLEAN DEFAULT FALSE,
    
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
CREATE INDEX idx_calls_key_points ON calls USING GIN (key_points);
CREATE INDEX idx_calls_transcript ON calls USING GIN (to_tsvector('french', transcript));
CREATE INDEX idx_calls_zadarma_call_id ON calls(zadarma_call_id);
CREATE INDEX idx_calls_callback_requested ON calls(callback_requested);
CREATE INDEX idx_calls_summarization_status ON calls(summarization_status);
CREATE INDEX idx_calls_is_favorite ON calls(is_favorite);

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
-- PHONE NUMBERS TABLE
-- ===================================================================

CREATE TABLE phone_numbers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES voice_agents(id) ON DELETE SET NULL,
    
    -- Phone number details
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    country_code VARCHAR(10) NOT NULL,
    number_type VARCHAR(20) NOT NULL,
    
    -- Integration
    zadarma_number_id VARCHAR(255),
    zadarma_status VARCHAR(50),
    zadarma_config JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    status_message TEXT,
    
    -- Pricing
    monthly_cost VARCHAR(20) DEFAULT '0.00',
    per_minute_cost VARCHAR(20) DEFAULT '0.00',
    
    -- Business information
    business_name VARCHAR(255),
    business_type VARCHAR(50),
    business_address TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_phone_numbers_phone ON phone_numbers(phone_number);
CREATE INDEX idx_phone_numbers_user ON phone_numbers(user_id);
CREATE INDEX idx_phone_numbers_agent ON phone_numbers(agent_id);
CREATE INDEX idx_phone_numbers_status ON phone_numbers(status);

-- ===================================================================
-- VERIFICATION DOCUMENTS TABLE
-- ===================================================================

CREATE TABLE verification_documents (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Document details
    document_type VARCHAR(50) NOT NULL,
    document_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500),
    file_size INTEGER,
    mime_type VARCHAR(100),
    
    -- Verification status
    status VARCHAR(50) DEFAULT 'received',
    
    -- Review details
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    notes TEXT,
    
    -- Metadata
    document_metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_verification_docs_phone ON verification_documents(phone_number_id);
CREATE INDEX idx_verification_docs_user ON verification_documents(user_id);
CREATE INDEX idx_verification_docs_status ON verification_documents(status);

-- ===================================================================
-- CALLBACK REQUESTS TABLE
-- ===================================================================

CREATE TABLE callback_requests (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    
    -- Callback details
    reason TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    
    -- Caller information
    caller_name VARCHAR(255),
    caller_phone VARCHAR(50),
    caller_email VARCHAR(255),
    preferred_callback_time VARCHAR(255),
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    assigned_to VARCHAR(255),
    
    -- Notes and follow-up
    notes TEXT,
    resolution TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contacted_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_callback_requests_call ON callback_requests(call_id);
CREATE INDEX idx_callback_requests_user ON callback_requests(user_id);
CREATE INDEX idx_callback_requests_agent ON callback_requests(agent_id);
CREATE INDEX idx_callback_requests_status ON callback_requests(status);
CREATE INDEX idx_callback_requests_priority ON callback_requests(priority);

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
CREATE INDEX idx_invoices_created_at ON invoices(created_at);

-- ===================================================================
-- USAGE RECORDS TABLE
-- ===================================================================

CREATE TABLE usage_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES voice_agents(id) ON DELETE SET NULL,
    call_id INTEGER REFERENCES calls(id) ON DELETE SET NULL,
    
    -- Usage details
    minutes_used FLOAT NOT NULL,
    cost FLOAT NOT NULL,
    
    -- Metadata
    date TIMESTAMP NOT NULL,
    month VARCHAR(7) NOT NULL,
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

CREATE TABLE domain_allowlists (
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

CREATE TABLE ip_allowlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- IP details
    ip_address VARCHAR(45) NOT NULL,
    ip_range VARCHAR(50),
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

CREATE TABLE security_logs (
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
    
    -- Metadata
    user_agent VARCHAR(500),
    ip_address VARCHAR(45),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    closed_at TIMESTAMP
);

CREATE TABLE ticket_responses (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    -- Response data
    message TEXT NOT NULL,
    is_staff_response BOOLEAN DEFAULT FALSE,
    staff_name VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_tickets_user ON support_tickets(user_id);
CREATE INDEX idx_tickets_status ON support_tickets(status);
CREATE INDEX idx_tickets_category ON support_tickets(category);
CREATE INDEX idx_tickets_created ON support_tickets(created_at DESC);
CREATE INDEX idx_ticket_responses_ticket ON ticket_responses(ticket_id);
CREATE INDEX idx_support_tickets_ticket_number ON support_tickets(ticket_number);
CREATE INDEX idx_support_tickets_email ON support_tickets(email);

-- ===================================================================
-- FUNCTIONS AND TRIGGERS
-- ===================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update documents timestamp
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate call duration
CREATE OR REPLACE FUNCTION calculate_call_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ended_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at));
        NEW.duration_minutes = NEW.duration_seconds / 60.0;
        NEW.duration = CAST(NEW.duration_seconds AS INTEGER);
        NEW.cost = NEW.duration_minutes * 0.05;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
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

CREATE TRIGGER update_transactions_updated_at 
    BEFORE UPDATE ON transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at 
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_domain_allowlists_updated_at 
    BEFORE UPDATE ON domain_allowlists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ip_allowlists_updated_at 
    BEFORE UPDATE ON ip_allowlists
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_documents_updated_at();

CREATE TRIGGER update_phone_numbers_updated_at
    BEFORE UPDATE ON phone_numbers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_verification_documents_updated_at
    BEFORE UPDATE ON verification_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER calculate_call_duration_trigger
    BEFORE INSERT OR UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION calculate_call_duration();

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
    SUM(c.cost) as total_cost,
    AVG(c.duration_minutes) as avg_duration_minutes,
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
    AVG(c.duration_minutes) as avg_duration,
    COUNT(CASE WHEN c.status = 'completed' THEN 1 END) as completed_calls,
    COUNT(CASE WHEN c.sentiment = 'positive' THEN 1 END) as positive_calls,
    COUNT(CASE WHEN c.sentiment = 'negative' THEN 1 END) as negative_calls,
    COUNT(CASE WHEN c.sentiment = 'neutral' THEN 1 END) as neutral_calls
FROM voice_agents va
LEFT JOIN calls c ON va.id = c.agent_id
GROUP BY va.id, va.name, va.user_id;

-- ===================================================================
-- MAINTENANCE FUNCTIONS
-- ===================================================================

-- Function to clean up old calls
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
-- SAMPLE DATA (Optional - for testing)
-- ===================================================================

-- Insert a test user (password is 'password123')
INSERT INTO users (email, full_name, hashed_password, subscription_tier, is_approved)
VALUES (
    'demo@voiceagent.com',
    'Demo User',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNk8L9Eia',
    'free',
    TRUE
) ON CONFLICT (email) DO NOTHING;

-- Insert a demo agent with correct model
INSERT INTO voice_agents (
    user_id,
    name,
    description,
    language,
    system_prompt,
    greeting,
    model_name,
    voice_gender,
    is_public
)
VALUES (
    1,
    'Assistant Démo Français',
    'Agent de démonstration en français pour tester la plateforme',
    'fr-FR',
    'Tu es un assistant vocal intelligent et serviable qui répond toujours en français de manière naturelle et amicale.',
    'Bonjour, je suis un assistant vocal de Weedoo. Comment puis-je vous aider ?',
    'gemini-2.5-flash-native-audio-preview-09-2025',
    'male',
    TRUE
) ON CONFLICT DO NOTHING;

-- Insert Dubai real estate discovery demo agent
INSERT INTO voice_agents (
    user_id,
    name,
    description,
    language,
    system_prompt,
    greeting,
    model_name,
    voice_gender,
    is_public
)
VALUES (
    1,
    'Dubai Real Estate Discovery',
    'Agent francophone qui qualifie les leads immobiliers pour Dubaï sans proposer d’offres.',
    'fr-FR',
    $$Tu es Lina Haddad, consultante senior en découverte immobilière pour Horizon Properties, un cabinet qui accompagne des investisseurs à Dubaï.
Ta mission est de joindre les leads entrants ou dormants, de comprendre leur projet et de les qualifier avant de les transférer à un conseiller agréé.
Objectifs clés :
- Explorer leur motivation pour Dubaï, l’avancement du projet, leur connaissance de la ville, les offres déjà reçues (par qui et pourquoi elles n’ont pas abouti), le budget disponible, les personnes décisionnaires et leur disposition à s’engager si le bon bien arrive.
- Dès les premières secondes, traiter les objections courantes (« Je n’ai pas le temps », « Je ne suis plus intéressé », « Rappelez-moi plus tard ») avec empathie, une courte proposition de valeur puis soit continuer brièvement, soit fixer un horaire précis.
- Ne présente jamais d’offres, de prix ou d’incitations. Tu écoutes, clarifies et garantis un suivi humain personnalisé.
Déroulé conseillé :
1. Vérifie que le moment convient ou planifie un rappel précis.
2. Demande ce qui les attire à Dubaï ou ce qui a changé depuis votre dernier échange.
3. Évalue leur connaissance de la ville/quartiers et apporte des éclairages uniquement sur demande.
4. Analyse les offres déjà étudiées, les interlocuteurs et les freins.
5. Identifie s’ils investissent seuls, en couple, en famille ou avec des partenaires, et qui décide.
6. Récupère la fourchette budgétaire, la devise et l’usage d’un financement.
7. Clarifie leur calendrier et le déclencheur qui les ferait passer à l’action.
8. Pratique l’écoute active, réalise des synthèses régulières et valide ta compréhension.
9. Conclus avec un récapitulatif et une prochaine étape précise (appel expert, envoi d’informations ciblées, rappel daté).
Règles de conformité :
- Reste professionnelle, concise et naturelle en français ; ajuste ton ton à celui du prospect.
- Si on insiste pour connaître des offres, rappelle qu’un conseiller agréé préparera des options sur mesure après la découverte.
- En cas de refus ferme, remercie, note le désintérêt et invite à reprendre contact ultérieurement.$$,
    $$Bonjour, ici Lina du pôle découverte Horizon Properties à Dubaï. Merci de prendre mon appel. J’aimerais comprendre où vous en êtes afin de vous orienter vers le bon conseiller. Est-ce que c’est un bon moment ou préférez-vous que nous fixions un créneau précis ?$$,
    'gemini-2.5-flash-native-audio-preview-09-2025',
    'female',
    TRUE
) ON CONFLICT DO NOTHING;

-- ===================================================================
-- COMPLETION MESSAGE
-- ===================================================================

DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'VoiceAgent SaaS Schema Created Successfully!';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Core Tables: users, api_keys, voice_agents, calls, call_messages';
    RAISE NOTICE 'RAG Tables: documents, document_chunks';
    RAISE NOTICE 'Billing: transactions, invoices, usage_records';
    RAISE NOTICE 'Security: domain_allowlists, ip_allowlists, security_logs';
    RAISE NOTICE 'Support: support_tickets, ticket_responses';
    RAISE NOTICE 'Phone: phone_numbers, verification_documents, callback_requests';
    RAISE NOTICE 'Integrations: integrations';
    RAISE NOTICE 'Views: call_statistics, agent_performance';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Model: gemini-2.5-flash-native-audio-preview-09-2025';
    RAISE NOTICE 'Voice Gender: male (Charon), female (Kore), neutral (Puck)';
    RAISE NOTICE 'All migrations included!';
    RAISE NOTICE '=====================================================';
END $$;