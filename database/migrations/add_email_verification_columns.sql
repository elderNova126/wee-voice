-- ===================================================================
-- Email Verification and Password Reset Migration
-- Date: 2025-12-29
-- ===================================================================
-- This migration adds support for email verification and password reset
-- ===================================================================

-- Add email verification columns to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verification_token VARCHAR(255),
ADD COLUMN IF NOT EXISTS verification_token_expires TIMESTAMP,
ADD COLUMN IF NOT EXISTS reset_password_token VARCHAR(255),
ADD COLUMN IF NOT EXISTS reset_password_token_expires TIMESTAMP;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);
CREATE INDEX IF NOT EXISTS idx_users_reset_password_token ON users(reset_password_token);

-- Update existing users to be verified (optional - comment out if you want existing users to verify)
-- UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL OR email_verified = FALSE;

-- Show migration status
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Added columns: email_verified, verification_token, verification_token_expires, reset_password_token, reset_password_token_expires';
    RAISE NOTICE 'Created indexes on verification_token and reset_password_token';
END $$;

