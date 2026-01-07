# Multi Phone Number System

This document explains how WeeVoice handles multiple phone numbers with different SIP configurations and agents.

## Overview

WeeVoice supports multiple phone numbers, each with:
- Its own SIP configuration (WebSocket URL, username, password, domain)
- An assigned AI agent with unique personality, voice, and prompts
- Automatic Asterisk configuration generation

When a call comes in to any phone number, the system:
1. Identifies which phone number was called (DID)
2. Looks up the phone number in the database
3. Finds the assigned agent
4. Routes the call to that agent's AI voice service

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Zadarma SIP   │────▶│   Asterisk   │────▶│  EAGI Script    │
│   Trunk         │     │   PBX        │     │  (Call Router)  │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                      │
                               ┌──────────────────────┼──────────────────────┐
                               │                      │                      │
                               ▼                      ▼                      ▼
                        ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
                        │ Phone #1     │       │ Phone #2     │       │ Phone #3     │
                        │ +32480206645 │       │ +33612345678 │       │ +1234567890  │
                        │ Agent: Sales │       │ Agent: Suppt │       │ Agent: Info  │
                        └──────────────┘       └──────────────┘       └──────────────┘
```

## Components

### 1. EAGI Script (`weevoice_eagi_realtime.py`)

The EAGI script is the core call router. When a call arrives:

1. **Extract DID**: Gets the called number from AGI variables:
   - `FROM_DID` (set in extensions.conf)
   - `agi_dnid` (Dialed Number Identification)
   - `agi_extension`
   - `EXTEN` channel variable

2. **Database Lookup**: Searches `phone_numbers` table for matching number

3. **Agent Resolution**: Gets the agent assigned to that phone number

4. **Start AI Session**: Creates `FrenchVoiceAgentService` with the correct agent

### 2. Asterisk Configuration Service (`asterisk_config_service.py`)

Generates dynamic Asterisk configuration based on database phone numbers:

- **`pjsip_weevoice.conf`**: PJSIP endpoints for each phone number
- **`extensions_weevoice.conf`**: Routing rules for each phone number

### 3. Phone Numbers API (`phone_numbers.py`)

REST API for managing phone numbers:
- Add/remove phone numbers
- Configure SIP credentials
- Assign agents
- Auto-triggers Asterisk config regeneration on changes

### 4. Asterisk API (`asterisk.py`)

API endpoints for Asterisk management:
- Preview generated configurations
- Regenerate config files
- Reload Asterisk

## Database Schema

The `phone_numbers` table stores:

```sql
phone_numbers (
    id,
    user_id,
    agent_id,           -- References voice_agents.id
    phone_number,       -- E.164 format: +32480206645
    country_code,
    number_type,
    -- SIP Configuration
    sip_websocket_url,  -- wss://weevoice.weedoo.com:8089/ws
    sip_transport,      -- WSS
    sip_username,       -- SIP login
    sip_password,       -- SIP password
    sip_domain,         -- weevoice.weedoo.com
    status,
    business_name,
    ...
)
```

## Setup Process

### 1. Add Phone Number (Frontend)

1. Go to **Phone Numbers** page
2. Click **Add Existing Number** or **Request New Number**
3. Enter phone number and SIP credentials
4. Save

### 2. Configure SIP Settings

In the phone number settings:
- **WebSocket URL**: `wss://your-asterisk-server:8089/ws`
- **Transport**: `WSS` (Secure WebSocket)
- **Username**: Your SIP username
- **Password**: Your SIP password  
- **Domain**: Your SIP domain

### 3. Assign Agent

1. Go to phone number settings
2. Select an agent from the dropdown
3. Save

### 4. Regenerate Asterisk Config (Automatic)

Configuration is auto-regenerated when:
- Adding a phone number with SIP config
- Updating SIP settings
- Assigning an agent
- Deleting a phone number

