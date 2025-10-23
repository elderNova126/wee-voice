-- Zadarma Integration Database Migration
-- Run this SQL to add Zadarma-related fields to existing database

-- Add Zadarma fields to calls table
ALTER TABLE calls ADD COLUMN IF NOT EXISTS zadarma_call_id VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS direction VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS disposition VARCHAR;
ALTER TABLE calls ADD COLUMN IF NOT EXISTS duration INTEGER DEFAULT 0;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_calls_zadarma_call_id ON calls(zadarma_call_id);

-- Make session_id nullable for phone calls (optional, only if using PostgreSQL)
-- For SQLite, this is already handled in the model
-- ALTER TABLE calls ALTER COLUMN session_id DROP NOT NULL;

-- Update existing records to have default values
UPDATE calls SET direction = 'inbound' WHERE direction IS NULL;
UPDATE calls SET duration = CAST(duration_seconds AS INTEGER) WHERE duration IS NULL OR duration = 0;

-- Verify changes
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'calls' 
    AND column_name IN ('zadarma_call_id', 'direction', 'disposition', 'duration')
ORDER BY ordinal_position;

-- Create phone_numbers table if not exists
CREATE TABLE IF NOT EXISTS phone_numbers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    agent_id INTEGER REFERENCES voice_agents(id),
    phone_number VARCHAR UNIQUE NOT NULL,
    country_code VARCHAR NOT NULL,
    number_type VARCHAR NOT NULL,
    zadarma_number_id VARCHAR,
    zadarma_status VARCHAR,
    zadarma_config JSONB,
    status VARCHAR DEFAULT 'pending',
    status_message TEXT,
    monthly_cost VARCHAR DEFAULT '0.00',
    per_minute_cost VARCHAR DEFAULT '0.00',
    business_name VARCHAR,
    business_type VARCHAR,
    business_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_phone_numbers_phone ON phone_numbers(phone_number);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_user ON phone_numbers(user_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent ON phone_numbers(agent_id);

-- Create verification_documents table if not exists
CREATE TABLE IF NOT EXISTS verification_documents (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER NOT NULL REFERENCES phone_numbers(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    document_type VARCHAR NOT NULL,
    document_name VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    file_url VARCHAR,
    file_size INTEGER,
    mime_type VARCHAR,
    status VARCHAR DEFAULT 'received',
    reviewed_by VARCHAR,
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    notes TEXT,
    document_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verification_docs_phone ON verification_documents(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_verification_docs_user ON verification_documents(user_id);

-- Create callback_requests table if not exists
CREATE TABLE IF NOT EXISTS callback_requests (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES calls(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    agent_id INTEGER NOT NULL REFERENCES voice_agents(id),
    reason TEXT NOT NULL,
    priority VARCHAR DEFAULT 'normal',
    caller_name VARCHAR,
    caller_phone VARCHAR,
    caller_email VARCHAR,
    preferred_callback_time VARCHAR,
    status VARCHAR DEFAULT 'pending',
    assigned_to VARCHAR,
    notes TEXT,
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contacted_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_callback_requests_call ON callback_requests(call_id);
CREATE INDEX IF NOT EXISTS idx_callback_requests_user ON callback_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_callback_requests_status ON callback_requests(status);

-- Add phone_number relationship to voice_agents if needed
-- ALTER TABLE voice_agents ADD COLUMN IF NOT EXISTS phone_number_id INTEGER REFERENCES phone_numbers(id);

COMMIT;

-- Verification queries
SELECT 'Calls table updated' AS status, COUNT(*) AS total_calls FROM calls;
SELECT 'Phone numbers table ready' AS status, COUNT(*) AS total_numbers FROM phone_numbers;
SELECT 'Verification docs table ready' AS status, COUNT(*) AS total_docs FROM verification_documents;
SELECT 'Callback requests table ready' AS status, COUNT(*) AS total_callbacks FROM callback_requests;

