# Email Service Account State Fix

## Problem Summary

The Gmail account `anmolsinha4321@gmail.com` was stuck in `account_state = 'token_revoked'` even though it was properly connected via OAuth. This caused all incoming webhook events to be skipped with the message:

```
Gmail event skipped — account requires reconnect | email=anmolsinha4321@gmail.com state=token_revoked
```

## Root Causes

### 1. Account State Not Reset on Reconnect
The `_restore_account_on_reconnect()` function in `api/connect.py` was running as a background task (`asyncio.create_task`), which meant:
- It could fail silently without being noticed
- The database update might not complete before the next webhook arrives
- The cache might not be properly invalidated

### 2. Recovery Worker Redis Client Bug
The `recovery_worker.py` had a bug where `get_redis_client()` was called without `await`, causing:
```
AttributeError: 'coroutine' object has no attribute 'xrange'
```

This prevented the recovery worker from processing any failed events.

## Fixes Applied

### Fix 1: Synchronous Account State Reset (api/connect.py)
Changed line 31 from:
```python
asyncio.create_task(_restore_account_on_reconnect(account))
```
To:
```python
await _restore_account_on_reconnect(account)
```

This ensures the account state is reset to `active` BEFORE the API returns, guaranteeing the next webhook will process correctly.

### Fix 2: Recovery Worker Await Fix (workers/recovery_worker.py)
Changed lines 49 and 129 from:
```python
redis = get_redis_client()
```
To:
```python
redis = await get_redis_client()
```

This fixes the coroutine error and allows the recovery worker to properly drain failed events.

## Immediate Fix for Current Database

Run the fix script to update the database and clear cache:

```bash
cd c:\webapp\project_genesis\server\services\emailservice
python scripts/fix_account_state.py
```

Or manually run the SQL:

```sql
UPDATE email_accounts
SET 
    account_state = 'active',
    last_error_message = NULL,
    is_active = true,
    connection_status = 'CONNECTED',
    updated_at = NOW()
WHERE 
    email_address = 'anmolsinha4321@gmail.com'
    AND id = '13672c43-c992-48e7-bdf5-c119b46a5ba9';
```

Then clear the Redis cache:
```bash
redis-cli DEL "es:snap:anmolsinha4321@gmail.com"
```

## Verification

After applying the fix:

1. Restart the emailservice:
```bash
python main.py
```

2. Send a test email to `anmolsinha4321@gmail.com`

3. Check the logs - you should see:
```
Gmail webhook received | email=anmolsinha4321@gmail.com historyId=...
Gmail enqueued to store_ready | email=anmolsinha4321@gmail.com messages=1
```

Instead of:
```
Gmail event skipped — account requires reconnect
```

## Prevention

The code fixes ensure this won't happen again:
- Account state is always reset synchronously on OAuth reconnect
- Recovery worker properly awaits Redis client
- Cache is properly invalidated on state changes

## Account State Machine

The account can be in these states:
- `active` - Fully operational (normal state)
- `token_expired` - Transient failure, will auto-retry
- `token_revoked` - Permanent failure, requires OAuth reconnect
- `watch_expired` - Watch needs renewal (auto-heals)
- `sync_required` - History gap detected (auto-heals)

The fix ensures that OAuth reconnect always transitions any error state back to `active`.
