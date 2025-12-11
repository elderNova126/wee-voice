-- Add SIP configuration columns to phone_numbers table
-- These allow per-phone-number SIP credentials for incoming calls

ALTER TABLE phone_numbers
    ADD COLUMN IF NOT EXISTS sip_websocket_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS sip_transport VARCHAR(50) DEFAULT 'WSS',
    ADD COLUMN IF NOT EXISTS sip_username VARCHAR(255),
    ADD COLUMN IF NOT EXISTS sip_password VARCHAR(255),
    ADD COLUMN IF NOT EXISTS sip_domain VARCHAR(255);

-- Create index for faster lookup by SIP username
CREATE INDEX IF NOT EXISTS idx_phone_numbers_sip_username ON phone_numbers(sip_username);

