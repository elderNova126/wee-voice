# Zadarma Call Debugging Guide

## Problem: Calls Not Working After Webhook Configuration

You've successfully configured the webhook URL, but when calling, nothing happens.

## Step-by-Step Debugging

### Step 1: Verify Webhooks Are Arriving

When you make a call, check if Zadarma is sending webhooks to your backend.

#### Check Railway Logs

1. Go to Railway dashboard
2. Select your backend service
3. Go to **Deployments** → **Latest** → **Logs**
4. Make a test call from your phone
5. Watch the logs immediately

**What to look for:**
```
INFO: Zadarma webhook received: NOTIFY_START
INFO: Full webhook data: {...}
```

**If you see nothing:**
- Zadarma is not sending webhooks
- Check webhook URL configuration in Zadarma
- Verify the phone number is configured to use webhooks

**If you see webhooks:**
- Continue to Step 2

---

### Step 2: Check Phone Number Configuration in Zadarma

The phone number must be configured to forward calls to your webhook.

#### Option A: PBX Configuration (Recommended)

1. Log in to Zadarma: https://my.zadarma.com
2. Go to **PBX** → **Internal Numbers** (or **Extensions**)
3. Find your extension (should match `ZADARMA_SIP_LOGIN="667776"`)
4. Check the extension settings:
   - **Forwarding**: Should be set to "Webhook"
   - **Webhook URL**: Should be your webhook URL
   - **Caller ID**: Should match your phone number

#### Option B: Direct Number Configuration

1. Go to **Numbers** → Select your number (`+3242833288`)
2. Check **Settings** or **Forwarding**:
   - Should forward to your extension or webhook
   - Webhook URL should be configured

#### Option C: Check via API

Test if your extension is configured correctly:

```powershell
# Get extension info
$apiKey = "b46820d6c0993ceb2258"
$apiSecret = "d7f384a4d60c093d0d53"
$extension = "534002-100"

# Generate signature (Zadarma format: HMAC-SHA1(endpoint + params + MD5(params)))
# Note: endpoint is the URL path, not HTTP method
$endpoint = "/v1/pbx/internal/info/"
$params = "extension=$extension"

# Step 1: Compute MD5 of params
$md5 = New-Object System.Security.Cryptography.MD5CryptoServiceProvider
$paramsBytes = [System.Text.Encoding]::UTF8.GetBytes($params)
$md5Hash = $md5.ComputeHash($paramsBytes)
$md5Hex = [System.BitConverter]::ToString($md5Hash) -replace '-', '' -replace ' ', '' | ForEach-Object { $_.ToLower() }

# Step 2: Concatenate: endpoint + params + md5_hash
$signatureString = "$endpoint$params$md5Hex"

# Step 3: Compute HMAC-SHA1
$hmac = New-Object System.Security.Cryptography.HMACSHA1
$hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($apiSecret)
$hash = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($signatureString))

# Step 4: Get hex digest (not base64)
$signature = [System.BitConverter]::ToString($hash) -replace '-', '' -replace ' ', '' | ForEach-Object { $_.ToLower() }

# Zadarma uses Authorization header: "api_key:signature"
$headers = @{
    "Authorization" = "$apiKey`:$signature"
}

$response = Invoke-RestMethod -Uri "https://api.zadarma.com/v1/pbx/internal/info/?extension=$extension" -Headers $headers
$response | ConvertTo-Json
```

**Check the response:**
- `forwarding` should be `"webhook"`
- `webhook_url` should be your webhook URL

---

### Step 3: Verify Phone Number in Database

Check if your phone number is stored correctly in the database:

```powershell
# First, get your API token
$loginBody = @{
    email = "your-email@example.com"
    password = "your-password"
} | ConvertTo-Json

$tokenResponse = Invoke-RestMethod -Method POST `
    -Uri "https://weevoice-api-production.up.railway.app/api/v1/auth/login" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $loginBody

$token = $tokenResponse.access_token
$headers = @{
    "Authorization" = "Bearer $token"
}

# Get phone numbers
$phones = Invoke-RestMethod -Uri "https://weevoice-api-production.up.railway.app/api/v1/phone-numbers/" -Headers $headers
$phones | ConvertTo-Json
```

