-- ===================================================================
-- VoiceAgent SaaS - Complete Database Schema
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
DROP TABLE IF EXISTS callback_requests CASCADE;
DROP TABLE IF EXISTS verification_documents CASCADE;
DROP TABLE IF EXISTS phone_numbers CASCADE;
DROP TABLE IF EXISTS call_messages CASCADE;
DROP TABLE IF EXISTS calls CASCADE;
DROP TABLE IF EXISTS document_chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
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
    is_approved BOOLEAN DEFAULT FALSE,  -- Admin approval required
    
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
    source_type VARCHAR DEFAULT 'pdf',  -- pdf, website, text
    source_url VARCHAR,  -- For websites
    
    -- Processing status
    status VARCHAR DEFAULT 'pending',  -- pending, processing, completed, failed
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
    embedding JSONB,  -- Vector embedding as JSON array
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
    
    -- Call metadata
    session_id VARCHAR(255) UNIQUE,  -- Nullable for phone calls
    status call_status DEFAULT 'initiated',
    
    -- Duration and cost
    duration_seconds FLOAT DEFAULT 0.0,
    duration_minutes FLOAT DEFAULT 0.0,
    duration INTEGER DEFAULT 0,  -- Integer version for compatibility
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
    
    -- Zadarma integration
    zadarma_call_id VARCHAR(255),
    direction VARCHAR(50),  -- inbound, outbound
    disposition VARCHAR(50),  -- answered, no_answer, busy, failed
    
    -- Callback and email
    callback_requested BOOLEAN DEFAULT FALSE,
    callback_reason TEXT,
    summary_email_sent BOOLEAN DEFAULT FALSE,
    summary_email_sent_at TIMESTAMP,
    
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
    number_type VARCHAR(20) NOT NULL,  -- "local", "toll-free", "mobile"
    
    -- Integration
    zadarma_number_id VARCHAR(255),
    zadarma_status VARCHAR(50),
    zadarma_config JSONB,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, documents_submitted, under_review, approved, rejected, active, suspended, cancelled
    status_message TEXT,
    
    -- Pricing
    monthly_cost VARCHAR(20) DEFAULT '0.00',
    per_minute_cost VARCHAR(20) DEFAULT '0.00',
    
    -- Business information
    business_name VARCHAR(255),
    business_type VARCHAR(50),  -- "company" or "individual"
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
    document_type VARCHAR(50) NOT NULL,  -- company_registration, proof_of_address, passport, national_id, other
    document_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500),
    file_size INTEGER,
    mime_type VARCHAR(100),
    
    -- Verification status
    status VARCHAR(50) DEFAULT 'received',  -- pending, received, in_review, accepted, rejected
    
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
    priority VARCHAR(20) DEFAULT 'normal',  -- urgent, high, normal, low
    
    -- Caller information
    caller_name VARCHAR(255),
    caller_phone VARCHAR(50),
    caller_email VARCHAR(255),
    preferred_callback_time VARCHAR(255),
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, contacted, completed, cancelled
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

CREATE TABLE ticket_responses (
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
DROP TRIGGER IF EXISTS trigger_update_documents_updated_at ON documents;
DROP TRIGGER IF EXISTS update_phone_numbers_updated_at ON phone_numbers;
DROP TRIGGER IF EXISTS update_verification_documents_updated_at ON verification_documents;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS calculate_call_duration() CASCADE;
DROP FUNCTION IF EXISTS update_documents_updated_at() CASCADE;
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

-- Trigger for phone_numbers
CREATE TRIGGER update_phone_numbers_updated_at
    BEFORE UPDATE ON phone_numbers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for verification_documents
CREATE TRIGGER update_verification_documents_updated_at
    BEFORE UPDATE ON verification_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update documents timestamp
CREATE OR REPLACE FUNCTION update_documents_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for documents
CREATE TRIGGER trigger_update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_documents_updated_at();

-- Function to calculate call duration
CREATE OR REPLACE FUNCTION calculate_call_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.ended_at IS NOT NULL AND NEW.started_at IS NOT NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at));
        NEW.duration_minutes = NEW.duration_seconds / 60.0;
        NEW.duration = CAST(NEW.duration_seconds AS INTEGER);
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
-- COMMENTS FOR DOCUMENTATION
-- ===================================================================

COMMENT ON TABLE users IS 'Platform users with authentication and subscription info';
COMMENT ON TABLE api_keys IS 'API keys for programmatic access';
COMMENT ON TABLE voice_agents IS 'Voice agent configurations with model settings (model_name default: gemini-2.5-flash-native-audio-preview-09-2025)';
COMMENT ON TABLE calls IS 'Call history and analytics';
COMMENT ON TABLE call_messages IS 'Individual messages within calls';
COMMENT ON TABLE documents IS 'Stores RAG knowledge sources (PDFs, websites, text, etc.)';
COMMENT ON TABLE document_chunks IS 'Text chunks from documents with embeddings for semantic search';
COMMENT ON TABLE transactions IS 'Payment transactions and billing history';
COMMENT ON TABLE invoices IS 'Generated invoices for billing periods';
COMMENT ON TABLE usage_records IS 'Detailed usage tracking per call/agent';
COMMENT ON TABLE domain_allowlists IS 'Allowed domains for ChatKit integration';
COMMENT ON TABLE ip_allowlists IS 'IP restrictions for security';
COMMENT ON TABLE security_logs IS 'Security events and audit trail';
COMMENT ON TABLE support_tickets IS 'Support tickets submitted by users';
COMMENT ON TABLE ticket_responses IS 'Responses to support tickets from users or staff';
COMMENT ON TABLE phone_numbers IS 'Phone numbers for voice agents';
COMMENT ON TABLE verification_documents IS 'Documents for phone number verification';
COMMENT ON TABLE callback_requests IS 'Callback requests from callers';
COMMENT ON COLUMN voice_agents.model_name IS 'Gemini model ID (default: gemini-2.5-flash-native-audio-preview-09-2025)';
COMMENT ON COLUMN voice_agents.voice_gender IS 'Voice gender/type: male (Charon), female (Kore), neutral (Puck)';
COMMENT ON COLUMN documents.file_url IS 'Public URL for storage files (null for local storage)';
COMMENT ON COLUMN calls.session_id IS 'Web session ID (nullable for phone calls)';

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
    RAISE NOTICE 'Views: call_statistics, agent_performance';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Model: gemini-2.5-flash-native-audio-preview-09-2025';
    RAISE NOTICE 'Voice Gender: male (Charon), female (Kore), neutral (Puck)';
    RAISE NOTICE 'All migrations included!';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Remember to configure environment variables!';
END $$;

