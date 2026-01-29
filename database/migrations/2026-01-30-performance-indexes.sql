-- ===================================================================
-- Performance Indexes Migration
-- Date: 2026-01-30
-- Purpose: Add indexes to improve query performance
-- ===================================================================

-- Index for action_required filter (JSONB array search)
-- Helps with the optimized action_required filter query
CREATE INDEX IF NOT EXISTS idx_calls_action_tags_gin ON calls USING GIN (action_tags jsonb_path_ops);

-- Composite index for caller_phone lookups with ordering
-- Helps with leads aggregation queries
CREATE INDEX IF NOT EXISTS idx_calls_agent_phone_started ON calls(agent_id, caller_phone, started_at DESC) 
    WHERE caller_phone IS NOT NULL;

-- Index for callback_requested filter (common in action_required queries)
CREATE INDEX IF NOT EXISTS idx_calls_callback_requested ON calls(callback_requested) 
    WHERE callback_requested = true;

-- Composite index for agent integrations lookup
CREATE INDEX IF NOT EXISTS idx_agent_integrations_composite ON agent_integrations(agent_id, integration_id);

-- Index for collaborator lookups (used in agents list)
CREATE INDEX IF NOT EXISTS idx_collaborators_user_active ON agent_collaborators(user_id, is_active) 
    WHERE is_active = true;

-- Index for call messages (used in text chat detection)
CREATE INDEX IF NOT EXISTS idx_call_messages_call_count ON call_messages(call_id);

-- Composite index for calls list with common filters
CREATE INDEX IF NOT EXISTS idx_calls_user_status_created ON calls(user_id, status, created_at DESC);

-- Index for favorite calls filter
CREATE INDEX IF NOT EXISTS idx_calls_user_favorite ON calls(user_id, is_favorite) 
    WHERE is_favorite = true;

-- Index for agent owner queries
CREATE INDEX IF NOT EXISTS idx_agents_user_id_active ON voice_agents(user_id, is_active);

-- Index for phone numbers with collaborators (for pending invites queries)
-- Since collaborators is stored as TEXT JSON, we can't use GIN but can at least index non-null
CREATE INDEX IF NOT EXISTS idx_phone_numbers_has_collaborators ON phone_numbers(user_id) 
    WHERE collaborators IS NOT NULL AND collaborators != '' AND collaborators != '[]';

-- ANALYZE tables to update statistics after adding indexes
ANALYZE calls;
ANALYZE voice_agents;
ANALYZE agent_integrations;
ANALYZE agent_collaborators;
ANALYZE call_messages;
ANALYZE phone_numbers;