**Verify:**
- Phone number `+3242833288` exists
- It has an `agent_id` assigned
- Status is active

---

### Step 4: Test Webhook Manually

Simulate a call webhook to see if your backend processes it correctly:

```powershell
$webhookUrl = "https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook"

# Generate signature
$apiSecret = "d7f384a4d60c093d0d53"
$body = @{
    event = "NOTIFY_START"
    call_id = "TEST_$(Get-Date -Format 'yyyyMMddHHmmss')"
    caller_id = "+33123456789"
    called_did = "+3242833288"
    pbx_call_id = "TEST_CALL_001"
} | ConvertTo-Json

# Generate signature for webhook
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$hmac = New-Object System.Security.Cryptography.HMACSHA1
$hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($apiSecret)
$hash = $hmac.ComputeHash($bodyBytes)
$signature = [System.Convert]::ToBase64String($hash)

$headers = @{
    "Content-Type" = "application/json"
    "X-Zadarma-Signature" = $signature
}

try {
    $response = Invoke-RestMethod -Method POST `
        -Uri $webhookUrl `
        -Headers $headers `
        -Body $body `
        -SkipCertificateCheck
    
    Write-Host "✅ Webhook processed successfully!" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}
```

**Check the response:**
- Should return audio endpoints (`input_url`, `output_url`)
- Should create a call record in the database

---

### Step 5: Check Zadarma Call Logs

1. Log in to Zadarma: https://my.zadarma.com
2. Go to **Statistics** → **Calls** (or **Call History**)
3. Find your test call
4. Check:
   - **Status**: Should show "Answered" or "Completed"
   - **Duration**: Should show call duration
   - **Destination**: Should show your extension or webhook

**If call shows as "No Answer" or "Failed":**
- Extension/webhook not configured correctly
- Webhook URL not accessible
- Check Zadarma error messages

---

### Step 6: Verify Extension Forwarding

Your extension (`667776`) must forward calls to the webhook.

#### Check Extension Settings:

1. **PBX** → **Internal Numbers** → Extension `667776`
2. Settings should be:
   ```
   Forwarding: Webhook
   Webhook URL: https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
   ```

#### Configure Extension via API:

If not configured, set it up:

```powershell
$apiKey = "b46820d6c0993ceb2258"
$apiSecret = "d7f384a4d60c093d0d53"
$extension = "667776"
$webhookUrl = "https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook"

# Prepare request
$endpoint = "/v1/pbx/internal/set/"
# URL encode the webhook URL first
Add-Type -AssemblyName System.Web
$encodedWebhookUrl = [System.Web.HttpUtility]::UrlEncode($webhookUrl)
$params = "extension=$extension&forwarding=webhook&webhook_url=$encodedWebhookUrl&display_name=VoiceAgent"

# Generate signature (Zadarma format: HMAC-SHA1(endpoint + params + MD5(params)))
# Step 1: Compute MD5 of params
$md5 = New-Object System.Security.Cryptography.MD5CryptoServiceProvider
$paramsBytes = [System.Text.Encoding]::UTF8.GetBytes($params)
$md5Hash = $md5.ComputeHash($paramsBytes)
$md5Hex = [System.BitConverter]::ToString($md5Hash) -replace '-', '' -replace ' ', '' | ForEach-Object { $_.ToLower() }

# Step 2: Concatenate: endpoint + params + md5_hash
$signatureString = "$endpoint$params$md5Hex"

# Step 3: Compute HMAC-SHA1
$hmac = New-Object System.Security.Cryptography.HMACSHA1
$hmac.Key = [System.Text.Encoding]::UTF8.GetBytes($apiSecret)
$hash = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($signatureString))

# Step 4: Get hex digest (not base64)
$signature = [System.BitConverter]::ToString($hash) -replace '-', '' -replace ' ', '' | ForEach-Object { $_.ToLower() }

# Zadarma uses Authorization header: "api_key:signature"
$headers = @{
    "Authorization" = "$apiKey`:$signature"
    "Content-Type" = "application/x-www-form-urlencoded"
}

$body = $params  # Use the same params string for the body

$response = Invoke-RestMethod -Method POST `
    -Uri "https://api.zadarma.com/v1/pbx/internal/set/" `
    -Headers $headers `
    -Body $body

$response | ConvertTo-Json
```

