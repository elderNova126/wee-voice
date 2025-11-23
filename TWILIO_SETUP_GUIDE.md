# Twilio SIP Trunk Setup Guide for Zadarma → Railway

## 🔄 Call Flow

```
Caller → Zadarma (+3242833288) → Twilio SIP Trunk → Twilio Webhook → Railway WebSocket → Agent
```

## ✅ Step-by-Step Configuration

### Step 1: Get Your Twilio SIP URI

1. Go to **Twilio Console** → **Elastic SIP Trunking** → **Trunks**
2. Click on your trunk (or create a new one)
3. Go to **Origination** tab
4. Find your **SIP Domain** (e.g., `weevoice.pstn.twilio.com`)
5. Your **SIP URI** format is: `sip:+3242833288@weevoice.pstn.twilio.com`
   - Replace `+3242833288` with your Zadarma phone number
   - Replace `weevoice.pstn.twilio.com` with your actual SIP domain

**Important:** This is the URI you'll configure in Zadarma's PBX to forward calls TO Twilio.

---

### Step 2: Configure Twilio Origination (Accept Calls from Zadarma)

1. In your **Twilio Trunk** → **Origination** tab
2. Under **IP Access Control List**, click **"Create new IP ACL"**
3. Name it: `Zadarma-IPs`
4. Add these IP ranges (one by one):
   ```
   185.45.152.0/24
   185.45.154.0/24
   185.45.155.0/24
   195.122.19.0/27
   31.31.222.192/27
   15.235.128.64/28
   ```
5. Click **Save**
6. Select this IP ACL in the **Origination** tab
7. **DO NOT add any Origination URLs** - leave it empty or remove any you added

---

### Step 3: Configure Twilio Call Control (Forward to Railway)

1. In your **Twilio Trunk** → **Origination** tab
2. Under **"Call Control Configuration"**, select **"TwiML Bin"** or **"Webhook"**
3. **Option A: Use Webhook (Recommended)**
   - Select **"Webhook"**
   - Enter: `https://weevoice-web-production.up.railway.app/api/v1/twilio/voice`
   - Method: `POST`
   - Click **Save**

4. **Option B: Use TwiML Bin (Alternative)**
   - Go to **Developer Tools** → **TwiML Bins**
   - Click **"Create new TwiML Bin"**
   - Name: `Forward-to-Railway`
   - Paste this code:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
       <Connect>
           <Stream url="wss://weevoice-web-production.up.railway.app/api/v1/ws/voice/1">
           </Stream>
       </Connect>
   </Response>
   ```
   - **Note:** Replace `1` with your actual `agent_id`
   - Click **Save**
   - Copy the TwiML URL (looks like: `https://handler.twilio.com/twiml/EHxxxx...`)
   - Go back to **Trunk** → **Origination** → Select **"TwiML Bin"** → Choose your bin

**⚠️ Important:** Option A (Webhook) is recommended because it automatically looks up the `agent_id` based on the called phone number.

---

### Step 4: Configure Zadarma PBX

1. Go to **Zadarma Dashboard** → **My PBX** → **Extensions**
2. Find the extension for phone number `+3242833288`
3. Go to **"Call Forwarding"** or **"External Server (SIP URI)"**
4. Enter the Twilio SIP URI:
   ```
   sip:+3242833288@weevoice.pstn.twilio.com
   ```
   - Replace `+3242833288` with your actual Zadarma number
   - Replace `weevoice.pstn.twilio.com` with your Twilio SIP domain
5. Click **Save**

---

### Step 5: Set Up API Key in Railway

1. Go to **Railway Dashboard** → Your App → **Variables**
2. Add a new environment variable:
   - **Key:** `TWILIO_API_KEY`
   - **Value:** Your API key (create one in your Railway app: Settings → API Keys)
3. **OR** use an existing API key from your account
4. Click **Save** and **Redeploy** your app

**Note:** The webhook will use this API key to authenticate the WebSocket connection to Railway.

---

### Step 6: Verify Phone Number Configuration

1. In your Railway app, make sure:
   - Phone number `+3242833288` exists in the `phone_numbers` table
   - The phone number has `status = 'active'`
   - The phone number has an `agent_id` assigned
   - The agent exists and is active

