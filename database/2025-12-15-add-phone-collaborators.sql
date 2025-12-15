-- Migration: Add collaborators column to phone_numbers table
-- Date: 2025-12-15

-- ===================================================================
-- ADD COLLABORATORS COLUMN TO PHONE_NUMBERS TABLE
-- ===================================================================

-- Add collaborators column as JSON text to store collaborator data
-- Format: [{"user_id": 1, "email": "user@example.com", "permissions": "view,edit", "added_at": "2025-12-15T10:00:00"}]
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS collaborators TEXT;

