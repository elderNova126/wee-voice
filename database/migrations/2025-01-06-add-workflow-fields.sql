-- ===================================================================
-- Migration: Add Workflow/Questionnaire Fields to Voice Agents
-- Date: 2025-01-06
-- Description: Adds fields to support structured outbound call workflows
--              where the agent proactively asks questions to leads
-- ===================================================================

-- Add call direction field (inbound vs outbound behavior)
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS call_direction VARCHAR(20) DEFAULT 'inbound';

-- Add workflow enabled flag
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS workflow_enabled BOOLEAN DEFAULT FALSE;

-- Add workflow questions (JSON array of questions)
-- Format: [{"id": 1, "question": "...", "key": "budget", "required": true}, ...]
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS workflow_questions JSONB DEFAULT '[]'::JSONB;

-- Add workflow intro message (said before starting questions)
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS workflow_intro TEXT;

-- Add workflow outro message (said after all questions answered)
ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS workflow_outro TEXT;

-- Add manager contact for escalation (if not already present)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'voice_agents' AND column_name = 'manager_contact'
    ) THEN
        ALTER TABLE voice_agents ADD COLUMN manager_contact VARCHAR(255);
    END IF;
END $$;

-- Add interaction_mode field if not present
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'voice_agents' AND column_name = 'interaction_mode'
    ) THEN
        ALTER TABLE voice_agents ADD COLUMN interaction_mode VARCHAR(20) DEFAULT 'voice';
    END IF;
END $$;

-- Create index for workflow-enabled agents
CREATE INDEX IF NOT EXISTS idx_agents_workflow_enabled ON voice_agents(workflow_enabled);
CREATE INDEX IF NOT EXISTS idx_agents_call_direction ON voice_agents(call_direction);

-- Comment on columns for documentation
COMMENT ON COLUMN voice_agents.call_direction IS 'Direction of calls: inbound (receive calls) or outbound (call leads)';
COMMENT ON COLUMN voice_agents.workflow_enabled IS 'When true, agent follows a structured question workflow';
COMMENT ON COLUMN voice_agents.workflow_questions IS 'JSON array of questions to ask in order: [{id, question, key, required}]';
COMMENT ON COLUMN voice_agents.workflow_intro IS 'Message said before starting the workflow questions';
COMMENT ON COLUMN voice_agents.workflow_outro IS 'Message said after all workflow questions are completed';

-- ===================================================================
-- Completion
-- ===================================================================
DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Migration: Workflow Fields Added Successfully!';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'New columns added to voice_agents:';
    RAISE NOTICE '  - call_direction (inbound/outbound)';
    RAISE NOTICE '  - workflow_enabled (boolean)';
    RAISE NOTICE '  - workflow_questions (JSONB array)';
    RAISE NOTICE '  - workflow_intro (TEXT)';
    RAISE NOTICE '  - workflow_outro (TEXT)';
    RAISE NOTICE '=====================================================';
END $$;

