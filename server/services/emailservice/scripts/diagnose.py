"""
Diagnostic script to check why emailservice is not processing messages
"""
import asyncio
import sys
from pathlib import Path

# Add server root to path (where shared/ is located)
# Path: scripts/diagnose.py -> emailservice/ -> services/ -> server/
server_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(server_dir))

from shared.database import get_db_session
from sqlalchemy import text as _text


async def diagnose():
    print("="*70)
    print("Email Service Diagnostic")
    print("="*70)
    print()
    
    email = "anmolsinha4321@gmail.com"
    
    # 1. Check account state
    print("1. Checking account state...")
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    id::text,
                    email_address,
                    account_state,
                    is_active,
                    last_history_id,
                    last_error_message,
                    automation_enabled
                FROM email_accounts
                WHERE email_address = :email
            """),
            {"email": email}
        )
        r = row.first()
        
        if not r:
            print(f"   ❌ Account not found: {email}")
            return
        
        account_id = r[0]
        print(f"   ✅ Account found")
        print(f"      ID: {account_id}")
        print(f"      State: {r[2]}")
        print(f"      Active: {r[3]}")
        print(f"      Last History ID: {r[4]}")
        print(f"      Automation Enabled: {r[6]}")
        if r[5]:
            print(f"      Last Error: {r[5]}")
        print()
        
        if r[2] != "active":
            print(f"   ⚠️  Account state is '{r[2]}' - should be 'active'")
            print(f"      Run: python scripts/fix_account_state.py")
            print()
        
        if not r[3]:
            print(f"   ⚠️  Account is not active")
            print()
        
        if not r[6]:
            print(f"   ⚠️  Automation is DISABLED for this account")
            print(f"      Messages will be stored but NOT sent to automation-service")
            print()
    
    # 2. Check recent messages
    print("2. Checking recent messages...")
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    message_id,
                    direction,
                    subject,
                    from_email,
                    timestamp,
                    LENGTH(content) as content_len
                FROM es_messages
                WHERE user_id = (
                    SELECT user_id FROM email_accounts WHERE email_address = :email
                )
                ORDER BY timestamp DESC
                LIMIT 5
            """),
            {"email": email}
        )
        messages = row.fetchall()
        
        if not messages:
            print("   ⚠️  No messages found in database")
            print("      This means emailservice is not storing messages")
            print()
        else:
            print(f"   ✅ Found {len(messages)} recent messages:")
            for msg in messages:
                print(f"      - {msg[0][:16]} | {msg[1]:8} | {msg[2][:30]:30} | {msg[4]}")
            print()
    
    # 3. Check conversations
    print("3. Checking conversations...")
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    thread_id,
                    subject,
                    message_count,
                    last_message_at
                FROM es_conversations
                WHERE user_id = (
                    SELECT user_id FROM email_accounts WHERE email_address = :email
                )
                ORDER BY last_message_at DESC
                LIMIT 3
            """),
            {"email": email}
        )
        convs = row.fetchall()
        
        if not convs:
            print("   ⚠️  No conversations found")
        else:
            print(f"   ✅ Found {len(convs)} recent conversations:")
            for conv in convs:
                print(f"      - {conv[0][:16]} | {conv[1][:30]:30} | msgs={conv[2]} | {conv[3]}")
            print()
    
    # 4. Check outbox (replies)
    print("4. Checking outbox (replies)...")
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    id::text,
                    status,
                    subject,
                    created_at
                FROM es_outbox
                WHERE user_id = (
                    SELECT user_id FROM email_accounts WHERE email_address = :email
                )
                ORDER BY created_at DESC
                LIMIT 3
            """),
            {"email": email}
        )
        outbox = row.fetchall()
        
        if not outbox:
            print("   ⚠️  No replies in outbox")
            print("      This means automation-service has not generated any replies")
            print()
        else:
            print(f"   ✅ Found {len(outbox)} replies:")
            for item in outbox:
                print(f"      - {item[0][:16]} | {item[1]:10} | {item[2][:30]:30} | {item[3]}")
            print()
    
    # 5. Summary
    print("="*70)
    print("DIAGNOSIS SUMMARY")
    print("="*70)
    
    if r[2] == "active" and r[3] and r[6]:
        print("✅ Account configuration looks good")
        print()
        print("If messages are not being processed:")
        print("  1. Check emailservice logs for 'Gmail enqueued to store_ready'")
        print("  2. Check emailservice logs for 'AI handoff → automation_events'")
        print("  3. Check automation-service logs for 'Processing | conv='")
        print()
        print("If you see 'No new messages' in logs:")
        print("  - The history cursor may be ahead of the webhook")
        print("  - Send a NEW email to trigger processing")
        print("  - Check last_history_id in database matches Gmail")
    else:
        print("❌ Account configuration issues found - see warnings above")
    
    print()


if __name__ == "__main__":
    asyncio.run(diagnose())
