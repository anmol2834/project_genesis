"""
End-to-End Pipeline Test
========================
This script tests the complete email automation pipeline:
1. Check account state
2. Check recent messages in database
3. Check automation stream
4. Provide actionable recommendations
"""
import asyncio
import sys
from pathlib import Path

# Add server root to path (where shared/ is located)
# Path: scripts/test_e2e.py -> emailservice/ -> services/ -> server/
server_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(server_dir))


async def main():
    print("="*80)
    print("EMAIL AUTOMATION PIPELINE - END-TO-END TEST")
    print("="*80)
    print()
    
    email = "anmolsinha4321@gmail.com"
    
    # ========================================================================
    # STEP 1: Check Account Configuration
    # ========================================================================
    print("STEP 1: Checking Account Configuration")
    print("-"*80)
    
    from shared.database import get_db_session
    from sqlalchemy import text as _text
    
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    id::text as account_id,
                    user_id::text,
                    email_address,
                    account_state,
                    is_active,
                    automation_enabled,
                    last_history_id,
                    connection_status,
                    last_error_message
                FROM email_accounts
                WHERE email_address = :email
            """),
            {"email": email}
        )
        account = row.first()
        
        if not account:
            print(f"❌ FATAL: Account not found: {email}")
            print("   ACTION: Connect the account via OAuth")
            return
        
        account_id = account[0]
        user_id = account[1]
        account_state = account[3]
        is_active = account[4]
        automation_enabled = account[5]
        last_history_id = account[6]
        
        print(f"Account ID: {account_id}")
        print(f"User ID: {user_id}")
        print(f"Email: {account[2]}")
        print()
        
        issues = []
        
        if account_state != "active":
            print(f"❌ Account State: {account_state} (should be 'active')")
            issues.append("account_state")
        else:
            print(f"✅ Account State: {account_state}")
        
        if not is_active:
            print(f"❌ Is Active: {is_active} (should be True)")
            issues.append("is_active")
        else:
            print(f"✅ Is Active: {is_active}")
        
        if not automation_enabled:
            print(f"⚠️  Automation Enabled: {automation_enabled}")
            print(f"   NOTE: Messages will be stored but NOT sent to automation-service")
            issues.append("automation_disabled")
        else:
            print(f"✅ Automation Enabled: {automation_enabled}")
        
        print(f"   Last History ID: {last_history_id or 'none'}")
        print(f"   Connection Status: {account[7]}")
        
        if account[8]:
            print(f"   Last Error: {account[8][:100]}")
        
        print()
        
        if issues:
            if "account_state" in issues or "is_active" in issues:
                print("❌ CRITICAL ISSUES FOUND")
                print("   ACTION: Run fix script:")
                print("   python scripts/fix_account_state.py")
                print()
                return
    
    # ========================================================================
    # STEP 2: Check Recent Messages
    # ========================================================================
    print("STEP 2: Checking Recent Messages in Database")
    print("-"*80)
    
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
                WHERE user_id = :user_id
                ORDER BY timestamp DESC
                LIMIT 5
            """),
            {"user_id": user_id}
        )
        messages = row.fetchall()
        
        if not messages:
            print("⚠️  No messages found in database")
            print("   This means emailservice has not stored any messages yet")
            print()
            print("   ACTION: Send a test email to trigger processing")
            print(f"   Send to: {email}")
            print("   Subject: test")
            print("   Body: hello")
            print()
            return
        
        print(f"Found {len(messages)} recent messages:")
        print()
        
        incoming_count = 0
        latest_incoming = None
        
        for i, msg in enumerate(messages, 1):
            direction_symbol = "📥" if msg[1] == "INCOMING" else "📤"
            print(f"{i}. {direction_symbol} {msg[0][:20]:20} | {msg[2][:40]:40}")
            print(f"   From: {msg[3][:50]}")
            print(f"   Time: {msg[4]} | Content: {msg[5]} chars")
            print()
            
            if msg[1] == "INCOMING":
                incoming_count += 1
                if not latest_incoming:
                    latest_incoming = msg
        
        if incoming_count == 0:
            print("⚠️  No INCOMING messages found")
            print("   Only INCOMING messages trigger automation")
            print()
            print("   ACTION: Send a NEW email (not a reply) to trigger automation")
            print(f"   Send to: {email}")
            return
        
        print(f"✅ Found {incoming_count} INCOMING message(s)")
        print()
    
    # ========================================================================
    # STEP 3: Check Automation Stream
    # ========================================================================
    print("STEP 3: Checking Automation Stream")
    print("-"*80)
    
    from shared.cache import get_redis
    redis = await get_redis()
    
    try:
        stream_info = await redis.xinfo_stream("automation_events")
        stream_length = stream_info.get("length", 0)
        last_entry_id = stream_info.get("last-generated-id", "none")
        
        print(f"✅ automation_events stream exists")
        print(f"   Length: {stream_length}")
        print(f"   Last Entry ID: {last_entry_id}")
        print()
        
        if stream_length == 0:
            print("⚠️  Stream is empty - no events published yet")
            print()
            print("   Possible reasons:")
            print("   1. No INCOMING messages have been processed")
            print("   2. AIHandoffWorker not running")
            print("   3. automation_enabled is False")
            print()
        else:
            # Check latest event
            latest = await redis.xrevrange("automation_events", "+", "-", count=1)
            if latest:
                event_id, fields = latest[0]
                import json
                data = json.loads(fields.get("data", "{}"))
                print(f"Latest event:")
                print(f"   Event ID: {event_id}")
                print(f"   Message ID: {data.get('message_id', 'unknown')[:20]}")
                print(f"   User ID: {data.get('user_id', 'unknown')[:20]}")
                print(f"   Timestamp: {data.get('ts', 0)}")
                print()
    
    except Exception as e:
        print(f"⚠️  automation_events stream not found: {e}")
        print("   This means no events have been published yet")
        print()
    
    # ========================================================================
    # STEP 4: Check Outbox (Replies)
    # ========================================================================
    print("STEP 4: Checking Outbox (Generated Replies)")
    print("-"*80)
    
    async with get_db_session() as session:
        row = await session.execute(
            _text("""
                SELECT 
                    id::text,
                    status,
                    subject,
                    in_reply_to_message_id,
                    created_at
                FROM es_outbox
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 5
            """),
            {"user_id": user_id}
        )
        replies = row.fetchall()
        
        if not replies:
            print("⚠️  No replies found in outbox")
            print("   This means automation-service has not generated any replies")
            print()
            print("   Possible reasons:")
            print("   1. automation-service not running")
            print("   2. automation-service not processing events from stream")
            print("   3. Messages filtered by automation rules")
            print("   4. Confidence too low (escalated instead of sending)")
            print()
            print("   ACTION: Check automation-service logs for:")
            print("   - 'Processing | conv=...'")
            print("   - 'DB load OK | msg=...'")
            print("   - 'Orchestrator COMPLETE | decision=...'")
            print()
        else:
            print(f"✅ Found {len(replies)} reply/replies:")
            print()
            for i, reply in enumerate(replies, 1):
                print(f"{i}. {reply[0][:20]:20} | Status: {reply[1]:10}")
                print(f"   Subject: {reply[2][:50]}")
                print(f"   In Reply To: {reply[3] or 'N/A'}")
                print(f"   Created: {reply[4]}")
                print()
    
    # ========================================================================
    # STEP 5: Summary & Recommendations
    # ========================================================================
    print("="*80)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*80)
    print()
    
    if account_state == "active" and is_active and automation_enabled:
        if incoming_count > 0:
            if replies:
                print("✅ PIPELINE IS WORKING!")
                print()
                print("The complete flow is operational:")
                print("  1. ✅ Account configured correctly")
                print("  2. ✅ Messages being stored")
                print("  3. ✅ Automation generating replies")
                print()
            else:
                print("⚠️  PARTIAL SUCCESS")
                print()
                print("Messages are being stored, but no replies generated.")
                print()
                print("Next steps:")
                print("  1. Check if automation-service is running")
                print("  2. Send a NEW test email to trigger automation")
                print("  3. Monitor automation-service logs for processing")
                print()
                print("Test email:")
                print(f"  To: {email}")
                print("  Subject: test inquiry")
                print("  Body: I need help with your product")
                print()
        else:
            print("⚠️  NO INCOMING MESSAGES")
            print()
            print("Send a test email to trigger the pipeline:")
            print(f"  To: {email}")
            print("  Subject: test")
            print("  Body: hello")
            print()
    else:
        print("❌ CONFIGURATION ISSUES")
        print()
        print("Fix the account configuration first:")
        print("  python scripts/fix_account_state.py")
        print()
    
    print("For detailed logs, check:")
    print("  - emailservice: Look for 'Gmail enqueued to store_ready'")
    print("  - emailservice: Look for 'AI handoff → automation_events'")
    print("  - automation-service: Look for 'Processing | conv='")
    print("  - automation-service: Look for 'Orchestrator COMPLETE'")
    print()


if __name__ == "__main__":
    asyncio.run(main())
