# Zadarma Webhook Configuration Guide

## Where to Configure Webhooks in Zadarma

You're looking at the **Event Notifications** page in Zadarma. This is the correct place to configure webhooks.

## Step-by-Step Configuration

### Step 1: Echo Verification (Already Handled)

Zadarma requires echo verification to test the webhook endpoint. **This is already implemented** in our backend.

Our webhook endpoint automatically handles Zadarma's echo test (GET request with `?zd_echo=<value>`). You can **skip the PHP code requirement** - it's not needed for our FastAPI backend.

### Step 2: Configure Webhook URLs

In the **Event Notifications** page, you'll see two fields:

1. **"About PBX calls"** - This is for PBX-related call events
2. **"About events"** - This is for general events

#### Which URL to Use?

**Use the same URL for both fields:**

```
https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
```

**Important**: 
- ✅ Use **HTTPS** (not HTTP)
- ✅ Include the full path: `/api/v1/zadarma/webhook`
- ✅ No trailing slash

### Step 3: Enter the URLs

1. **"About PBX calls"** field:
   ```
   https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
   ```

2. **"About events"** field:
   ```
   https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
   ```

3. Click **Save** or **Update**

### Step 4: Select Events (If Available)

If Zadarma shows checkboxes or options to select which events to receive, make sure these are enabled:

- ✅ **NOTIFY_START** - Incoming call initiated
- ✅ **NOTIFY_ANSWER** - Call was answered  
- ✅ **NOTIFY_END** - Call ended
- ✅ **NOTIFY_RECORD** - Call recording available (optional)

### Step 5: Verify Configuration

After saving, Zadarma may test the webhook URL. Check:

1. **Zadarma Dashboard**: Look for a success message or test result
2. **Railway Logs**: Check if any test requests arrive
3. **Make a Test Call**: Call your number and check Railway logs

---

## What Events We Handle

Our backend handles these Zadarma webhook events:

| Event | Description | Action |
|-------|-------------|--------|
| `NOTIFY_START` | Incoming call initiated | Creates call record, starts audio bridge |
| `NOTIFY_ANSWER` | Call was answered | Updates call status to "in_progress" |
| `NOTIFY_END` | Call ended | Stops audio bridge, finalizes call |
| `NOTIFY_RECORD` | Recording available | Downloads and stores recording |
| `NOTIFY_OUT_START` | Outgoing call started | Creates call record |
| `NOTIFY_OUT_END` | Outgoing call ended | Finalizes call |

---

## Testing the Configuration

### Test 1: Manual Webhook Test

Use PowerShell to test if the webhook endpoint is accessible:

```powershell
$webhookUrl = "https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook"

$body = @{
    event = "NOTIFY_START"
    call_id = "TEST_$(Get-Date -Format 'yyyyMMddHHmmss')"
    caller_id = "+33123456789"
    called_did = "+3242833288"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri $webhookUrl `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body `
    -SkipCertificateCheck
```

**Expected Result**: Should return a response with `call_id` and audio endpoints.

### Test 2: Real Phone Call

1. Call your Zadarma phone number from a real phone
2. Check Railway logs immediately
3. You should see:
   ```
   INFO: Zadarma webhook received: NOTIFY_START
   INFO: Full webhook data: {...}
   ```

---

## Troubleshooting

### Issue: "No signal in backend"

**Possible causes:**

1. **Wrong URL format**
   - ❌ `http://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook` (HTTP)
   - ✅ `https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook` (HTTPS)

2. **URL not saved in Zadarma**
   - Go back to Event Notifications page
   - Verify URLs are saved (not empty)
   - Click Save again

3. **Railway service not running**
   - Check Railway dashboard
   - Verify service is deployed and running
   - Check service logs

4. **Webhook signature verification failing**
   - Verify `ZADARMA_API_SECRET` is set in Railway environment variables
   - Check Railway logs for "Invalid signature" errors

### Issue: "Webhook test fails"

If Zadarma's webhook test fails:

1. **Check Railway logs** for the test request
2. **Verify HTTPS is working**: Test the URL manually (see Test 1 above)
3. **Check CORS settings**: Railway should allow all requests by default
4. **Verify endpoint path**: Must be exactly `/api/v1/zadarma/webhook`

### Issue: "Events not arriving"

1. **Check event selection**: Make sure events are enabled in Zadarma
2. **Check webhook URL**: Verify it's set in both fields
3. **Check Railway logs**: Look for incoming requests
4. **Test manually**: Use Test 1 above to verify endpoint works

---

## Alternative: Configure via API

If you prefer to configure webhooks programmatically, you can use the Zadarma API. However, the dashboard method above is usually easier.

---

## Next Steps After Configuration

1. ✅ **Save webhook URLs** in Zadarma
2. ✅ **Test webhook endpoint** manually (see Test 1)
3. ✅ **Make a test call** from your phone
4. ✅ **Check Railway logs** for incoming webhooks
5. ✅ **Verify call is created** in your application

---

## Important Notes

- **HTTPS Required**: Zadarma requires HTTPS for webhooks. Never use HTTP.
- **Same URL for Both Fields**: Use the same webhook URL for "About PBX calls" and "About events"
- **No PHP Code Needed**: The PHP echo code is for PHP backends. Our FastAPI backend handles verification automatically.
- **Keep Railway Running**: The backend must be running for webhooks to work
- **Check Logs**: Railway logs will show all incoming webhook requests

---

## Quick Reference

**Webhook URL to use:**
```
https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
```

**Where to configure:**
- Zadarma Dashboard → Integrations → API → Event Notifications
- Or: Zadarma Dashboard → Settings → Webhooks

**Events to enable:**
- NOTIFY_START
- NOTIFY_ANSWER
- NOTIFY_END
- NOTIFY_RECORD (optional)

