-- Migration: Add busy line settings and call restrictions to phone_numbers table
-- Date: 2025-12-12

-- Busy settings
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS busy_action VARCHAR DEFAULT 'busy_tone';
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS busy_audio_file_url VARCHAR;

-- Call restrictions
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS blocked_countries TEXT;
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS blocked_numbers TEXT;
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS allowed_countries TEXT;
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS restriction_mode VARCHAR DEFAULT 'none';