Manual regeneration:
```bash
curl -X POST https://api.example.com/api/v1/asterisk/regenerate \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## API Endpoints

### Phone Numbers

```
POST   /api/v1/phone-numbers/add-existing     Add phone with SIP config
GET    /api/v1/phone-numbers/                 List all phone numbers
GET    /api/v1/phone-numbers/{id}             Get phone number details
PUT    /api/v1/phone-numbers/{id}             Update settings (triggers config regen)
DELETE /api/v1/phone-numbers/{id}             Delete phone number
POST   /api/v1/phone-numbers/{id}/activate/{agent_id}  Assign agent
```

### Asterisk Configuration

```
POST   /api/v1/asterisk/regenerate            Regenerate config files
GET    /api/v1/asterisk/status                Get config file status
POST   /api/v1/asterisk/reload                Reload Asterisk (admin only)
GET    /api/v1/asterisk/preview/pjsip         Preview PJSIP config
GET    /api/v1/asterisk/preview/extensions    Preview extensions config
GET    /api/v1/asterisk/phone-numbers         List configured phone numbers
```

### Virtual Numbers (Zadarma)

```
GET    /api/v1/virtual-numbers/countries      List available countries
GET    /api/v1/virtual-numbers/destinations/{country}  List cities
GET    /api/v1/virtual-numbers/available/{direction}   Available numbers
POST   /api/v1/virtual-numbers/order          Order new number
```

## Generated Configuration Files

### pjsip_weevoice.conf

```ini
;--- Endpoint for +32480206645 ---
[weevoice-myuser]
type=endpoint
transport=transport-ws-server-8089
context=weevoice-inbound
disallow=all
allow=ulaw
allow=alaw
allow=opus
webrtc=yes
auth=weevoice-myuser-auth
aors=weevoice-myuser
callerid="WeeVoice" <+32480206645>
from_user=myuser
from_domain=weevoice.weedoo.com
...
```

### extensions_weevoice.conf

```ini
[weevoice-inbound]
; Phone: +32480206645 -> Agent: 1 (Sales Agent)
exten => 32480206645,1,NoOp(=== WeeVoice Incoming: +32480206645 ===)
 same => n,Set(CALLED_DID=+32480206645)
 same => n,Set(FROM_DID=+32480206645)
 same => n,Set(AGENT_ID=1)
 same => n,Answer()
 same => n,Wait(0.5)
 same => n,EAGI(${WEEVOICE_EAGI})
 same => n,Hangup()
```

## Troubleshooting

### Call Not Routing to Correct Agent

1. Check phone number format in database (should be E.164: +32480206645)
2. Verify agent is assigned: `agent_id IS NOT NULL`
3. Check EAGI logs: `/var/log/weevoice/eagi.log`

### SIP Configuration Not Working

1. Verify all SIP fields are filled:
   - `sip_websocket_url`
   - `sip_username`
   - `sip_password`
   - `sip_domain`

2. Check Asterisk config generated:
   ```bash
   cat /etc/asterisk/pjsip_weevoice.conf
   ```

3. Reload Asterisk:
   ```bash
   asterisk -rx "pjsip reload"
   asterisk -rx "dialplan reload"
   ```

### Config Not Regenerating

1. Check backend logs for errors
2. Verify database connection
3. Check file permissions: `/etc/asterisk/`
4. Manual regenerate via API

## Security Considerations

1. **SIP Passwords**: Stored in database, transmitted over HTTPS
2. **WebSocket Security**: Use `wss://` (TLS) for SIP WebSockets
3. **API Authentication**: All endpoints require JWT token
4. **Asterisk Reload**: Only admins can trigger direct Asterisk reload

## Environment Variables

```bash
# Asterisk paths (defaults shown)
ASTERISK_CONFIG_DIR=/etc/asterisk
ASTERISK_AGI_DIR=/var/lib/asterisk/agi-bin
ASTERISK_SPOOL_DIR=/var/spool/asterisk

# Zadarma trunk credentials (for outbound calls)
ZADARMA_SIP_LOGIN=your_login
ZADARMA_SIP_PASSWORD=your_password
```

## Files Modified

### Backend
- `backend/eagi/weevoice_eagi_realtime.py` - Call routing based on DID
- `backend/app/services/asterisk_config_service.py` - Config generation
- `backend/app/api/asterisk.py` - Config management API
- `backend/app/api/phone_numbers.py` - Auto config regen on changes

### Asterisk
- `deploy/asterisk/extensions.conf` - Includes generated config
- `deploy/asterisk/pjsip.conf` - Includes generated config

### Generated (by backend)
- `/etc/asterisk/pjsip_weevoice.conf`
- `/etc/asterisk/extensions_weevoice.conf`

