-- Migration: Add voice_gender column to voice_agents table
-- Date: 2025-10-24
-- Purpose: Add voice gender selection (male, female, neutral) for Gemini 2.5 voices

-- Add voice_gender column
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS voice_gender VARCHAR(20) DEFAULT 'male';

-- Update comment
COMMENT ON COLUMN voice_agents.voice_gender IS 'Voice gender/type: male (Charon), female (Kore), neutral (Puck)';

-- Update existing agents to set voice_gender based on current voice_id
UPDATE voice_agents 
SET voice_gender = CASE 
    WHEN voice_id = 'Kore' OR voice_id = 'Aoede' THEN 'female'
    WHEN voice_id = 'Puck' THEN 'neutral'
    ELSE 'male'
END
WHERE voice_gender IS NULL;

-- Show migration result
DO $$
BEGIN
    RAISE NOTICE '✅ voice_gender column added successfully';
    RAISE NOTICE 'Voice types: male (Charon), female (Kore), neutral (Puck)';
    RAISE NOTICE 'Note: All Gemini 2.5 Flash voices have English accents';
END $$;

