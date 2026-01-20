-- Migration: Add separate provider SIP fields for inbound calls
-- Date: 2025-01-08
-- Purpose: Separate provider SIP credentials (for inbound/Zadarma) from 
--          Asterisk WebSocket credentials (for outbound calls)
--
-- BEFORE: Both inbound and outbound used the same sip_* fields, causing conflicts
-- AFTER: 
--   - provider_sip_* fields: Used by Asterisk to register with SIP provider (Zadarma)
--   - sip_* fields: Used by Python client to connect to Asterisk WebSocket for outbound

-- Add new provider SIP fields for inbound calls
ALTER TABLE phone_numbers 
ADD COLUMN IF NOT EXISTS provider_sip_username VARCHAR(255);

ALTER TABLE phone_numbers 
ADD COLUMN IF NOT EXISTS provider_sip_password VARCHAR(255);

ALTER TABLE phone_numbers 
ADD COLUMN IF NOT EXISTS provider_sip_domain VARCHAR(255);

-- Copy existing data from sip_* to provider_sip_* if domain looks like a provider
-- (This helps migrate existing setups where sip.zadarma.com was in sip_domain)
UPDATE phone_numbers 
SET 
    provider_sip_username = sip_username,
    provider_sip_password = sip_password,
    provider_sip_domain = sip_domain
WHERE sip_domain LIKE '%zadarma%' 
   OR sip_domain LIKE '%sip.%'
   OR sip_domain NOT IN ('localhost', '127.0.0.1');

-- Add comments for documentation
COMMENT ON COLUMN phone_numbers.provider_sip_username IS 'SIP provider username (e.g., Zadarma login) - used for INBOUND calls';
COMMENT ON COLUMN phone_numbers.provider_sip_password IS 'SIP provider password - used for INBOUND calls';
COMMENT ON COLUMN phone_numbers.provider_sip_domain IS 'SIP provider domain (e.g., sip.zadarma.com) - used for INBOUND calls';
COMMENT ON COLUMN phone_numbers.sip_websocket_url IS 'Asterisk WebSocket URL (e.g., ws://localhost:8089/ws) - used for OUTBOUND calls';
COMMENT ON COLUMN phone_numbers.sip_username IS 'Asterisk internal extension (e.g., 55555) - used for OUTBOUND calls';
COMMENT ON COLUMN phone_numbers.sip_password IS 'Asterisk extension password - used for OUTBOUND calls';
COMMENT ON COLUMN phone_numbers.sip_domain IS 'Asterisk server domain (e.g., localhost) - used for OUTBOUND calls';

