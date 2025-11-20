# Comprehensive Phone Call Test Cases

This document provides complete test cases to verify phone call functionality end-to-end without requiring a physical phone.

## Test Environment Setup

### Prerequisites
1. ✅ Phone number added to system (`+3242833288`)
2. ✅ Agent created and configured
3. ✅ Agent assigned to phone number
4. ✅ Backend running (`http://localhost:8000`)
5. ✅ Frontend running (`http://localhost:3000`)
6. ✅ Database accessible
7. ✅ Google API key configured
8. ✅ Zadarma credentials configured (optional for testing)

### Authentication
Most endpoints require authentication. Get your token:

**Option 1: From Browser**
1. Login to frontend (`http://localhost:3000`)
2. Open browser DevTools (F12)
3. Go to Application/Storage → Local Storage
4. Find `auth_token` or `token` key
5. Copy the token value

**Option 2: From API**

**Using curl (Linux/Mac/Git Bash):**
```bash
# Login and get token (form data, not JSON)
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your@email.com&password=your_password"
# Extract access_token from response
```

**Using PowerShell (Windows):**
```powershell
# Login and get token
$body = @{
    username = "your@email.com"
    password = "your_password"
}
$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -Body $body `
    -ContentType "application/x-www-form-urlencoded"
$token = $response.access_token
Write-Host "Token: $token"
```

**Using Token in Requests (PowerShell):**
```powershell
# Set token as environment variable (PowerShell)
$env:API_TOKEN = "your_token_here"

# Verify it's set
Write-Host "Token: $env:API_TOKEN"

# Use in requests
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}
Invoke-RestMethod -Uri "..." -Headers $headers
```

---

## Test Suite 1: Phone Number Setup & Matching

### TC-1.1: Verify Phone Number Storage
**Objective**: Ensure phone numbers are stored correctly in normalized format

**Steps**:
1. Add phone number `3242833288` via API
2. Check database for stored format

**Expected Results**:
- Phone number stored as `+3242833288` (E.164 format)
- `zadarma_number_id` populated (if Zadarma number)
- `agent_id` set if agent assigned

**API Test (PowerShell)**:
```powershell
# Add phone number (requires auth)
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
    "Content-Type" = "application/json"
}
$body = @{
    phone_number = "3242833288"
    country_code = "BE"
    agent_id = 1
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/phone-numbers/add-existing" `
    -Headers $headers `
    -Body $body
$response | ConvertTo-Json

# Debug phone numbers (requires auth)
$phones = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/phone-numbers" `
    -Headers $headers
$phones | ConvertTo-Json
```

**Verification**:
- Check response shows normalized format
- Verify `phone_number` field is `+3242833288`

---

### TC-1.2: Test Phone Number Matching Logic
**Objective**: Verify phone number matching works with various formats

**Test Cases**:
1. Exact match: `+3242833288` → `+3242833288`
2. Without +: `3242833288` → `+3242833288`
3. With 00: `003242833288` → `+3242833288`
4. Last 9 digits: `42833288` → `+3242833288` (should match)
5. Last 10 digits: `3242833288` → `+3242833288` (should match)

**API Test (PowerShell)**:
```powershell
# Test matching (requires auth)
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}

# Test without +
$match1 = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/test-match/3242833288" `
    -Headers $headers
$match1 | ConvertTo-Json

# Test with +
$match2 = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/test-match/%2B3242833288" `
    -Headers $headers
$match2 | ConvertTo-Json

# Test with 00
$match3 = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/test-match/003242833288" `
    -Headers $headers
