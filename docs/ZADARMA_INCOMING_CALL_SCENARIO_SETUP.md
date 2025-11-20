# Zadarma Incoming Call Scenario Setup

## Problem: Busy Tone When Calling

If you hear a busy tone immediately when calling your Zadarma virtual number, even though the call shows as "INITIATED" and "in_progress" in the call history, it means **the incoming call scenario is not configured** in Zadarma's PBX.

## Why This Happens

When you create a PBX extension (e.g., extension 100 for your AI agent), Zadarma creates the extension but **does NOT automatically add it to the incoming call scenario**. 

By default, calls go to the "Main Menu" → "Without pressing" scenario. If this scenario has no extensions assigned, Zadarma immediately returns a busy signal.

## Solution: Configure Incoming Call Scenario

### Step 1: Log in to Zadarma Dashboard

1. Go to [https://zadarma.com](https://zadarma.com)
2. Log in to your account

### Step 2: Navigate to Incoming Calls Configuration

1. Go to **My PBX** → **Incoming Calls and IVR**
2. You will see the **Main Menu** (or similar name)

### Step 3: Configure the Default Scenario

1. Click on the scenario called **"Without pressing"** (this is the default scenario that triggers when someone calls without pressing any IVR keys)
2. In that scenario, you need to **add your extensions**:

   **For AI Agent Setup:**
   - Click **"Add Extension"** or **"Add Step"**
   - Select extension **100** (or your AI agent extension number)
   - Set ring time: **30-60 seconds** (or as needed)
   - Set action: **Ring extension**
   - Save

   **Optional: Add Fallback Extensions**
   - Add extension **200** as the next step (if 100 doesn't answer)
   - Add extension **300** if needed
   - Configure ring order (sequential or simultaneous)

3. **Save the changes**

### Step 4: Verify Extension Status (CRITICAL)

1. Go to **My PBX** → **Extensions**
2. **VERIFY that extension 100 shows as ONLINE/REGISTERED (green status)**
3. **If it's OFFLINE (red), the call will ring but NEVER be answered**

**Why This Matters:**
- The webhook (`NOTIFY_START`) only notifies your server about the call
- **The actual call connection happens through SIP**
- If the extension is offline, Zadarma cannot connect the call
- You will see `NOTIFY_START` webhooks, but the call will keep ringing

**To Register the Extension:**
- You need a SIP client that registers to the extension
- SIP Login: `{PBX_NUMBER}-{EXTENSION}` (e.g., `32480206645-100`)
- SIP Password: Check in **My PBX** → **Extensions** → **100** → **Password**
- SIP Server: `sip.zadarma.com` (or regional equivalent like `sip-eu.zadarma.com`)
- Port: 5060 (UDP)

**Current Status:**
- ✅ Extension created via API
- ✅ Webhook configured
- ✅ Incoming call scenario configured
- ❌ **SIP client NOT implemented** (this is why calls ring but don't answer)

### Step 5: Test

1. Call your Zadarma virtual number from a physical phone
2. The call should now ring to extension 100 instead of giving a busy tone
3. Check your backend logs to confirm the webhook is receiving the call

## Alternative: Configure via API (If Available)

If Zadarma provides an API endpoint for configuring incoming call scenarios, we can add automatic configuration. Currently, this must be done manually in the dashboard.

## Quick Checklist

- [ ] Extension 100 is created and shows as online in Zadarma dashboard
- [ ] "Without pressing" scenario has extension 100 added
- [ ] Ring time is set (30-60 seconds recommended)
- [ ] Changes are saved
- [ ] Extension shows green/online status
- [ ] Test call works (no busy tone)

## Troubleshooting

### Still Getting Busy Tone?

1. **Check extension status:**
   - Go to **My PBX** → **Extensions**
   - Extension must show **green/online** status
   - If offline, check SIP registration credentials

2. **Verify scenario configuration:**
   - Go to **My PBX** → **Incoming Calls and IVR**
   - Check that "Without pressing" scenario has at least one extension
   - Verify the extension number matches (e.g., 100)

3. **Check call history:**
   - Go to **Statistics** → **Call History** in Zadarma dashboard
   - Look for the call and check the rejection reason
   - Common reasons: "No answer", "Extension not found", "Extension offline"

4. **Verify webhook configuration:**
   - Go to **Settings** → **Integrations** → **API** → **Event Notifications**
   - Ensure webhook URL is set: `{BACKEND_URL}/api/v1/zadarma/webhook`
   - Test webhook with: `curl {BACKEND_URL}/api/v1/zadarma/webhook?zd_echo=test`

### Extension Shows Offline

If extension 100 shows as offline:

1. **Check SIP credentials:**
   - Login format: `{PBX_NUMBER}-100` (e.g., if PBX number is 32480206645, login is `32480206645-100`)
   - Password: Check in **My PBX** → **Extensions** → **100** → **Password**
   - Server: `sip.zadarma.com` (or regional equivalent like `sip-eu.zadarma.com`)

2. **Verify AI server is running:**
   - Check that your backend service is running
   - Check logs for SIP registration errors

3. **Check firewall/network:**
   - Ensure UDP ports 5060 (SIP) and RTP ports are open
   - Check if your server can reach Zadarma SIP servers

## Additional Configuration Options

### Simultaneous Ringing

If you want calls to ring multiple extensions at once:

1. In the scenario, add multiple extensions
2. Set delay between them to **0 seconds**
3. Or create a **Call Group** in Zadarma and add the group to the scenario

### IVR Menu

If you want to use an IVR menu:

1. Create menu options in **My PBX** → **Incoming Calls and IVR**
2. For each menu option, create a scenario
3. Each scenario should route to the appropriate extension
4. Make sure at least one scenario (including "Without pressing") has extensions assigned

## Related Documentation

- [PBX Extension Environment Setup](./PBX_EXTENSION_ENV_SETUP.md)
- [Zadarma Webhook Configuration](./ZADARMA_WEBHOOK_CONFIGURATION.md)

## Issue: Phone Rings But No Audio/Greeting

If the phone rings but you don't hear anything (including the greeting), this means:

**The call is being routed correctly, but the audio connection isn't established.**

### Root Cause

PBX extensions with `forwarding: "webhook"` configuration:
- ✅ Webhooks work for call control (NOTIFY_START, NOTIFY_END, etc.)
- ❌ Audio still needs to flow through **SIP connection** to the extension

The webhook only handles call events, not audio streaming. For audio to work, you need:

1. **SIP Client Registration**: A SIP client must register to the extension
2. **RTP Audio Streaming**: Audio flows via RTP through the SIP connection
3. **Audio Bridge**: Bridge between SIP audio and Gemini API

### Current Status

The current implementation:
- ✅ Creates PBX extensions
- ✅ Handles webhook events (call control)
- ❌ **Missing SIP client for audio streaming**

### Solutions

#### Option 1: Use SIP Connection (Recommended)

Configure a SIP client to register to your extension:

1. **Get Extension SIP Credentials:**
   - Go to **My PBX** → **Extensions** → Your extension (e.g., 100)
   - Note the SIP login and password
   - Format: Login = `{PBX_NUMBER}-{EXTENSION}` (e.g., `32480206645-100`)
   - Server: `sip.zadarma.com` or regional equivalent

2. **Set Up SIP Client:**
   - Use a SIP client library (e.g., `pjsua2` for Python)
   - Register to the extension using the credentials
   - Handle incoming RTP audio streams
   - Bridge audio between SIP and Gemini API

3. **Implementation Required:**
   - SIP client registration
   - RTP audio handling
   - Audio format conversion (PCM16, 16kHz for input, 24kHz for output)
   - Bidirectional audio streaming

#### Option 2: Change Extension Forwarding (Alternative)

Instead of webhook forwarding, you could:
- Use direct SIP forwarding to a SIP endpoint
- Configure the extension to forward to a SIP URI
- Handle audio entirely through SIP

#### Option 3: Use Zadarma's Audio Streaming API (If Available)

Check if Zadarma provides an HTTP-based audio streaming API for webhook-forwarded extensions. This would allow audio without SIP.

### Temporary Workaround

Until SIP client is implemented:
1. The call will ring and be answered
2. Call events will be logged correctly
3. But no audio will be transmitted
4. The call will appear in call history but with no audio/transcript

### Next Steps

To enable audio:
1. Implement SIP client registration
2. Set up RTP audio handling
3. Bridge SIP audio with Gemini API
4. Test end-to-end audio flow

**Note:** This requires significant development work. The webhook-based approach works for call control but not for audio streaming with PBX extensions.

## Support

If you continue to experience issues after following this guide:

1. Check Zadarma's call history for detailed error messages
2. Review backend logs for webhook events
3. Verify all environment variables are set correctly
4. Contact Zadarma support if the issue is with PBX configuration

