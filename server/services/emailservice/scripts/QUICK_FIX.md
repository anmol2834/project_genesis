# QUICK FIX GUIDE

## The Problem
Gmail account is stuck in `token_revoked` state, causing all emails to be skipped.

## The Solution (3 Steps)

### Step 1: Run the Fix Script
```bash
cd c:\webapp\project_genesis\server\services\emailservice
python scripts\fix_account_state.py
```

Or use the batch file:
```bash
cd c:\webapp\project_genesis\server\services\emailservice\scripts
run_fix.bat
```

### Step 2: Restart the Email Service
Stop the current service (Ctrl+C) and restart:
```bash
cd c:\webapp\project_genesis\server\services\emailservice
python main.py
```

### Step 3: Test
Send a test email to `anmolsinha4321@gmail.com` and check the logs.

You should see:
```
✅ Gmail webhook received | email=anmolsinha4321@gmail.com
✅ Gmail enqueued to store_ready | email=anmolsinha4321@gmail.com messages=1
```

NOT:
```
❌ Gmail event skipped — account requires reconnect
```

## What Was Fixed

1. **Code Fix 1**: `api/connect.py` - Account state now resets synchronously on OAuth reconnect
2. **Code Fix 2**: `workers/recovery_worker.py` - Fixed Redis client await bug
3. **Database Fix**: Account state reset from `token_revoked` to `active`
4. **Cache Fix**: Cleared stale Redis cache

## If It Still Doesn't Work

Check these:
1. Database was updated: `SELECT account_state FROM email_accounts WHERE email_address = 'anmolsinha4321@gmail.com'`
   - Should show: `active`
2. Redis cache was cleared: `redis-cli GET "es:snap:anmolsinha4321@gmail.com"`
   - Should show: `(nil)` or contain `"account_state":"active"`
3. Service restarted: Check logs for "emailservice ready on port 8004"

## Need Help?
See `FIX_README.md` for detailed explanation of the root causes and fixes.
