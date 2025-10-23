-- WeeVoice Platform Database Migration - PostgreSQL Version
-- Run this SQL script in Supabase SQL Editor to add new tables

-- =====================================================
-- 1. Phone Numbers Table
-- =====================================================
CREATE TABLE IF NOT EXISTS phone_numbers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    agent_id INTEGER,
    
    -- Phone number details
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    country_code VARCHAR(10) NOT NULL,
    number_type VARCHAR(20) NOT NULL,  -- "local", "toll-free", "mobile"
    
    -- Zadarma integration
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES voice_agents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_phone_numbers_user ON phone_numbers(user_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent ON phone_numbers(agent_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_status ON phone_numbers(status);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_phone_numbers_updated_at BEFORE UPDATE ON phone_numbers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 2. Verification Documents Table
-- =====================================================
CREATE TABLE IF NOT EXISTS verification_documents (
    id SERIAL PRIMARY KEY,
    phone_number_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    
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
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    notes TEXT,
    
    -- Metadata
    document_metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (phone_number_id) REFERENCES phone_numbers(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verification_docs_phone ON verification_documents(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_verification_docs_user ON verification_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_verification_docs_status ON verification_documents(status);

CREATE TRIGGER update_verification_documents_updated_at BEFORE UPDATE ON verification_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 3. Callback Requests Table
-- =====================================================
CREATE TABLE IF NOT EXISTS callback_requests (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    contacted_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES voice_agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_callbacks_call ON callback_requests(call_id);
CREATE INDEX IF NOT EXISTS idx_callbacks_user ON callback_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_callbacks_agent ON callback_requests(agent_id);
CREATE INDEX IF NOT EXISTS idx_callbacks_status ON callback_requests(status);
CREATE INDEX IF NOT EXISTS idx_callbacks_priority ON callback_requests(priority);

-- =====================================================
-- 4. Update Voice Agents Table (Add Embed Settings)
-- =====================================================
-- Check if columns exist before adding (PostgreSQL doesn't have IF NOT EXISTS for ALTER COLUMN)
DO $$ 
BEGIN
    -- Add embed_enabled if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='voice_agents' AND column_name='embed_enabled') THEN
        ALTER TABLE voice_agents ADD COLUMN embed_enabled BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Add embed_widget_color if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='voice_agents' AND column_name='embed_widget_color') THEN
        ALTER TABLE voice_agents ADD COLUMN embed_widget_color VARCHAR(20) DEFAULT '#4F46E5';
    END IF;
    
    -- Add embed_position if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='voice_agents' AND column_name='embed_position') THEN
        ALTER TABLE voice_agents ADD COLUMN embed_position VARCHAR(20) DEFAULT 'bottom-right';
    END IF;
    
    -- Add embed_greeting_message if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='voice_agents' AND column_name='embed_greeting_message') THEN
        ALTER TABLE voice_agents ADD COLUMN embed_greeting_message TEXT;
    END IF;
    
    -- Add allowed_domains if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='voice_agents' AND column_name='allowed_domains') THEN
        ALTER TABLE voice_agents ADD COLUMN allowed_domains JSONB;
    END IF;
END $$;

-- =====================================================
-- 5. Update Calls Table (Add Callback & Email Fields)
-- =====================================================
DO $$ 
BEGIN
    -- Add callback_requested if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='calls' AND column_name='callback_requested') THEN
        ALTER TABLE calls ADD COLUMN callback_requested BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Add callback_reason if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='calls' AND column_name='callback_reason') THEN
        ALTER TABLE calls ADD COLUMN callback_reason TEXT;
    END IF;
    
    -- Add summary_email_sent if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='calls' AND column_name='summary_email_sent') THEN
        ALTER TABLE calls ADD COLUMN summary_email_sent BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Add summary_email_sent_at if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='calls' AND column_name='summary_email_sent_at') THEN
        ALTER TABLE calls ADD COLUMN summary_email_sent_at TIMESTAMPTZ;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_calls_callback_requested ON calls(callback_requested);

-- =====================================================
-- 6. Enable Row Level Security (RLS) for Supabase
-- =====================================================

-- Enable RLS on new tables
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE callback_requests ENABLE ROW LEVEL SECURITY;

-- Policies for phone_numbers
CREATE POLICY "Users can view their own phone numbers"
    ON phone_numbers FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can create their own phone numbers"
    ON phone_numbers FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own phone numbers"
    ON phone_numbers FOR UPDATE
    USING (auth.uid()::text = user_id::text);

-- Policies for verification_documents
CREATE POLICY "Users can view their own verification documents"
    ON verification_documents FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can create their own verification documents"
    ON verification_documents FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own verification documents"
    ON verification_documents FOR UPDATE
    USING (auth.uid()::text = user_id::text);

-- Policies for callback_requests
CREATE POLICY "Users can view their own callback requests"
    ON callback_requests FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can create their own callback requests"
    ON callback_requests FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text);

CREATE POLICY "Users can update their own callback requests"
    ON callback_requests FOR UPDATE
    USING (auth.uid()::text = user_id::text);

-- =====================================================
-- 7. Sample Data (Optional - for testing)
-- =====================================================

-- Example: Insert a test phone number (uncomment to use)
-- INSERT INTO phone_numbers (
--     user_id, phone_number, country_code, number_type,
--     status, business_name, business_type, business_address,
--     monthly_cost, per_minute_cost
-- ) VALUES (
--     1, '+33123456789', 'FR', 'local',
--     'pending', 'Test Company', 'company', '123 Test Street, Paris, France',
--     '4.99', '0.02'
-- );

-- =====================================================
-- Migration Complete
-- =====================================================

-- Verify tables were created
SELECT 'Migration complete. New tables created:' as status;
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('phone_numbers', 'verification_documents', 'callback_requests');

-- Verify columns were added to existing tables
SELECT 'Columns in voice_agents:' as status;
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'voice_agents' 
AND column_name IN ('embed_enabled', 'embed_widget_color', 'embed_position', 'embed_greeting_message', 'allowed_domains');

SELECT 'Columns in calls:' as status;
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'calls' 
AND column_name IN ('callback_requested', 'callback_reason', 'summary_email_sent', 'summary_email_sent_at');

