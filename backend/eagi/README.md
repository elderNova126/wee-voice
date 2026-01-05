# WeeVoice EAGI Integration

This directory contains the EAGI (Extended AGI) scripts for handling phone calls with Google Gemini AI.

## Overview

EAGI (Extended AGI) provides direct audio access from Asterisk, allowing real-time voice processing:

- **Audio Input**: File Descriptor 3 (FD3) provides raw audio from the caller (8kHz signed linear)
- **Audio Output**: AGI `STREAM FILE` command plays audio back to the caller
- **Control**: Standard AGI protocol via stdin/stdout

## Scripts

### `weevoice_eagi_realtime.py`

Main production EAGI script with:
- Real-time audio capture from Asterisk
- Streaming connection to Google Gemini Live API
- Audio format conversion (8kHz ↔ 16kHz ↔ 24kHz)
- Transcript capture and database storage
- Jitter buffering for smooth playback

### `weevoice_eagi.py`

Basic EAGI script for simpler deployments or testing.

## Installation

1. **Copy to AGI directory:**
   ```bash
   cp weevoice_eagi_realtime.py /var/lib/asterisk/agi-bin/
   chmod +x /var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py
   chown asterisk:asterisk /var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py
   ```

2. **Configure environment:**
   ```bash
   # /opt/weevoice/backend/.env
   GOOGLE_API_KEY=your-api-key-here
   GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-09-2025
   GEMINI_VOICE=Aoede
   ```

3. **Add to Asterisk dialplan:**
   ```
   [weevoice-ai-agent]
   exten => s,1,Answer()
    same => n,Wait(0.5)
    same => n,EAGI(/var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py)
    same => n,Hangup()
   ```

4. **Reload dialplan:**
   ```bash
   asterisk -rx "dialplan reload"
   ```

## Audio Flow

```
┌─────────────┐    8kHz slin    ┌──────────────┐    16kHz PCM    ┌─────────────┐
│  Asterisk   │ ──────────────► │  EAGI Script │ ──────────────► │   Gemini    │
│   (PSTN)    │                 │   (Python)   │                 │  Live API   │
│             │ ◄────────────── │              │ ◄────────────── │             │
└─────────────┘    8kHz slin    └──────────────┘    24kHz PCM    └─────────────┘
                  (STREAM FILE)                   (Resample)
```

### Input Path (Caller → Gemini)
1. Asterisk captures caller audio at 8kHz signed linear
2. EAGI reads from File Descriptor 3
3. Python resamples 8kHz → 16kHz
4. Audio sent to Gemini Live API

### Output Path (Gemini → Caller)
1. Gemini returns 24kHz PCM audio
2. Python resamples 24kHz → 8kHz
3. Audio saved to temp file (.sln)
4. AGI STREAM FILE plays to caller

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | (required) | Google AI API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-native-audio-preview-09-2025` | Gemini model |
| `GEMINI_VOICE` | `Aoede` | Voice name (Aoede, Charon, Fenrir, Kore, Puck) |
| `AGENT_SYSTEM_PROMPT` | Default prompt | AI system instructions |
| `AGENT_GREETING` | "Hello! How can I help..." | Initial greeting |

### Channel Variables

Set these in dialplan before calling EAGI:

| Variable | Description |
|----------|-------------|
| `AGENT_ID` | Load config from database for specific agent |

Example:
```
exten => s,1,Set(AGENT_ID=123)
 same => n,EAGI(/var/lib/asterisk/agi-bin/weevoice_eagi_realtime.py)
```

## Voice Options

Available Gemini voices:
- **Aoede** - Female, warm and friendly
- **Charon** - Male, deeper tone
- **Fenrir** - Male, authoritative
- **Kore** - Female, softer
- **Puck** - Neutral, standard

## Troubleshooting

### Logs
```bash
# EAGI logs
tail -f /var/log/weevoice/eagi_realtime.log

# Asterisk logs
tail -f /var/log/asterisk/messages

# Live debugging
asterisk -rvvvv
```

### Common Issues

**No audio:**
- Check File Descriptor 3 is available (EAGI, not AGI)
- Verify audio codec is `slin` (signed linear)
- Check Asterisk channel type supports EAGI audio

**API errors:**
- Verify GOOGLE_API_KEY is set
- Check internet connectivity
- Verify API key has Gemini access

**Choppy audio:**
- Increase jitter buffer settings
- Check network latency
- Verify CPU is not overloaded

## Testing

```bash
# Test EAGI directly
asterisk -rx 'originate Local/s@weevoice-ai-agent application Wait 60'

# Echo test (verify audio path)
asterisk -rx 'originate Local/9998@weevoice-test application Wait 30'
```

## Comparison: EAGI vs AudioSocket

| Feature | EAGI | AudioSocket |
|---------|------|-------------|
| Audio access | FD3 (unidirectional read) | TCP socket (bidirectional) |
| Output method | STREAM FILE (file-based) | Direct socket write |
| Latency | Slightly higher | Lower |
| Complexity | Simpler | More complex |
| Asterisk version | All versions | 16+ |

EAGI is recommended for:
- Simpler deployments
- Better compatibility
- Easier debugging

AudioSocket is better for:
- Ultra-low latency
- True real-time bidirectional audio
- High-volume deployments

