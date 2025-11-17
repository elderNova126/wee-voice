# Phone Call Implementation Summary

## Problem Identified

The phone call system was creating call records and starting agent sessions, but **was not actually streaming audio** between Zadarma and the Gemini API. This meant phone calls couldn't have real conversations with the AI agent.

## Solution Implemented

Created a **phone audio bridge system** that works exactly like the web voice agent, but uses HTTP endpoints instead of WebSocket for audio streaming.

## Key Components

### 1. Phone Audio Bridge Service (`backend/app/services/phone_audio_bridge.py`)

- **`PhoneAudioBridge`**: Manages bidirectional audio streaming for a single phone call
  - Receives audio from Zadarma → Forwards to Gemini
  - Receives audio from Gemini → Queues for Zadarma to retrieve
  - Handles audio format conversion (16kHz ↔ 24kHz)

- **`PhoneCallAudioManager`**: Manages multiple concurrent phone call bridges
  - Creates bridges when calls start
  - Tracks active bridges
  - Cleans up when calls end

### 2. Phone Audio API (`backend/app/api/phone_audio.py`)

HTTP endpoints for Zadarma to send/receive audio:

- **POST `/api/v1/phone/audio/{call_id}/input`**: Receive caller's voice
- **GET `/api/v1/phone/audio/{call_id}/output`**: Get AI responses
- **POST `/api/v1/phone/audio/{call_id}/end`**: End audio streaming
- **GET `/api/v1/phone/audio/{call_id}/status`**: Check streaming status

### 3. Webhook Integration (`backend/app/api/zadarma_webhook.py`)

Updated to:
- Create phone audio bridge when call starts (NOTIFY_START)
- Return audio endpoint URLs to Zadarma
- Stop audio bridge when call ends (NOTIFY_END)

## How It Works

### Call Flow

1. **Call Starts (NOTIFY_START)**
   ```
   Zadarma → Webhook → Backend
   - Creates call record
   - Starts agent session
   - Creates audio bridge
   - Returns audio endpoint URLs
   ```

2. **Audio Streaming (During Call)**
   ```
   Caller Voice:
   Zadarma → POST /phone/audio/{id}/input → Backend → Gemini
   
   AI Responses:
   Gemini → Backend → GET /phone/audio/{id}/output ← Zadarma → Caller
   ```

3. **Call Ends (NOTIFY_END)**
   ```
   Zadarma → Webhook → Backend
   - Stops audio bridge
   - Updates call status
   - Triggers summarization
   ```

## Comparison with Web Voice Agent

| Aspect | Web Voice Agent | Phone Call Agent |
|--------|----------------|------------------|
| **Connection** | WebSocket (bidirectional) | HTTP POST/GET (polling) |
| **Input** | WebSocket binary messages | HTTP POST body |
| **Output** | WebSocket binary messages | HTTP GET response |
| **Real-time** | Yes (instant) | Yes (polling-based, ~100ms) |
| **Complexity** | Medium | Low |
| **Agent Service** | Same (`FrenchVoiceAgentService`) | Same |
| **Gemini API** | Same | Same |

## Key Features

✅ **Bidirectional Audio Streaming**
- Caller's voice → Gemini
- Gemini responses → Caller

✅ **Same Agent Service**
- Uses existing `FrenchVoiceAgentService`
- Same greeting, same conversation logic
- Same RAG, tools, and features

✅ **Automatic Format Handling**
- Input: 16kHz PCM16 (telephony standard)
- Output: 24kHz PCM16 (Gemini standard)
- Automatic conversion handled by bridge

✅ **Error Handling**
- Graceful degradation
- Automatic cleanup on call end
- Comprehensive logging

## Configuration Required

### Backend (.env)
```bash
BASE_URL=http://your-backend.com  # For audio endpoint URLs
```

### Zadarma PBX
Configure Zadarma to:
1. POST audio chunks to: `{BASE_URL}/api/v1/phone/audio/{call_id}/input`
2. GET audio chunks from: `{BASE_URL}/api/v1/phone/audio/{call_id}/output`
3. Poll output endpoint every ~100ms during active call

## Testing

### 1. Test Call Simulation
```bash
POST /api/v1/zadarma/test-call?phone_number=+3242833288
```
This creates a call record and starts the audio bridge.

### 2. Test Audio Input
```bash
POST /api/v1/phone/audio/{call_id}/input
Content-Type: audio/pcm;rate=16000
[PCM16 audio data]
```

### 3. Test Audio Output
```bash
GET /api/v1/phone/audio/{call_id}/output
# Returns: audio/pcm;rate=24000
[PCM16 audio data]
```

### 4. Check Status
```bash
GET /api/v1/phone/audio/{call_id}/status
# Returns: {"status": "active", "is_running": true, ...}
```

## Files Changed

1. **New Files:**
   - `backend/app/services/phone_audio_bridge.py` - Audio bridge service
   - `backend/app/api/phone_audio.py` - HTTP endpoints
   - `PHONE_CALL_AUDIO_SETUP.md` - Setup documentation

2. **Modified Files:**
   - `backend/app/api/zadarma_webhook.py` - Integrated audio bridge
   - `backend/app/main.py` - Added phone audio router
   - `backend/app/core/config.py` - Added BASE_URL setting

## Next Steps

1. **Configure Zadarma PBX** to use the audio endpoints
2. **Test with real phone call** to verify audio quality
3. **Monitor performance** and adjust polling intervals if needed
4. **Add authentication** to audio endpoints if required

## Notes

- The implementation mirrors the web voice agent architecture
- Same agent service means same features (RAG, tools, etc.)
- Audio format conversion is handled automatically
- The bridge automatically cleans up when calls end
- All audio streaming is logged for debugging

## Troubleshooting

See `PHONE_CALL_AUDIO_SETUP.md` for detailed troubleshooting guide.

Common issues:
- **No audio**: Check audio bridge status endpoint
- **Call drops**: Check webhook handler logs
- **Poor quality**: Verify audio format (PCM16, correct sample rates)