$match3 | ConvertTo-Json
```

**Expected Results**:
- All formats should match the stored number
- Response shows matching strategy used
- Agent ID returned if match found

---

### TC-1.3: Agent Assignment Verification
**Objective**: Verify agent is correctly assigned to phone number

**Steps**:
1. Assign agent to phone number
2. Query phone number details
3. Verify agent relationship

**API Test**:
```bash
GET /api/v1/phone-numbers/
```

**Expected Results**:
- Phone number shows `agent_id`
- Agent details accessible via relationship
- Agent name/description visible in response

---

## Test Suite 2: Webhook Handling

### TC-2.1: NOTIFY_START Event Handling
**Objective**: Verify incoming call webhook is processed correctly

**Test Data**:
```json
{
  "event": "NOTIFY_START",
  "call_id": "TEST_CALL_001",
  "caller_id": "+33123456789",
  "called_did": "+3242833288",
  "pbx_call_id": "TEST_CALL_001"
}
```

**API Test (PowerShell)**:
```powershell
$body = @{
    event = "NOTIFY_START"
    call_id = "TEST_CALL_001"
    caller_id = "+33123456789"
    called_did = "+3242833288"
} | ConvertTo-Json

$headers = @{
    "Content-Type" = "application/json"
    # "X-Zadarma-Signature" = "<signature>"  # Optional
}

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers $headers `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 response
- ✅ Call record created in database
- ✅ Call status = `initiated`
- ✅ `caller_phone` = `+33123456789`
- ✅ `zadarma_call_id` = `TEST_CALL_001`
- ✅ Agent session initialized
- ✅ Audio bridge created
- ✅ Response includes audio endpoints:
  ```json
  {
    "status": "ok",
    "call_id": <id>,
    "audio": {
      "input_url": "/api/v1/phone/audio/{call_id}/input",
      "output_url": "/api/v1/phone/audio/{call_id}/output",
      "end_url": "/api/v1/phone/audio/{call_id}/end"
    }
  }
  ```

**Verification**:
- Check database: `SELECT * FROM calls WHERE zadarma_call_id = 'TEST_CALL_001'`
- Check logs for: "Created call record", "Started voice session", "Started phone audio bridge"

---

### TC-2.2: NOTIFY_ANSWER Event Handling
**Objective**: Verify call answered event updates call status

**Test Data**:
```json
{
  "event": "NOTIFY_ANSWER",
  "call_id": "TEST_CALL_001"
}
```

**API Test (PowerShell)**:
```powershell
$body = @{
    event = "NOTIFY_ANSWER"
    call_id = "TEST_CALL_001"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 response
- ✅ Call status updated to `in_progress`
- ✅ `started_at` timestamp set
- ✅ WebSocket broadcast sent

**Verification**:
- Check database: `status = 'in_progress'`
- Check Calls page updates in real-time

---

### TC-2.3: NOTIFY_END Event Handling
**Objective**: Verify call end event processes correctly

**Test Data**:
```json
{
  "event": "NOTIFY_END",
  "call_id": "TEST_CALL_001",
  "duration": 60,
  "disposition": "answered"
}
```

**API Test (PowerShell)**:
```powershell
$body = @{
    event = "NOTIFY_END"
    call_id = "TEST_CALL_001"
    duration = 60
    disposition = "answered"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 response
- ✅ Call status = `summarizing` (then `completed` after summarization)
- ✅ `ended_at` timestamp set
- ✅ Duration calculated correctly
- ✅ Cost calculated
- ✅ Audio bridge stopped
- ✅ Summarization task started
- ✅ WebSocket broadcast sent

**Verification**:
- Check database: `status = 'summarizing'` → `'completed'`
- Check `duration_seconds`, `duration_minutes`, `cost` fields
- Check logs for summarization task

---

### TC-2.4: Webhook Signature Verification
**Objective**: Verify webhook signature validation (if configured)

**Test Cases**:
1. Valid signature → Should accept
2. Invalid signature → Should reject (401)
3. Missing signature → Should accept (if dev mode)

**API Test (PowerShell)**:
```powershell
# Step 1: Generate signature
# The signature is HMAC-SHA1 of the JSON payload using ZADARMA_API_SECRET
$body = @{
    event = "NOTIFY_START"
    call_id = "TEST_SIG_001"
    caller_id = "+33123456789"
    called_did = "+3242833288"
} | ConvertTo-Json

# Get your ZADARMA_API_SECRET from .env file or environment
$secret = $env:ZADARMA_API_SECRET
if (-not $secret) {
    Write-Host "Warning: ZADARMA_API_SECRET not set. Signature validation will be skipped." -ForegroundColor Yellow
    $secret = "your_secret_here"  # Replace with actual secret
}

# Generate HMAC-SHA1 signature
$payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$secretBytes = [System.Text.Encoding]::UTF8.GetBytes($secret)
$hmac = New-Object System.Security.Cryptography.HMACSHA1
$hmac.Key = $secretBytes
$hashBytes = $hmac.ComputeHash($payloadBytes)
$signature = [System.BitConverter]::ToString($hashBytes) -replace '-', '' | ForEach-Object { $_.ToLower() }

Write-Host "Generated signature: $signature" -ForegroundColor Cyan

# Step 2: Test with valid signature
$headers = @{
    "Content-Type" = "application/json"
    "X-Zadarma-Signature" = $signature
}

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers $headers `
    -Body $body
$response | ConvertTo-Json

# Test with invalid signature
$headers = @{
    "Content-Type" = "application/json"
    "X-Zadarma-Signature" = "invalid_signature"
}

try {
    $response = Invoke-RestMethod -Method POST `
        -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
        -Headers $headers `
        -Body $body
} catch {
    Write-Host "Expected error: $($_.Exception.Message)"
    # Should return HTTP 401 if signature validation is enabled
}

# Test without signature (should work in dev mode)
$headers = @{
    "Content-Type" = "application/json"
}

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers $headers `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- Valid signature: HTTP 200
- Invalid signature: HTTP 401 (if production mode and signature validation enabled)
- Missing signature: HTTP 200 (if dev mode or signature validation disabled)

---

## Test Suite 3: Call Record Creation

### TC-3.1: Call Record Fields
**Objective**: Verify all call record fields are populated correctly

**Verification Points**:
- ✅ `id` - Auto-generated
- ✅ `user_id` - From agent
- ✅ `agent_id` - From phone number assignment
- ✅ `caller_phone` - From webhook `caller_id`
- ✅ `caller_name` - Initially set to `caller_phone`
- ✅ `zadarma_call_id` - From webhook
- ✅ `session_id` - Generated UUID
- ✅ `status` - `initiated` → `in_progress` → `completed`
- ✅ `direction` - `inbound`
- ✅ `started_at` - Set on NOTIFY_START
- ✅ `ended_at` - Set on NOTIFY_END
- ✅ `duration_seconds` - Calculated
- ✅ `cost` - Calculated

**API Test**:
```bash
GET /api/v1/calls/{call_id}
```

---

### TC-3.2: Call Record Relationships
**Objective**: Verify call record relationships work correctly

**Verification**:
- ✅ `call.agent` - Returns VoiceAgent object
- ✅ `call.user` - Returns User object
- ✅ `call.messages` - Returns CallMessage array (if any)

**API Test**:
```bash
GET /api/v1/calls/{call_id}
```

---

## Test Suite 4: Agent Session Initialization

### TC-4.1: Session Creation
**Objective**: Verify agent session is created for phone calls

**Verification Points**:
- ✅ `FrenchVoiceAgentService` initialized
- ✅ Gemini session connected
- ✅ Session ID stored in call record
- ✅ Session stored in `manager.agent_services`

**Logs to Check**:
```
"Connecting to Gemini model: ..."
"Successfully started voice session for call ..."
"Initialized phone audio bridge for call ..."
```

---

### TC-4.2: Greeting Trigger
**Objective**: Verify agent greeting is triggered on call start

**Verification Points**:
- ✅ Greeting sent to Gemini if `agent.greeting` is set
- ✅ Greeting audio queued in audio bridge
- ✅ Greeting available via output endpoint

**API Test (PowerShell)**:
```powershell
# After NOTIFY_START, wait 2 seconds, then:
Start-Sleep -Seconds 2

# Get greeting audio (no auth required)
$audio = Invoke-WebRequest `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/output"
    
# Save audio to file
$audio.Content | Set-Content -Path "greeting.pcm" -Encoding Byte
Write-Host "Audio received: $($audio.Headers.'X-Audio-Length') bytes"
```

**Expected Results**:
- Audio data returned (greeting)
- Content-Type: `audio/pcm;rate=24000`
- Audio length > 0

---

### TC-4.3: Agent Configuration
**Objective**: Verify agent configuration is applied correctly

**Verification Points**:
- ✅ System instruction from agent
- ✅ Temperature setting
- ✅ Model name
- ✅ Tools enabled
- ✅ RAG enabled (if configured)

**Logs to Check**:
```
"Initializing FrenchVoiceAgentService with API key: ..."
"Config response_modalities: ['AUDIO']"
```

---

## Test Suite 5: Audio Bridge

### TC-5.1: Audio Bridge Creation
**Objective**: Verify audio bridge is created on call start

**Verification Points**:
- ✅ `PhoneAudioBridge` instance created
- ✅ Bridge stored in `phone_audio_manager`
- ✅ Bridge `is_running` = `True`
- ✅ Gemini audio stream task started

**API Test (PowerShell)**:
```powershell
# Check audio bridge status (no auth required)
$status = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/status"
$status | ConvertTo-Json
```

**Expected Results**:
```json
{
  "status": "active",
  "call_id": "<id>",
  "zadarma_call_id": "<id>",
  "is_running": true,
  "queue_size": 0
}
```

---

### TC-5.2: Audio Input (Caller → Agent)
**Objective**: Verify caller audio is received and forwarded to Gemini

**Test Data**: PCM audio chunk (16kHz, 16-bit, mono)

**API Test (PowerShell)**:
```powershell
# Send audio to agent (requires PCM audio file)
$audioBytes = [System.IO.File]::ReadAllBytes("audio_chunk.pcm")
$headers = @{
    "Content-Type" = "audio/pcm;rate=16000"
}

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/input" `
    -Headers $headers `
    -Body $audioBytes `
    -ContentType "audio/pcm;rate=16000"
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 response
- ✅ Audio forwarded to Gemini session
- ✅ Response: `{"status": "ok", "bytes_received": <size>}`

**Verification**:
- Check logs: "Received phone audio: X bytes"
- Check Gemini receives audio chunks

---

### TC-5.3: Audio Output (Agent → Caller)
**Objective**: Verify agent audio is available for caller

**API Test (PowerShell)**:
```powershell
# Get audio from agent (no auth required)
$audio = Invoke-WebRequest `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/output"

if ($audio.StatusCode -eq 200) {
    # Save audio to file
    $audio.Content | Set-Content -Path "agent_response.pcm" -Encoding Byte
    Write-Host "Audio received: $($audio.Headers.'X-Audio-Length') bytes"
} elseif ($audio.StatusCode -eq 204) {
    Write-Host "No audio available yet"
}
```

**Expected Results**:
- ✅ HTTP 200 with audio data OR HTTP 204 (no content yet)
- ✅ Content-Type: `audio/pcm;rate=24000`
- ✅ Audio data in response body (if available)
- ✅ Headers: `X-Audio-Length`, `X-Call-ID`

**Test Flow**:
1. Send greeting trigger → Wait 2s → GET output → Should have greeting audio
2. Send user audio → Wait 2s → GET output → Should have response audio

---

### TC-5.4: Audio Bridge Cleanup
**Objective**: Verify audio bridge stops on call end

**API Test (PowerShell)**:
```powershell
# End audio streaming
$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/end"
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 response
- ✅ Bridge `is_running` = `False`
- ✅ Audio tasks cancelled
- ✅ Bridge removed from manager

**Verification**:
```bash
GET /api/v1/phone/audio/{call_id}/status
# Should return: {"status": "inactive"}
```

---

## Test Suite 6: Call State Progression

### TC-6.1: State Transitions
**Objective**: Verify call progresses through all states correctly

**State Flow**:
1. `initiated` - On NOTIFY_START
2. `in_progress` - On NOTIFY_ANSWER
3. `summarizing` - On NOTIFY_END
4. `completed` - After summarization

**API Test (PowerShell)**:
```powershell
# Step 1: NOTIFY_START
$body = @{
    event = "NOTIFY_START"
    call_id = "TEST_001"
    caller_id = "+33123456789"
    called_did = "+3242833288"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body
# Check: status = "initiated"

# Step 2: NOTIFY_ANSWER
$body = @{
    event = "NOTIFY_ANSWER"
    call_id = "TEST_001"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body | Out-Null
# Check: status = "in_progress"

# Step 3: NOTIFY_END
$body = @{
    event = "NOTIFY_END"
    call_id = "TEST_001"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body | Out-Null
# Check: status = "summarizing" → "completed"
```

**Verification**:
- Query database after each step
- Check WebSocket broadcasts

---

### TC-6.2: Duration Calculation
**Objective**: Verify call duration is calculated correctly

**Test Cases**:
1. 30 second call → `duration_seconds = 30`, `duration_minutes = 0.5`
2. 2 minute call → `duration_seconds = 120`, `duration_minutes = 2.0`
3. Call with `started_at` and `ended_at` → Duration calculated from timestamps

**Verification**:
```sql
SELECT 
  id, 
  started_at, 
  ended_at, 
  duration_seconds, 
  duration_minutes,
  (ended_at - started_at) as calculated_duration
FROM calls 
WHERE id = <call_id>;
```

---

### TC-6.3: Cost Calculation
**Objective**: Verify call cost is calculated correctly

**Formula**: `cost = duration_minutes * cost_per_minute`

**Test Cases**:
1. 1 minute call → `cost = 1.0 * 0.05 = 0.05`
2. 5 minute call → `cost = 5.0 * 0.05 = 0.25`
3. 0 duration → `cost = 0.0`

**Verification**:
```sql
SELECT duration_minutes, cost, (duration_minutes * 0.05) as expected_cost
FROM calls 
WHERE id = <call_id>;
```

---

## Test Suite 7: WebSocket Real-time Updates

### TC-7.1: Call Creation Broadcast
**Objective**: Verify call creation is broadcast to frontend

**Verification**:
- ✅ WebSocket connection established
- ✅ Call data broadcast on NOTIFY_START
- ✅ Frontend receives update
- ✅ Calls page shows new call

**Test**:
1. Open Calls page in browser
2. Open browser console (F12)
3. Trigger NOTIFY_START webhook
4. Check console for WebSocket message
5. Verify call appears in list

---

### TC-7.2: Status Update Broadcast
**Objective**: Verify status changes are broadcast in real-time

**Test Flow**:
1. NOTIFY_START → Broadcast `status: "initiated"`
2. NOTIFY_ANSWER → Broadcast `status: "in_progress"`
3. NOTIFY_END → Broadcast `status: "summarizing"` → `"completed"`

**Verification**:
- Check WebSocket messages in browser console
- Verify Calls page updates without refresh

---

### TC-7.3: Call Completion Broadcast
**Objective**: Verify call completion includes summary data

**Verification Points**:
- ✅ Summary broadcast after completion
- ✅ Sentiment included
- ✅ Action items included
- ✅ Action tags included

---

## Test Suite 8: End-to-End Simulation

### TC-8.1: Complete Call Flow Simulation
**Objective**: Simulate complete call from start to end

**Test Script (PowerShell)**:
```powershell
# 1. Start call
$callId = "TEST_$(Get-Date -Format 'yyyyMMddHHmmss')"
$body = @{
    event = "NOTIFY_START"
    call_id = $callId
    caller_id = "+33123456789"
    called_did = "+3242833288"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body

# Get call_id from response
$callIdInternal = $response.call_id
Write-Host "Call ID: $callIdInternal"

# 2. Wait for greeting
Start-Sleep -Seconds 2

# 3. Get greeting audio
$audio = Invoke-WebRequest `
    -Uri "http://localhost:8000/api/v1/phone/audio/$callIdInternal/output"
$audio.Content | Set-Content -Path "greeting.pcm" -Encoding Byte
Write-Host "Greeting audio saved"

# 4. Answer call
$body = @{
    event = "NOTIFY_ANSWER"
    call_id = $callId
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body | Out-Null

# 5. Send caller audio (simulate speaking)
# [Send multiple audio chunks if you have audio files]

# 6. Get agent responses
# [Poll output endpoint multiple times]

# 7. End call
$body = @{
    event = "NOTIFY_END"
    call_id = $callId
    duration = 60
    disposition = "answered"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body | Out-Null

# 8. Wait for summarization
Start-Sleep -Seconds 5

# 9. Verify call completed
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}
$call = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/calls/$callIdInternal" `
    -Headers $headers
$call | ConvertTo-Json
```

**Expected Results**:
- ✅ All steps complete successfully
- ✅ Call record shows complete data
- ✅ Summary generated
- ✅ Audio bridge cleaned up

---

### TC-8.2: Test Call Endpoint
**Objective**: Use the test call endpoint for quick testing

**API Test (PowerShell)**:
```powershell
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}
$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/test-call?phone_number=%2B3242833288&caller_id=%2B33123456789" `
    -Headers $headers
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ Call record created
- ✅ Audio bridge initialized
- ✅ States progress: `initiated` → `in_progress` → `completed`
- ✅ Response includes audio endpoints
- ✅ WebSocket broadcasts sent

**Verification**:
- Check Calls page for new call
- Verify call progresses through states
- Check audio endpoints are accessible

---

## Test Suite 9: Error Handling

### TC-9.1: No Agent Assigned
**Objective**: Verify error when no agent is assigned to number

**Test (PowerShell)**:
```powershell
$body = @{
    event = "NOTIFY_START"
    called_did = "+32111111111"  # Number without agent
    caller_id = "+33123456789"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 (webhook accepted)
- ✅ Response: `{"status": "error", "message": "No agent configured..."}`
- ✅ No call record created
- ✅ Logs show warning

---

### TC-9.2: Invalid Phone Number Format
**Objective**: Verify handling of invalid phone number formats

**Test Cases**:
1. Empty phone number
2. Invalid characters
3. Too short/long numbers

**Expected Results**:
- ✅ Normalization handles edge cases
- ✅ Logs show warnings
- ✅ Graceful degradation

---

### TC-9.3: Audio Bridge Not Found
**Objective**: Verify error when accessing non-existent bridge

**API Test (PowerShell)**:
```powershell
try {
    $response = Invoke-WebRequest `
        -Uri "http://localhost:8000/api/v1/phone/audio/99999/output"
} catch {
    $_.Exception.Response | ConvertTo-Json
}
```

**Expected Results**:
- ✅ HTTP 200 with error message
- ✅ Response: `{"status": "error", "message": "Call not active"}`

---

### TC-9.4: Call Record Not Found
**Objective**: Verify handling when call record doesn't exist

**Test (PowerShell)**:
```powershell
$body = @{
    event = "NOTIFY_END"
    call_id = "NON_EXISTENT"
} | ConvertTo-Json

$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/webhook" `
    -Headers @{"Content-Type" = "application/json"} `
    -Body $body
$response | ConvertTo-Json
```

**Expected Results**:
- ✅ HTTP 200 (webhook accepted)
- ✅ Response: `{"status": "ok", "message": "Call not found"}`
- ✅ Logs show warning

---

## Test Suite 10: Integration Testing

### TC-10.1: Frontend Integration
**Objective**: Verify frontend displays calls correctly

**Test Steps**:
1. Trigger test call via API
2. Open Calls page
3. Verify call appears
4. Click call to view details
5. Verify all fields displayed

**Verification Points**:
- ✅ Call list shows caller phone/name
- ✅ Status badge correct
- ✅ Duration displayed
- ✅ Cost displayed
- ✅ Timestamps correct
- ✅ Real-time updates work

---

### TC-10.2: Database Consistency
**Objective**: Verify database integrity throughout call lifecycle

**Verification**:
- ✅ Foreign keys valid
- ✅ Timestamps logical (started_at < ended_at)
- ✅ Duration matches timestamps
- ✅ Cost matches duration
- ✅ Relationships intact

---

### TC-10.3: Concurrent Calls
**Objective**: Verify system handles multiple simultaneous calls

**Test**:
1. Trigger 3 test calls simultaneously
2. Verify all calls processed
3. Verify audio bridges don't interfere
4. Verify WebSocket broadcasts for all

**Expected Results**:
- ✅ All calls created successfully
- ✅ Each has unique session_id
- ✅ Audio bridges isolated
- ✅ No data mixing

---

## Test Execution Checklist

### Pre-Test Setup
- [ ] Backend running
- [ ] Frontend running
- [ ] Database accessible
- [ ] Phone number added
- [ ] Agent created and assigned
- [ ] API credentials configured

### Test Execution
- [ ] TC-1.1: Phone Number Storage
- [ ] TC-1.2: Phone Number Matching
- [ ] TC-1.3: Agent Assignment
- [ ] TC-2.1: NOTIFY_START
- [ ] TC-2.2: NOTIFY_ANSWER
- [ ] TC-2.3: NOTIFY_END
- [ ] TC-3.1: Call Record Fields
- [ ] TC-4.1: Session Creation
- [ ] TC-4.2: Greeting Trigger
- [ ] TC-5.1: Audio Bridge Creation
- [ ] TC-5.2: Audio Input
- [ ] TC-5.3: Audio Output
- [ ] TC-6.1: State Transitions
- [ ] TC-7.1: WebSocket Broadcasts
- [ ] TC-8.1: Complete Flow
- [ ] TC-9.1: Error Handling

### Post-Test Verification
- [ ] All test cases passed
- [ ] No errors in logs
- [ ] Database consistent
- [ ] Frontend displays correctly
- [ ] Audio bridge cleanup verified

---

## Quick Test Commands (PowerShell)

### Get Authentication Token
```powershell
# Login and get token
$body = @{
    username = "your@email.com"
    password = "your_password"
}
$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/auth/login" `
    -Body $body `
    -ContentType "application/x-www-form-urlencoded"

$token = $response.access_token
Write-Host "Token: $token"

# Save token to environment variable
$env:API_TOKEN = $token
```

### Test Call Simulation
```powershell
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}
$response = Invoke-RestMethod -Method POST `
    -Uri "http://localhost:8000/api/v1/zadarma/test-call?phone_number=%2B3242833288&caller_id=%2B33123456789" `
    -Headers $headers
$response | ConvertTo-Json
```

### Check Call Status
```powershell
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}
$call = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/calls/{call_id}" `
    -Headers $headers
$call | ConvertTo-Json
```

### Check Audio Bridge
```powershell
# No auth required
$status = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone/audio/{call_id}/status"
$status | ConvertTo-Json
```

### Debug Phone Numbers
```powershell
# Requires authentication
$headers = @{
    "Authorization" = "Bearer $env:API_TOKEN"
}

# List all phone numbers
$phones = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/phone-numbers" `
    -Headers $headers
$phones | ConvertTo-Json

# Test phone number matching
$match = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/phone-numbers/debug/test-match/%2B3242833288" `
    -Headers $headers
$match | ConvertTo-Json
```

---

## Notes

- All tests can be run without a physical phone
- Use `test-call` endpoint for quick validation
- Monitor backend logs for detailed flow
- Use debug endpoints to inspect state
- WebSocket updates require frontend connection
- Audio testing requires actual PCM data (can use test files)

---

## ⚠️ Important: Real Phone Calls Require Public URL

When calling from a **real phone**, Zadarma needs to send webhooks to your backend. Your backend must be **publicly accessible** (not `localhost`).

### Quick Setup for Testing

1. **Use ngrok** to expose your backend:
   ```powershell
   # Install ngrok from https://ngrok.com/download
   ngrok http 8000
   ```

2. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.io`)

3. **Configure in Zadarma**:
   - Webhook URL: `https://abc123.ngrok.io/api/v1/zadarma/webhook`

4. **Update `.env` file**:
   ```env
   BASE_URL=https://abc123.ngrok.io
   BACKEND_URL=https://abc123.ngrok.io
   ```

5. **Restart backend** after updating `.env`

See `docs/ZADARMA_WEBHOOK_SETUP.md` for detailed instructions.