---

### Step 7: Check Number Assignment

Your phone number must be assigned to your extension:

1. **Numbers** → Select `+3242833288`
2. Check **Settings**:
   - **Assigned to**: Should be your extension (`667776`)
   - Or **Forwarding**: Should forward to extension or webhook

---

## Common Issues and Solutions

### Issue 1: No Webhooks Arriving

**Symptoms:**
- No logs in Railway when calling
- Call shows in Zadarma but no webhook received

**Solutions:**
1. Verify webhook URL is saved in Zadarma (both "About PBX calls" and "About events")
2. Check extension forwarding is set to "Webhook"
3. Verify webhook URL uses HTTPS
4. Check Zadarma call logs for errors

### Issue 2: Webhooks Arriving But No Call Created

**Symptoms:**
- Webhook logs appear in Railway
- But no call record in database

**Solutions:**
1. Check webhook logs for errors
2. Verify phone number matching logic
3. Check if agent is assigned to phone number
4. Look for "No agent found" warnings in logs

### Issue 3: Call Created But No Audio

**Symptoms:**
- Call record created
- But no audio streaming

**Solutions:**
1. Check audio bridge initialization in logs
2. Verify audio endpoints are returned to Zadarma
3. Check if Gemini API is responding
4. Verify `GOOGLE_API_KEY` is set in Railway

### Issue 4: Extension Not Forwarding

**Symptoms:**
- Call doesn't reach webhook
- Extension shows as "Not configured"

**Solutions:**
1. Configure extension forwarding via API (see Step 6)
2. Or configure manually in Zadarma dashboard
3. Verify extension exists and is active

---

## Quick Diagnostic Script

Run this to check everything at once:

```powershell
Write-Host "=== Zadarma Call Debugging ===" -ForegroundColor Cyan
Write-Host ""

# 1. Test webhook endpoint
Write-Host "1. Testing webhook endpoint..." -ForegroundColor Yellow
$webhookUrl = "https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook?zd_echo=test123"
try {
    $response = Invoke-RestMethod -Uri $webhookUrl -SkipCertificateCheck
    Write-Host "✅ Webhook endpoint is accessible" -ForegroundColor Green
} catch {
    Write-Host "❌ Webhook endpoint error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""

# 2. Check phone numbers in database
Write-Host "2. Checking phone numbers in database..." -ForegroundColor Yellow
# (Requires authentication - add your login code here)

Write-Host ""

# 3. Test manual webhook
Write-Host "3. Testing manual webhook..." -ForegroundColor Yellow
# (Use the manual webhook test from Step 4)

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Make a test call from your phone" -ForegroundColor White
Write-Host "2. Check Railway logs immediately" -ForegroundColor White
Write-Host "3. Check Zadarma call logs" -ForegroundColor White
Write-Host "4. Verify extension forwarding in Zadarma" -ForegroundColor White
```

---

## What to Check in Railway Logs

When you make a call, you should see this sequence:

1. **NOTIFY_START**:
   ```
   INFO: Zadarma webhook received: NOTIFY_START
   INFO: Looking up agent for phone number: +3242833288
   INFO: Found agent X for phone +3242833288
   INFO: Created call record: X
   INFO: Audio bridge created
   ```

2. **NOTIFY_ANSWER** (after call is answered):
   ```
   INFO: Zadarma webhook received: NOTIFY_ANSWER
   INFO: Call X status updated to in_progress
   ```

3. **NOTIFY_END** (when call ends):
   ```
   INFO: Zadarma webhook received: NOTIFY_END
   INFO: Call X ended, stopping audio bridge
   ```

**If any step is missing, that's where the problem is.**

---

## Next Steps

1. ✅ Make a test call
2. ✅ Check Railway logs immediately
3. ✅ Check Zadarma call logs
4. ✅ Verify extension forwarding
5. ✅ Test manual webhook (Step 4)

If webhooks are arriving but calls aren't working, the issue is likely in:
- Phone number matching
- Agent assignment
- Audio bridge initialization

If webhooks aren't arriving, the issue is in:
- Zadarma extension configuration
- Webhook URL configuration
- Number assignment

