-- Migration: Add busy line settings columns to phone_numbers table
-- Date: 2025-12-12

ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS busy_action VARCHAR DEFAULT 'busy_tone';
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS busy_audio_file_url VARCHAR;
