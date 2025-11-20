# PBX Extension Environment Setup Guide

This guide explains how to configure your environment variables to use PBX extensions with Zadarma.

## Required Environment Variables

### 1. Zadarma API Credentials (REQUIRED)

```bash
ZADARMA_API_KEY=your_zadarma_api_key_here
ZADARMA_API_SECRET=your_zadarma_api_secret_here
```

**How to get these:**
1. Log in to your Zadarma account
2. Go to: **Settings → API**
3. Copy your **API Key** and **API Secret**
4. Paste them into your `.env` file

**Important:** 
- The `ZADARMA_API_SECRET` is used to verify webhook signatures from Zadarma. Keep it secure!
- **No separate PBX login is needed** - the API key and secret authenticate all PBX operations
- These credentials work for both PBX extensions and SIP (if you use SIP later)

### 2. Backend URL (REQUIRED)

```bash
BACKEND_URL=https://your-domain.com
```

**Important for PBX Extensions:**
- Must be **publicly accessible** (not `localhost` or `127.0.0.1`)
- Must use **HTTPS** (Zadarma requires HTTPS for webhooks)
- This URL is used to construct the webhook endpoint: `{BACKEND_URL}/api/v1/zadarma/webhook`

**For Production:**
```bash
BACKEND_URL=https://weevoice-api-production.up.railway.app
```

**For Local Development:**
Use a tunneling service like ngrok:
```bash
# Install ngrok: https://ngrok.com/
# Run: ngrok http 8000
# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
BACKEND_URL=https://abc123.ngrok.io
```

### 3. Frontend URL (Optional)

```bash
FRONTEND_URL=https://your-frontend-domain.com
```

Used for email links and redirects.

## Complete .env File Example

Copy `.env.example.pbx` to `.env` and fill in your values:

```bash
cp .env.example.pbx .env
```

Then edit `.env` with your actual credentials.

## Minimal PBX Extension Setup

For PBX extensions to work, you only need these variables:

```bash
# Required
ZADARMA_API_KEY=your_api_key
ZADARMA_API_SECRET=your_api_secret
BACKEND_URL=https://your-public-domain.com

# Optional but recommended
GOOGLE_API_KEY=your_gemini_key  # For voice AI
DATABASE_URL=postgresql://...   # For production
```

**Note:** You do NOT need separate PBX login credentials. The API key and secret are sufficient for all PBX operations.

### Optional: PBX ID

If you have multiple PBX systems in your Zadarma account, you may need to specify which PBX to use:

```bash
# Optional: Only if you have multiple PBX systems
ZADARMA_PBX_ID=your_pbx_id
```

You can find your PBX ID in: **Zadarma Dashboard → PBX → Settings**

### SIP vs PBX

**Important distinction:**
- **PBX Extensions** use `ZADARMA_API_KEY` and `ZADARMA_API_SECRET` (no separate login)
- **SIP Connections** use `ZADARMA_SIP_LOGIN` and `ZADARMA_SIP_PASSWORD` (different credentials)

For PBX extensions, you only need the API credentials. SIP credentials are only needed if you want to use direct SIP connections instead of PBX extensions.

## Zadarma Webhook Configuration

After setting up your environment variables:

1. **In Zadarma Dashboard:**
   - Go to: **Settings → Integrations → API → Event Notifications**
   - Set **"About PBX calls"** webhook URL to:
     ```
     {BACKEND_URL}/api/v1/zadarma/webhook
     ```
   - Set **"About events"** webhook URL to:
     ```
     {BACKEND_URL}/api/v1/zadarma/webhook
     ```
   - Click **Save**

2. **Verify the webhook:**
   - Zadarma will send a test request with `?zd_echo=...`
   - Check your logs to confirm the webhook is receiving requests

## How PBX Extensions Work

1. When you assign a phone number to an agent in WeeVoice:
   - A PBX extension is automatically created (e.g., 2001, 2002, etc.)
   - The extension is configured to forward calls to your webhook
   - The webhook URL is: `{BACKEND_URL}/api/v1/zadarma/webhook`

2. When a call comes in:
   - Zadarma sends a `NOTIFY_START` webhook to your backend
   - Your backend creates a call record and starts the voice agent
   - The call is handled by your AI agent

3. Webhook events handled:
   - `NOTIFY_START`: Incoming call initiated
   - `NOTIFY_INTERNAL`: Internal call to PBX extension
   - `NOTIFY_ANSWER`: Call was answered
   - `NOTIFY_END`: Call ended
   - `NOTIFY_IVR`: Caller response to IVR action
   - `NOTIFY_RECORD`: Call recording available

## Troubleshooting

### Issue: "Invalid signature" errors

**Solution:** Make sure `ZADARMA_API_SECRET` is set correctly and matches your Zadarma account.

### Issue: Webhooks not arriving

**Solutions:**
1. Check that `BACKEND_URL` is publicly accessible (test with: `curl https://your-domain.com/api/v1/zadarma/webhook`)
2. Verify the webhook URL is set correctly in Zadarma Dashboard
3. Check that your server is running and accessible
4. For local development, make sure ngrok is running and the URL is updated

### Issue: "No agent found" errors

**Solution:** Make sure you've assigned a phone number to an agent in the WeeVoice dashboard.

### Issue: PBX extension not created

**Solution:** 
1. Check that `ZADARMA_API_KEY` and `ZADARMA_API_SECRET` are correct
2. Check your backend logs for API errors
3. Verify you have permissions to create PBX extensions in your Zadarma account

## Testing

1. **Test webhook endpoint:**
   ```bash
   curl https://your-domain.com/api/v1/zadarma/webhook?zd_echo=test123
   # Should return: test123
   ```

2. **Test with a real call:**
   - Call your Zadarma phone number
   - Check backend logs for webhook events
   - Verify the call is created in your database

## Security Notes

- **Never commit `.env` file to version control**
- Keep `ZADARMA_API_SECRET` secure
- Use HTTPS for `BACKEND_URL` in production
- Webhook signatures are automatically verified for security

## Next Steps

After setting up your environment:

1. ✅ Set `ZADARMA_API_KEY` and `ZADARMA_API_SECRET`
2. ✅ Set `BACKEND_URL` to your public HTTPS URL
3. ✅ Configure webhook URLs in Zadarma Dashboard
4. ✅ Assign a phone number to an agent in WeeVoice
5. ✅ **Configure incoming call scenario in Zadarma Dashboard** (IMPORTANT - see below)
6. ✅ Test with a real phone call

### ⚠️ IMPORTANT: Configure Incoming Call Scenario

**After creating a PBX extension, you MUST configure the incoming call scenario in Zadarma Dashboard:**

1. Go to **My PBX** → **Incoming Calls and IVR**
2. Click on **"Without pressing"** scenario
3. Add your extension (e.g., 100) to the scenario
4. Set ring time (30-60 seconds)
5. Save changes

**Without this step, calls will get a busy tone even though the extension exists.**

For detailed instructions, see: **[ZADARMA_INCOMING_CALL_SCENARIO_SETUP.md](./ZADARMA_INCOMING_CALL_SCENARIO_SETUP.md)**

For more details on webhooks, see: `docs/ZADARMA_WEBHOOK_CONFIGURATION.md`

