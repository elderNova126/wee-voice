# Gemini 2.5 Flash Native Audio - Fix Guide

## Problem Summary

Your backend was encountering the following error:

```
websockets.exceptions.ConnectionClosedError: received 1008 (policy violation) 
models/gemini-2.5-flash-preview-native-audio-dialog is not found for API version v1beta, 
or is not supported for bidiGenera
```

This error indicated **three critical issues**:

1. **Invalid Model Name** - The model `gemini-2.5-flash-preview-native-audio-dialog` doesn't exist
2. **Incorrect Audio Format** - Audio wasn't being sent as a proper Blob with sample rate
3. **Protocol Violation** - The configuration and audio format didn't match API expectations

## Root Causes

### Issue 1: Wrong Model Name ❌
**Before:** `gemini-2.5-flash-preview-native-audio-dialog`  
**After:** `gemini-2.5-flash-native-audio-preview-09-2025` ✓

The old model name was invalid. The correct native audio model for Gemini 2.5 Flash is:
- `gemini-2.5-flash-native-audio-preview-09-2025`

### Issue 2: Incorrect Audio Blob Format ❌
**Before:**
```python
await self.session.send_realtime_input(audio=msg)
# where msg = {"data": audio_bytes, "mime_type": "audio/pcm"}
```

**After:**
```python
audio_blob = types.Blob(
    data=msg["data"],
    mime_type="audio/pcm;rate=16000"
)
await self.session.send_realtime_input(audio=audio_blob)
```

The API requires:
- Audio wrapped in `types.Blob()` object
- MIME type with sample rate: `audio/pcm;rate=16000` (not just `audio/pcm`)

### Issue 3: Configuration ✓ (Already Correct)
Response modalities was already set correctly to `["AUDIO"]` only, which is correct for native audio mode.

## Files Modified

### 1. `backend/app/core/config.py`
**Change:** Updated GEMINI_MODEL constant
```python
# Before
GEMINI_MODEL: str = "gemini-2.5-flash-preview-native-audio-dialog"

# After
GEMINI_MODEL: str = "gemini-2.5-flash-native-audio-preview-09-2025"
```

### 2. `backend/app/models/agent.py`
**Change:** Updated default model name in VoiceAgent model
```python
# Before
model_name = Column(String, default="gemini-2.5-flash-preview-native-audio-dialog")

# After
model_name = Column(String, default="gemini-2.5-flash-native-audio-preview-09-2025")
```

### 3. `backend/init_demo_agent.py`
**Changes:** Updated both demo agent creation calls
```python
# Before
model_name="gemini-2.5-flash-preview-native-audio-dialog"

# After
model_name="gemini-2.5-flash-native-audio-preview-09-2025"
```

### 4. `backend/app/services/agent_service.py`
**Change:** Updated `send_realtime_input()` method to use proper Blob wrapping
```python
# Before
await self.session.send_realtime_input(audio=msg)

# After
audio_blob = types.Blob(
    data=msg["data"],
    mime_type="audio/pcm;rate=16000"
)
await self.session.send_realtime_input(audio=audio_blob)
```

### 5. `backend/test.py` and `backend/test_connection.py`
**Changes:** Updated model references in test files

## Why These Fixes Work

### Model Name
The `gemini-2.5-flash-native-audio-preview-09-2025` model is specifically designed for:
- **Native audio streaming** - Ultra-low latency audio I/O
- **Bidirectional communication** - Send and receive audio simultaneously
- **Auto voice selection** - Automatically picks appropriate voice based on language
- **September 2025 preview** - Latest native audio implementation

### Audio Blob Format
The `types.Blob` wrapper is required by the Gemini Live API to:
- Properly serialize binary audio data
- Include MIME type information with sample rate specification
- Validate audio format before transmission
- Enable proper error handling

The sample rate specification `audio/pcm;rate=16000` ensures:
- API correctly interprets PCM audio format
- Proper resampling on the server side
- Prevents codec mismatch errors

## Testing the Fix

### Run the Test Script
```bash
cd backend
python test_audio_fix.py
```

Expected output:
```
✅ ALL TESTS PASSED! Your fixes are working correctly.

Key fixes applied:
  1. ✓ Updated model to: gemini-2.5-flash-native-audio-preview-09-2025
  2. ✓ Set response_modalities to: ['AUDIO']
  3. ✓ Updated MIME type to: audio/pcm;rate=16000
  4. ✓ Wrapped audio in types.Blob()
```

### Test with Frontend
1. Start the backend: `python -m uvicorn app.main:app --reload`
2. Open the frontend and connect to an agent
3. Speak into the microphone - audio should transmit without 1008 errors

## Audio Configuration Details

### Client to Server (Upload)
- **Format:** PCM 16-bit
- **Sample Rate:** 16000 Hz
- **Channels:** 1 (Mono)
- **Chunk Size:** 2048 bytes
- **MIME Type:** `audio/pcm;rate=16000`

### Server to Client (Download)
- **Format:** PCM 16-bit
- **Sample Rate:** 24000 Hz
- **Channels:** 1 (Mono)
- **MIME Type:** `audio/pcm;rate=24000`

## Key Implementation Details

### In `FrenchVoiceAgentService`:

1. **Config Building** (already correct):
```python
config = {
    "response_modalities": ["AUDIO"],  # Only AUDIO, no TEXT
    "system_instruction": types.Content(...),
}
```

2. **Audio Sending** (now fixed):
```python
audio_blob = types.Blob(
    data=audio_data,
    mime_type="audio/pcm;rate=16000"
)
await self.session.send_realtime_input(audio=audio_blob)
```

3. **Audio Receiving** (already correct):
```python
async for response in session.receive():
    if response.data:
        yield response.data
```

## Verification Checklist

After applying these fixes:

- [x] Model name updated to `gemini-2.5-flash-native-audio-preview-09-2025`
- [x] Audio wrapped in `types.Blob()` with proper MIME type
- [x] Sample rate specified as `rate=16000`
- [x] Response modalities set to `["AUDIO"]` only
- [x] No text responses in audio-only mode
- [x] Test script passes
- [x] WebSocket connections don't error with 1008

## Troubleshooting

### If you still see "not found for API version v1beta"
- Verify GOOGLE_API_KEY is valid and current
- Check that backend is using updated `config.py`
- Ensure database models are using new defaults (or create new agents)

### If you see "policy violation"
- Verify MIME type includes sample rate: `audio/pcm;rate=16000`
- Ensure audio is wrapped in `types.Blob()`
- Check that response_modalities = `["AUDIO"]` (no TEXT)

### If audio quality is poor
- Verify client is sending 16-bit PCM at 16000 Hz
- Check frontend audio encoding settings
- Try test script to isolate the issue

## References

- **Working Example:** See `backend/test.py` for complete working implementation
- **Gemini Live API Docs:** https://ai.google.dev/docs/live-api
- **Audio Format Requirements:** PCM 16-bit, 16000 Hz input, 24000 Hz output

## Summary

The three key fixes are:

1. **Model Name**: Use the correct model identifier
2. **Audio Blob**: Wrap audio in `types.Blob()` with sample rate in MIME type
3. **Configuration**: Keep response_modalities as `["AUDIO"]` only

These ensure compatibility with the Gemini 2.5 Flash Native Audio API and prevent connection errors.
