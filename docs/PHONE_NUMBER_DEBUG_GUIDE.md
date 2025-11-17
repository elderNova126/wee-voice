# Phone Number Display Debugging Guide

## Understanding Phone Number Fields

When a call comes in, there are two important phone numbers:

1. **`caller_id`** (or `caller_phone` in database) - The phone number **calling FROM** (the person making the call)
2. **`called_did`** (or `called_number`) - The phone number **being called TO** (your Zadarma number, e.g., 3242833288)

## Current Implementation

### What Gets Stored
- **`caller_phone`** = The caller's phone number (who is calling you)
- **`caller_name`** = Initially set to caller's phone, can be updated later

### What Gets Displayed
- In the Calls list: Shows `caller_name` or `caller_phone` (the person who called)
- In call details: Shows `caller_phone` and `caller_name`

## Debugging Steps

### 1. Check What Zadarma Sends

When you receive a call, check the backend logs for:
```
Full webhook data: {...}
Extracted - From: ..., To: ...
Normalized - From: ..., To: ...
```

This shows exactly what Zadarma is sending.

### 2. Check Your Stored Phone Numbers

Use the debug endpoint:
```bash
GET /api/v1/phone-numbers/debug/phone-numbers
```

This shows:
- All your phone numbers
- Their normalized forms
- Which ones have agents assigned

### 3. Test Phone Number Matching

Test if a phone number would match:
```bash
GET /api/v1/phone-numbers/debug/test-match/3242833288
GET /api/v1/phone-numbers/debug/test-match/+3242833288
GET /api/v1/phone-numbers/debug/test-match/003242833288
```

### 4. Check Call Records

Look at recent call records to see what was stored:
- Check `caller_phone` field (should be the caller's number)
- Check `zadarma_call_id` to match with Zadarma logs

## Common Issues

### Issue 1: Wrong Number Displayed

**Symptom**: The displayed phone number doesn't match what you expect.

**Possible Causes**:
- Phone number stored without `+` prefix (e.g., `3242833288` instead of `+3242833288`)
- Zadarma sending number in different format
- Normalization changing the number incorrectly

**Solution**:
1. Check backend logs to see what Zadarma sent
2. Check database to see what was stored
3. Use debug endpoints to test matching

### Issue 2: Number Not Matching Agent

**Symptom**: Call comes in but no agent is found.

**Possible Causes**:
- Phone number format mismatch (e.g., `3242833288` vs `+3242833288`)
- Number stored differently than Zadarma sends it
- Agent not assigned to the number

**Solution**:
1. Check logs: "Looking up agent for phone number: ..."
2. Check logs: "Available phone numbers in database: ..."
3. Ensure phone number is normalized consistently
4. Use debug endpoint to test matching

### Issue 3: Number Shows as "Call #123" Instead of Phone Number

**Symptom**: Call list shows "Call #123" instead of phone number.

**Possible Causes**:
- `caller_phone` is `null` or empty
- API not returning `caller_phone` field
- Frontend not receiving the field

**Solution**:
1. Check if `caller_phone` is in API response
2. Check database to see if `caller_phone` was stored
3. Verify `CallResponse` model includes `caller_phone`

## Phone Number Format

### Expected Format
- **E.164 format**: `+3242833288` (with `+` prefix)
- **Belgian numbers**: `+32` (country code) + `42833288` (local number)

### Normalization Rules
1. Remove spaces, dashes, parentheses, dots
2. If starts with `00`, replace with `+`
3. If starts with `32` and 10+ digits, add `+` prefix
4. Otherwise preserve as-is

## Testing

### Test with Real Call
1. Call your Zadarma number (3242833288)
2. Check backend logs immediately
3. Check Calls page to see what's displayed
4. Compare with what you expect

### Test with Debug Endpoints
1. Check stored numbers: `/api/v1/phone-numbers/debug/phone-numbers`
2. Test matching: `/api/v1/phone-numbers/debug/test-match/3242833288`
3. Check recent calls in database

## Next Steps

If you're still seeing the wrong number:

1. **Check backend logs** when you receive a call - they now show:
   - Full webhook data from Zadarma
   - Extracted phone numbers
   - Normalized phone numbers
   - Available phone numbers in database
   - Matching attempts

2. **Use debug endpoints** to see:
   - How your numbers are stored
   - If matching would work

3. **Verify phone number format**:
   - Should be stored as `+3242833288` (with `+`)
   - If stored as `3242833288` (without `+`), update it

4. **Check what Zadarma sends**:
   - Look at "Full webhook data" in logs
   - See which field contains the phone number
   - Verify normalization is working correctly

