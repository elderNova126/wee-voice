# Text Chat Feature - Documentation

## Overview

The WeeVoice platform now supports **text-only chat mode** in addition to voice calls. This allows your voice agents to be used as traditional chatbots on websites, giving users the option to type messages instead of speaking.

## Key Features

✅ **Dual Provider Support**: Uses Anthropic Claude (primary) with OpenAI GPT fallback  
✅ **Real-time WebSocket Communication**: Instant message delivery  
✅ **RAG Integration**: Access to knowledge base documents  
✅ **Callback Detection**: Automatically detects when human intervention is needed  
✅ **Multi-language Support**: Works with all supported languages  
✅ **Responsive UI**: Beautiful chat interface that works on all devices  
✅ **Easy Integration**: Simple JavaScript snippet for any website  

## Architecture

### Backend Components

1. **TextChatService** (`backend/app/services/text_chat_service.py`)
   - Manages text conversations
   - Handles Anthropic API (primary) and OpenAI API (fallback)
   - Integrates with RAG system for knowledge base queries
   - Detects callback requirements

2. **WebSocket Endpoint** (`/api/v1/ws/text/{agent_id}`)
   - Real-time bidirectional communication
   - JSON message protocol
   - Session management

3. **Database Schema**
   - New `interaction_mode` field in `voice_agents` table
   - Values: `voice`, `text`, or `both`

### Frontend Components

1. **Widget JavaScript** (`backend/static/js/voice-widget.js`)
   - Supports both voice and text modes
   - Auto-detects mode from configuration
   - Manages WebSocket connection

2. **Widget CSS** (`backend/static/css/voice-widget.css`)
   - Chat interface styles
   - Message bubbles (user/assistant/system)
   - Responsive design

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install anthropic==0.39.0
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Add to your `.env` file:

```env
# Anthropic (Primary - Recommended)
ANTHROPIC_API_KEY=sk-ant-api03-...

# OpenAI (Fallback)
OPENAI_API_KEY=sk-proj-...
```

**Note**: You need at least one of these API keys. Anthropic is used first, then OpenAI as fallback.

### 3. Run Database Migration

```bash
psql -U your_user -d your_database -f database/migrations/add_interaction_mode_to_agents.sql
```

Or manually add the column:
```sql
ALTER TABLE voice_agents 
ADD COLUMN interaction_mode VARCHAR(20) DEFAULT 'voice';
```

### 4. Create or Update Agent

When creating/updating an agent, set the `interaction_mode`:

```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chat Support Bot",
    "system_prompt": "You are a helpful customer support assistant.",
    "language": "en-US",
    "interaction_mode": "text",
    "greeting": "Hello! How can I help you today?"
  }'
```

### 5. Embed on Website

Add this code to your website:

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://your-domain.com/static/css/voice-widget.css">
</head>
<body>
    <!-- Your website content -->
    
    <script src="https://your-domain.com/static/js/voice-widget.js"></script>
    <script>
        WeeVoiceWidget.init({
            mode: 'text',  // 'voice' or 'text'
            apiUrl: 'https://your-domain.com',
            agentId: YOUR_AGENT_ID,
            agentName: 'Support Assistant',
            greeting: 'Hi! How can I help?',
            color: '#4F46E5',
            position: 'bottom-right',  // or 'bottom-left'
            language: 'en'  // en, fr, es, de, it, pt, zh, ja, ko
        });
    </script>
</body>
</html>
```

## API Reference

### WebSocket Endpoint

**URL**: `ws://your-domain.com/api/v1/ws/text/{agent_id}`

**Query Parameters**:
- `token` (optional): JWT authentication token
- `api_key` (optional): API key for authentication

### Message Protocol

#### Client → Server

**Send Message**:
```json
{
  "type": "message",
  "content": "Hello, I need help with..."
}
```

**End Session**:
```json
{
  "type": "end_session"
}
```

#### Server → Client

