# SIP Integration Setup

Connect your Dialsense SIP server with your voice agent app for full phone call support.

## Setup (5 minutes)

### 1. Add to `backend/.env`

```bash
SIP_ENABLED=true
SIP_WS_URL=wss://weevoice.weedoo.com:8089/ws
SIP_USERNAME=55555
SIP_PASSWORD=KpowernBgdfgdffdgg3244
SIP_DOMAIN=weevoice.weedoo.com
```

### 2. Start Backend

```bash
cd backend
python -m uvicorn app.main:app --reload
```

**Look for**:
```
✅ SIP registration successful
✅ SIP Call Handler started successfully
```

### 3. Configure Zadarma

Route your Zadarma phone number to your SIP server:

**In Zadarma Dashboard:**
- Go to **My Numbers** → Select number → **Settings**
- Set **Forward to SIP**: `sip:55555@weevoice.weedoo.com:8089;transport=wss`

OR use **SIP Trunk** in PBX settings.

### 4. Assign Agent (Frontend)

- Go to **Phone Numbers**
- Select your number → **Assign Agent**
- Choose voice agent → Save

### 5. Test

Call your Zadarma number → AI agent answers!

---

## How It Works

```
📞 Caller
  ↓
📱 Zadarma Number
  ↓
🌐 Dialsense SIP Server (weevoice.weedoo.com)
  ↓
⚙️ Backend (your wee-voice app)
  ↓
🤖 Gemini AI
```

**Audio conversions** (automatic):
- Caller: 8kHz → 16kHz → Gemini
- Gemini: 24kHz → 8kHz → Caller

---

## What You Get

✅ Full bidirectional phone calls  
✅ Real-time AI conversations  
✅ Call transcripts & summaries  
✅ Dashboard with live status  
✅ Cost tracking & analytics  
✅ Multiple agents, multiple numbers  

---

## Files Changed

**New**:
- `backend/app/services/sip_client_service.py` - SIP WebSocket client
- `backend/app/services/sip_call_handler.py` - Call orchestration

**Updated**:
- `backend/app/core/config.py` - Added SIP settings
- `backend/app/main.py` - Auto-start SIP on launch

---

## Troubleshooting

**Connection failed?**
- Verify SIP_WS_URL, username, password
- Check firewall allows port 8089

**No agent found?**
- Assign agent to phone number in frontend

**No audio?**
- Check logs for "Gemini session started"
- Verify GOOGLE_API_KEY is set

**Call doesn't show in dashboard?**
- Check WebSocket connection in browser console
- Verify BACKEND_URL is correct

---

## That's It!

Your voice agents now handle real phone calls through your Dialsense SIP server. No extra infrastructure needed.