2. Check in your database:
   ```sql
   SELECT id, phone_number, agent_id, status 
   FROM phone_numbers 
   WHERE phone_number LIKE '%3242833288%';
   ```

---

### Step 7: Test the Call Flow

1. Call your Zadarma number `+3242833288` from any phone
2. Check **Twilio Console** → **Monitor** → **Logs** → **Calls**
   - You should see an incoming call
   - Check the call details for webhook requests
3. Check **Railway Logs**:
   - You should see: `📞 Twilio webhook received: Called=+3242833288...`
   - You should see: `✅ Found agent X for phone +3242833288`
   - You should see: `🔗 Forwarding to WebSocket: wss://...`
   - You should see: `WebSocket connected: ...`

---

## 🔍 Troubleshooting

### Issue: "No Called number in Twilio webhook"
**Solution:** Check that Twilio is sending the `Called` parameter. Verify in Twilio Console → Monitor → Logs → Calls → Webhook requests.

### Issue: "Phone number not found in database"
**Solution:** 
- Verify the phone number exists in `phone_numbers` table
- Check that the number format matches (with/without +, spaces, etc.)
- Ensure `status = 'active'`

### Issue: "Phone number has no agent_id assigned"
**Solution:**
- Go to your Railway app → Phone Numbers page
- Assign an agent to the phone number

### Issue: "Calls ring then drop"
**Possible causes:**
1. **Webhook not configured:** Check Twilio Trunk → Origination → Call Control Configuration
2. **Webhook URL wrong:** Should be `https://weevoice-web-production.up.railway.app/api/v1/twilio/voice`
3. **API key missing:** Set `TWILIO_API_KEY` in Railway environment variables
4. **Agent not found:** Verify `agent_id` exists and agent is active
5. **WebSocket connection fails:** Check Railway logs for WebSocket errors

### Issue: "No backend logs, no Twilio logs"
**Possible causes:**
1. **Zadarma not forwarding:** Check Zadarma PBX configuration
2. **Twilio not receiving:** Check Twilio Origination IP ACL (Zadarma IPs whitelisted)
3. **SIP URI wrong:** Verify the SIP URI format: `sip:+3242833288@weevoice.pstn.twilio.com`

---

## 📋 Quick Checklist

- [ ] Twilio SIP Trunk created
- [ ] Twilio Origination IP ACL created with Zadarma IPs
- [ ] Twilio Origination Call Control set to Webhook: `https://weevoice-web-production.up.railway.app/api/v1/twilio/voice`
- [ ] Twilio SIP URI obtained: `sip:+3242833288@weevoice.pstn.twilio.com`
- [ ] Zadarma PBX configured with Twilio SIP URI
- [ ] Phone number exists in Railway database with `agent_id` assigned
- [ ] `TWILIO_API_KEY` set in Railway environment variables
- [ ] Railway app redeployed
- [ ] Test call made and verified in logs

---

## 🔗 Important URLs

- **Twilio Webhook Endpoint:** `https://weevoice-web-production.up.railway.app/api/v1/twilio/voice`
- **Railway WebSocket:** `wss://weevoice-web-production.up.railway.app/api/v1/ws/voice/{agent_id}`
- **Twilio Console:** https://console.twilio.com
- **Zadarma Dashboard:** https://zadarma.com

---

## 💡 Key Points

1. **Origination URLs are NOT needed** - those are for calls TO Twilio (which Zadarma will do via SIP)
2. **Termination is NOT needed** - we're using WebSocket, not SIP termination
3. **The webhook automatically looks up `agent_id`** based on the called phone number
4. **Make sure your phone number has `agent_id` assigned** in the database

---

## 🆘 Need Help?

If calls are still not working:
1. Check **Twilio Console** → **Monitor** → **Logs** → **Calls** for detailed call logs
2. Check **Railway Logs** for webhook and WebSocket connection logs
3. Verify all steps in the checklist above
4. Test the webhook manually using curl:
   ```bash
   curl -X POST https://weevoice-web-production.up.railway.app/api/v1/twilio/voice \
     -d "Called=+3242833288" \
     -d "Caller=+1234567890" \
     -d "CallSid=test123"
   ```

Expected response: TwiML XML with `<Stream>` tag pointing to your WebSocket URL.