**Session Started**:
```json
{
  "type": "session_started",
  "session_id": "uuid",
  "call_id": 123,
  "agent_name": "Support Assistant",
  "language": "en-US",
  "mode": "text"
}
```

**AI Response**:
```json
{
  "type": "message",
  "role": "assistant",
  "content": "I'd be happy to help you with that...",
  "timestamp": "2025-12-19T10:30:00Z",
  "needs_callback": false,
  "callback_priority": null
}
```

**Error**:
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Configuration Options

### Agent Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `interaction_mode` | string | `"voice"` | `"voice"`, `"text"`, or `"both"` |
| `system_prompt` | string | required | AI instructions and personality |
| `greeting` | string | optional | Initial message shown to users |
| `language` | string | `"en-US"` | Agent language |
| `rag_enabled` | boolean | `false` | Enable knowledge base integration |

### Widget Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mode` | string | `"voice"` | `"voice"` or `"text"` |
| `apiUrl` | string | required | Backend API URL |
| `agentId` | number | required | Agent ID |
| `agentName` | string | required | Display name |
| `greeting` | string | optional | Welcome message |
| `color` | string | `"#4F46E5"` | Primary color (hex) |
| `position` | string | `"bottom-right"` | `"bottom-right"` or `"bottom-left"` |
| `language` | string | `"en"` | UI language code |

## Features in Detail

### 1. Anthropic Claude Integration

The system uses Anthropic's Claude as the primary AI provider:
- **Model**: `claude-3-5-sonnet-20241022` (latest)
- **Max Tokens**: 1024 (configurable)
- **System Prompt**: Custom per agent
- **Advantages**: Superior reasoning, multilingual support, longer context

### 2. OpenAI Fallback

If Anthropic fails or is unavailable:
- **Model**: `gpt-4o`
- **Automatic Fallback**: No configuration needed
- **Same API**: Seamless transition

### 3. RAG (Knowledge Base) Support

When enabled:
- Searches uploaded documents automatically
- Includes relevant context in queries
- Top 3 results used by default
- Works with both Anthropic and OpenAI

### 4. Callback Detection

System automatically detects when human help is needed:

**Priority Levels**:
- `URGENT`: Angry/frustrated users
- `HIGH`: Complex issues, explicit human requests
- `NORMAL`: Sensitive topics

**Markers**:
```
[CALLBACK_URGENT] - Immediate escalation needed
[CALLBACK_HIGH] - Route to human soon
[CALLBACK_NORMAL] - Human follow-up recommended
```

These markers are removed before showing to user.

### 5. Conversation History

- Stored in `conversation_history` list
- Saved to database as `CallMessage` records
- Used for context in subsequent messages
- Included in call transcript

## Testing

### 1. Local Testing

```bash
# Start backend
cd backend
python -m uvicorn app.main:app --reload

# Open test page
open http://localhost:8000/test-text-chat-widget.html
```

### 2. Test with Curl

```bash
# Create test agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Chat Bot",
    "system_prompt": "You are a test assistant.",
    "interaction_mode": "text"
  }'
```

### 3. WebSocket Testing

Use a WebSocket client like `wscat`:

```bash
npm install -g wscat
wscat -c "ws://localhost:8000/api/v1/ws/text/1"

# Send message
> {"type": "message", "content": "Hello!"}

# Receive response
< {"type": "message", "role": "assistant", "content": "Hi! How can I help?", ...}
```

## Troubleshooting

### Issue: "Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is configured"

**Solution**: Add at least one API key to `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Issue: "Agent does not support text mode"

**Solution**: Update agent's `interaction_mode`:
```sql
UPDATE voice_agents 
SET interaction_mode = 'text' 
WHERE id = YOUR_AGENT_ID;
```

### Issue: WebSocket connection fails

**Check**:
1. Backend is running: `http://localhost:8000/docs`
2. CORS settings allow your domain
3. Agent ID exists and is active
4. Network allows WebSocket connections

