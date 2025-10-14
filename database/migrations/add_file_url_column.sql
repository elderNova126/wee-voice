-- Migration: Add file_url column to documents table
-- Date: 2025-10-13
-- Description: Add file_url column to support Supabase Storage URLs

-- Add file_url column to documents table
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS file_url VARCHAR;

-- Add comment for clarity
COMMENT ON COLUMN documents.file_url IS 'Public URL for Supabase storage files (null for local storage)';

-- Update metadata for tracking storage type
COMMENT ON COLUMN documents.file_path IS 'Path to stored file (local path or Supabase path)';

-- Migration completed
SELECT 'Migration completed: file_url column added to documents table' AS status;

