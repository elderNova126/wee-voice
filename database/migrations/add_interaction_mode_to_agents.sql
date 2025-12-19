-- Add interaction_mode column to voice_agents table
-- This allows agents to support voice, text, or both modes

ALTER TABLE voice_agents 
ADD COLUMN IF NOT EXISTS interaction_mode VARCHAR(20) DEFAULT 'voice';

-- Valid values: 'voice', 'text', 'both'
-- voice: Traditional voice-only agent (default)
-- text: Text chat only (uses Anthropic/OpenAI)
-- both: Supports both voice and text interactions

-- Add a check constraint to ensure valid values
ALTER TABLE voice_agents 
ADD CONSTRAINT check_interaction_mode 
CHECK (interaction_mode IN ('voice', 'text', 'both'));

-- Update existing agents to use 'voice' mode (backward compatibility)
UPDATE voice_agents 
SET interaction_mode = 'voice' 
WHERE interaction_mode IS NULL;

