-- Migration: Add LLM model selection to phone_numbers
-- Date: 2026-01-29
-- Description: Allows users to select which LLM model to use for phone call agents

-- Add llm_model column to phone_numbers table
-- Default to 'gemini' for existing phone numbers (current behavior)
ALTER TABLE phone_numbers 
ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100) DEFAULT 'gemini';

-- Supported models:
-- OpenAI: gpt-3.5-turbo, gpt-3.5-turbo-16k, gpt-4, gpt-4o, gpt-4o-mini, 
--         gpt-4-turbo, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5, gpt-5-mini, gpt-5-nano
-- Google: gemini (gemini-2.5-flash-native-audio-preview-09-2025)

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_phone_numbers_llm_model ON phone_numbers(llm_model);

-- Verify migration
DO $$
BEGIN
    RAISE NOTICE 'Migration complete: Added llm_model column to phone_numbers table';
    RAISE NOTICE 'Default value: gemini (for native audio dialog support)';
END $$;
