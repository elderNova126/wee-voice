-- Add avatar columns to users table
-- This migration adds support for video avatars from photos

-- Add avatar photo URL column (can store base64 or URL)
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_photo_url TEXT;

-- Add avatar photo type column ('upload' or 'sample')
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_photo_type VARCHAR(20);

-- Add avatar enabled flag
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_enabled BOOLEAN DEFAULT FALSE;

-- Add comment to document the feature
COMMENT ON COLUMN users.avatar_photo_url IS 'URL or base64 data for user avatar photo used in video calls';
COMMENT ON COLUMN users.avatar_photo_type IS 'Type of avatar photo: upload (user uploaded) or sample (from gallery)';
COMMENT ON COLUMN users.avatar_enabled IS 'Whether video avatar is enabled for calls';

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_avatar_enabled ON users(avatar_enabled) WHERE avatar_enabled = TRUE;