### Issue: No AI responses

**Check**:
1. API keys are valid
2. Check backend logs for errors
3. Verify agent's `system_prompt` is set
4. Test API keys directly:

```python
# Test Anthropic
from anthropic import Anthropic
client = Anthropic(api_key="your-key")
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.content)
```

## Production Deployment

### 1. Environment Variables

```env
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql://user:pass@host:5432/db

# Optional
OPENAI_API_KEY=sk-proj-...
SECRET_KEY=your-secret-key-here
```

### 2. CORS Configuration

Update `backend/app/core/config.py`:
```python
BACKEND_CORS_ORIGINS: List[str] = [
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]
```

### 3. SSL/TLS

WebSocket connections should use `wss://` in production:
```javascript
apiUrl: 'https://your-domain.com',  // Will auto-convert to wss://
```

### 4. Rate Limiting

Consider adding rate limits for:
- Message sending (e.g., 10 messages/minute)
- Connection creation (e.g., 5 connections/hour)

## Best Practices

1. **System Prompts**
   - Be specific about agent's role and capabilities
   - Include language instructions if multilingual
   - Set clear boundaries

2. **Greetings**
   - Keep short and friendly
   - Mention main capabilities
   - Encourage user to ask questions

3. **Error Handling**
   - Always show user-friendly error messages
   - Log detailed errors server-side
   - Implement retry logic for transient failures

4. **Performance**
   - Use Anthropic for best quality
   - Keep system prompts concise
   - Limit conversation history if needed

5. **Security**
   - Always use HTTPS/WSS in production
   - Validate and sanitize user input
   - Implement rate limiting
   - Use authentication for private agents

## Examples

### Customer Support Bot

```javascript
WeeVoiceWidget.init({
    mode: 'text',
    apiUrl: 'https://api.yourcompany.com',
    agentId: 42,
    agentName: 'Support Assistant',
    greeting: 'Hi! I\'m here to help with your questions about our products and services.',
    color: '#2563eb',
    position: 'bottom-right',
    language: 'en'
});
```

### Sales Assistant

```javascript
WeeVoiceWidget.init({
    mode: 'text',
    apiUrl: 'https://api.yourcompany.com',
    agentId: 43,
    agentName: 'Sales Bot',
    greeting: 'Hello! Looking to learn more about our solutions? Ask me anything!',
    color: '#10b981',
    position: 'bottom-right',
    language: 'en'
});
```

### Multilingual Support

```javascript
// French
WeeVoiceWidget.init({
    mode: 'text',
    apiUrl: 'https://api.yourcompany.com',
    agentId: 44,
    agentName: 'Assistant Français',
    greeting: 'Bonjour! Comment puis-je vous aider aujourd\'hui?',
    color: '#6366f1',
    position: 'bottom-right',
    language: 'fr'
});
```

## Migration from Voice to Text

To add text support to existing voice agents:

```sql
-- Enable both modes for existing agent
UPDATE voice_agents 
SET interaction_mode = 'both' 
WHERE id = YOUR_AGENT_ID;
```

Then users can choose:
```javascript
// Voice mode
WeeVoiceWidget.init({ mode: 'voice', agentId: 1, ... });

// OR Text mode
WeeVoiceWidget.init({ mode: 'text', agentId: 1, ... });
```

## Roadmap

Future enhancements planned:
- [ ] Streaming responses for longer messages
- [ ] Message typing indicators
- [ ] Read receipts
- [ ] File upload support
- [ ] Rich message formatting (markdown)
- [ ] Suggested quick replies
- [ ] Chat history persistence
- [ ] Multi-agent handoff

## Support

For issues or questions:
- Check logs: `backend/logs/`
- Review API docs: `http://localhost:8000/docs`
- Test endpoint: `http://localhost:8000/api/v1/agents`

## License

Same as main WeeVoice platform license.

