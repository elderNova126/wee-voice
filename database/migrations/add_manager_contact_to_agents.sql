-- ============================================================================
-- Migration: Add manager_contact field to voice_agents table
-- Purpose: Enable agents to provide manager contact info for escalation
-- Date: 2025-12-20
-- ============================================================================

-- Check if column exists (PostgreSQL syntax)
-- For PostgreSQL, this will be a no-op if column exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'voice_agents' 
        AND column_name = 'manager_contact'
    ) THEN
        ALTER TABLE voice_agents 
        ADD COLUMN manager_contact VARCHAR(255) NULL;
        
        RAISE NOTICE '✓ Column manager_contact added successfully';
    ELSE
        RAISE NOTICE '✓ Column manager_contact already exists, skipping';
    END IF;
END $$;

-- ============================================================================
-- Optional: Set default manager contact for existing agents
-- Uncomment and customize the line below if you want to set a default value
-- ============================================================================
-- UPDATE voice_agents 
-- SET manager_contact = 'support@company.com or +1-555-0100' 
-- WHERE manager_contact IS NULL;

-- ============================================================================
-- Verification: Check the column was added
-- ============================================================================
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'voice_agents' 
AND column_name = 'manager_contact';

-- Expected output:
-- column_name      | data_type        | character_maximum_length | is_nullable
-- manager_contact  | character varying| 255                      | YES

