# SIP Configuration Guide

## Overview

This project now supports **SIP-based call forwarding** in addition to PBX extensions. SIP is the preferred method when available.

## Key Differences: SIP vs PBX

### SIP (Session Initiation Protocol)
- Uses SIP IDs (e.g., `534002-100`, `00001`)
- Configured via `/v1/sip/` API endpoints
- Webhook forwarding configured in **Event Notifications** (not via SIP API)
- SIP redirection API forwards to phone numbers, not webhooks directly

### PBX (Private Branch Exchange)
- Uses extension numbers (e.g., `667776`, `2001`)
- Configured via `/v1/pbx/internal/` API endpoints
- Can forward directly to webhook via API

## Configuration

### Step 1: Set Environment Variables

In your `.env` file or Railway environment variables:

```env
ZADARMA_API_KEY="b46820d6c0993ceb2258"
ZADARMA_API_SECRET="d7f384a4d60c093d0d53"
ZADARMA_SIP_LOGIN="534002-100"  # Your SIP ID
ZADARMA_SIP_PASSWORD="gVZaJZ71es"
ZADARMA_SIP_SERVER="sip.zadarma.com"
ZADARMA_PHONE_NUMBER="+3242833288"
```

### Step 2: Configure Webhook in Zadarma

**This is the most important step!**

1. Log in to Zadarma: https://my.zadarma.com
2. Go to **Integrations** → **API** → **Event Notifications**
3. Set both webhook URLs to:
   ```
   https://weevoice-api-production.up.railway.app/api/v1/zadarma/webhook
   ```
4. Save

**Note:** SIP redirection API does NOT support webhook URLs directly. Webhooks must be configured in Event Notifications.

### Step 3: Verify SIP Configuration

Run the SIP configuration script:

```powershell
.\configure_zadarma_sip.ps1
```

This will:
- List your SIP numbers
- Check SIP status
- Show current redirection settings

## How It Works

1. **Call arrives** → Zadarma receives call to your phone number
2. **SIP routing** → Call is routed through your SIP (`534002-100`)
3. **Webhook sent** → Zadarma sends `NOTIFY_START` webhook to your backend
4. **Backend processes** → Your webhook handler creates call record and starts audio bridge
5. **Audio streaming** → Bidirectional audio flows between caller and Gemini AI

## API Methods Available

### Get SIP List
```python
from app.services.zadarma_service import ZadarmaService

service = ZadarmaService()
sips = service.get_sip_list()
```

### Get SIP Status
```python
status = service.get_sip_status("534002-100")
```

### Get SIP Redirection
```python
redirection = service.get_sip_redirection("534002-100")
```

### Ensure SIP Configured
```python
sip_id = await service.ensure_sip_configured(db, phone_record, agent)
```

## Troubleshooting

### Issue: Calls not reaching webhook

**Check:**
1. ✅ Webhook URL configured in Zadarma Event Notifications
2. ✅ Webhook URL uses HTTPS
3. ✅ SIP ID is correct in environment variables
4. ✅ Phone number is assigned to SIP in Zadarma dashboard

### Issue: "No SIP ID found"

**Solution:**
- Set `ZADARMA_SIP_LOGIN` in environment variables
- Or the system will try to use the first available SIP from your account

### Issue: SIP redirection not working

**Note:** SIP redirection API forwards to **phone numbers**, not webhooks. For webhook forwarding:
- Configure in Zadarma Event Notifications (required)
- SIP redirection API is optional (mainly for phone-to-phone forwarding)

## Database Migration

The `PhoneNumber` model now includes a `sip_id` field. To add this to your database:

```python
# Run Alembic migration
alembic revision --autogenerate -m "add_sip_id_to_phone_numbers"
alembic upgrade head
```

Or manually add the column:

```sql
ALTER TABLE phone_numbers ADD COLUMN sip_id VARCHAR;
```

## Testing

1. **Test SIP configuration:**
   ```powershell
   .\configure_zadarma_sip.ps1
   ```

2. **Test webhook:**
   ```powershell
   .\test_zadarma_configuration.ps1
   ```

3. **Make a real call:**
   - Call your number: `+3242833288`
   - Check Railway logs for webhook events
   - Verify call record is created

## Important Notes

- **SIP redirection API ≠ Webhook forwarding**
  - SIP redirection API: Forwards to phone numbers
  - Webhook forwarding: Configured in Event Notifications

- **Both must be configured:**
  - SIP redirection: Optional (for phone forwarding)
  - Event Notifications: **Required** (for webhook forwarding)

- **Webhook is the primary method:**
  - All call events come via webhooks
  - SIP is just the routing mechanism
  - Webhook URL must be set in Event Notifications

