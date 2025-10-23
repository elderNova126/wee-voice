-- Zadarma Integration Migration for Supabase
-- Run this in Supabase SQL Editor to add Zadarma phone call support

-- ============================================
-- 1. Add Zadarma columns to calls table
-- ============================================

-- Add new columns
ALTER TABLE calls ADD COLUMN IF NOT EXISTS zadarma_call_id VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS direction VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS disposition VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS duration INTEGER DEFAULT 0;

-- Make session_id nullable (for phone calls that don't have a web session)
ALTER TABLE calls ALTER COLUMN session_id DROP NOT NULL;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_calls_zadarma_call_id ON calls(zadarma_call_id);

-- ============================================
-- 2. Create phone_numbers table
-- ============================================

CREATE TABLE IF NOT EXISTS phone_numbers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES voice_agents(id) ON DELETE SET NULL,
    
    -- Phone number details
    phone_number VARCHAR UNIQUE NOT NULL,
    country_code VARCHAR NOT NULL,
    number_type VARCHAR NOT NULL,
    
    -- Zadarma integration
    zadarma_number_id VARCHAR,
    zadarma_status VARCHAR,
    zadarma_config JSONB,
    
    -- Status
    status VARCHAR DEFAULT 'pending',
    status_message TEXT,
    
    -- Pricing
    monthly_cost VARCHAR DEFAULT '0.00',
    per_minute_cost VARCHAR DEFAULT '0.00',
    
    -- Business information
    business_name VARCHAR,
    business_type VARCHAR,
    business_address TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_phone_numbers_phone ON phone_numbers(phone_number);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_user ON phone_numbers(user_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent ON phone_numbers(agent_id);

-- ============================================
-- 3. Create verification_documents table
-- ============================================

CREATE TABLE IF NOT EXISTS verification_documents (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Document details
    document_type VARCHAR NOT NULL,
    document_name VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    file_url VARCHAR,
    file_size INTEGER,
    mime_type VARCHAR,
    
    -- Verification status
    status VARCHAR DEFAULT 'received',
    
    -- Review details
    reviewed_by VARCHAR,
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
CREATE INDEX IF NOT EXISTS idx_verification_docs_phone ON verification_documents(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_verification_docs_user ON verification_documents(user_id);

-- ============================================
-- 4. Create callback_requests table
-- ============================================

CREATE TABLE IF NOT EXISTS callback_requests (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id) ON DELETE CASCADE,
    
    -- Callback details
    reason TEXT NOT NULL,
    priority VARCHAR DEFAULT 'normal',
    
    -- Caller information
    caller_name VARCHAR,
    caller_phone VARCHAR,
    caller_email VARCHAR,
    preferred_callback_time VARCHAR,
    
    -- Status
    status VARCHAR DEFAULT 'pending',
    assigned_to VARCHAR,
    
    -- Notes and follow-up
    notes TEXT,
    resolution TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contacted_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_callback_requests_call ON callback_requests(call_id);
CREATE INDEX IF NOT EXISTS idx_callback_requests_user ON callback_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_callback_requests_status ON callback_requests(status);

-- ============================================
-- 5. Update existing data (if needed)
-- ============================================

-- Set default direction for existing calls
UPDATE calls 
SET direction = 'inbound' 
WHERE direction IS NULL;

-- Copy duration_seconds to new duration field
UPDATE calls 
SET duration = CAST(duration_seconds AS INTEGER) 
WHERE duration IS NULL OR duration = 0;

-- ============================================
-- Verification: Check the changes
-- ============================================

-- Verify calls table columns
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'calls' 
  AND column_name IN ('zadarma_call_id', 'direction', 'disposition', 'duration')
ORDER BY column_name;

-- Verify new tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('phone_numbers', 'verification_documents', 'callback_requests')
ORDER BY table_name;

-- Display summary
SELECT 
    'Migration Complete!' as message,
    (SELECT COUNT(*) FROM calls) as total_calls,
    (SELECT COUNT(*) FROM phone_numbers) as total_phone_numbers,
    (SELECT COUNT(*) FROM verification_documents) as total_documents,
    (SELECT COUNT(*) FROM callback_requests) as total_callbacks;

