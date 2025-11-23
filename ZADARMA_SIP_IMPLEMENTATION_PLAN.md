# Zadarma SIP Implementation Plan

## Current Architecture (HTTP Webhooks)
- **Zadarma** → HTTP webhook → Your backend → Creates call record
- **Audio**: HTTP POST/GET endpoints (not real-time SIP)
- **Problem**: This doesn't work well with Zadarma's actual call forwarding

## Target Architecture (SIP Direct)
- **Zadarma** → SIP INVITE → Your SIP server → Handles call directly
- **Audio**: Real-time RTP streams (not HTTP)
- **Configuration**: Manual setup in Zadarma dashboard

---

## Implementation Requirements

### 1. SIP Server Setup

You need a **Python SIP server** that can:
- Accept incoming SIP INVITE requests from Zadarma
- Handle SIP signaling (INVITE, ACK, BYE, etc.)
- Process RTP audio streams
- Bridge audio to Gemini API

**Python Libraries Options:**
- `pjsua2` (PJSIP Python bindings) - Recommended
- `aiortc` (WebRTC/SIP for asyncio)
- `python-sipsimple` (SIP SIMPLE SDK)

### 2. Railway Configuration

**Problem**: Railway is designed for HTTP/WebSocket apps, not SIP servers.

**Requirements**:
- Open UDP port 5060 (SIP signaling)
- Open UDP ports 10000-20000 (RTP audio)
- Static IP or domain for SIP URI
- Firewall rules to allow Zadarma IPs

**Zadarma IP Ranges to Whitelist**:
```
TBD - Need to get from Zadarma support
```

### 3. Network Architecture

```
[Caller] 
   ↓
[Zadarma Phone Number]
   ↓
[Zadarma PBX Extension] (Configured via dashboard)
   ↓ SIP INVITE to: user@your-railway-app.railway.app:5060
[Your SIP Server on Railway]
   ↓
[RTP Audio Stream]
   ↓
[Audio Bridge]
   ↓
[Gemini API]
```

---

## Challenges with Railway

### ❌ Railway Limitations:
1. **No UDP support by default** (SIP requires UDP)
2. **Dynamic IPs** (SIP needs static IP/domain)
3. **HTTP-focused** (no SIP protocol support)
4. **Port restrictions** (may not allow UDP 5060)

### ✅ Alternative Solutions:

#### Option 1: Use Twilio or Similar (Recommended)
- Zadarma → SIP → Twilio → WebSocket → Your Railway app
- Twilio handles SIP complexity
- You handle audio via WebSocket (already working!)

#### Option 2: Separate SIP Server
- Deploy SIP server on VPS (DigitalOcean, Linode)
- Open UDP ports 5060 + RTP ports
- SIP server forwards audio to Railway app via HTTP/WebSocket

#### Option 3: WebRTC Bridge
- Use `aiortc` to create WebRTC-to-HTTP bridge
- Zadarma → SIP → WebRTC → Your Railway app
- More complex but can work on Railway

---

## Recommended Approach

### Step 1: Verify Zadarma Requirements
Contact Zadarma support and ask:
1. What IP addresses do they send SIP calls from?
2. Can they forward to WebSocket instead of SIP?
3. Do they support HTTP audio endpoints? (They might already!)
4. Can they provide SIP-to-WebRTC gateway?

### Step 2: If Zadarma Requires SIP
Use a **SIP-to-HTTP bridge** (external service):
```
Zadarma → SIP → External SIP Gateway → HTTP/WebSocket → Railway App
```

Popular services:
- **Bandwidth.com**
- **SignalWire**
- **Telnyx**

### Step 3: If Railway Must Handle SIP Directly
Deploy separate SIP server:
```bash
# Use DigitalOcean droplet or similar
# Install PJSIP
sudo apt install python3-pjsua2

# Configure firewall
sudo ufw allow 5060/udp
sudo ufw allow 10000:20000/udp

# Run SIP server
python sip_server.py
```

---

## Simplified Solution (What I Recommend)

Instead of fighting with SIP on Railway, use **Zadarma's webhook system** (which already works!):

### Current Working Setup:
1. Configure in Zadarma dashboard:
   - PBX Extension → External Server: `your-railway-app.railway.app`
   - Webhook URL: `https://your-railway-app.railway.app/api/v1/zadarma/webhook`

2. When call arrives:
   - Zadarma sends webhook → Your app receives
   - Your app returns audio URLs
   - Zadarma fetches audio from your endpoints

This is **ALREADY IMPLEMENTED** in your code!

---

## What You Need to Do

### Immediate Actions:

1. **Simplify phone number configuration**:
   - Remove SIP URI field (not needed if using webhooks)
   - Keep only: Phone Number, Country Code, Business Name
   - Termination URI: pbx.zadarma.com (just for reference)

2. **Remove automatic PBX extension configuration**:
   - User configures manually in Zadarma dashboard
   - No API calls to create extensions

3. **Document manual setup process**:
   - User creates PBX extension in Zadarma
   - User sets call forwarding to webhook URL
   - User adds phone number to your system

4. **Test existing webhook flow**:
   - Make test call
   - Verify webhook receives call
   - Verify audio endpoints work

Would you like me to:
A) Implement SIP server (complex, requires VPS)
B) Simplify to webhook-only (recommended, already works)
C) Research SIP-to-HTTP bridge services
D) Document current working setup

**My recommendation: Option B** - Your webhook system already works, let's perfect that instead of adding SIP complexity.

