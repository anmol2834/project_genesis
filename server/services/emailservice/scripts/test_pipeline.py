"""
Manual pipeline test - simulates the full flow from webhook to automation
"""
import asyncio
import sys
import time
from pathlib import Path

# Add server root to path (where shared/ is located)
# Path: scripts/test_pipeline.py -> emailservice/ -> services/ -> server/
server_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(server_dir))


async def test_full_pipeline():
    print("="*70)
    print("Manual Pipeline Test")
    print("="*70)
    print()
    
    # Test data
    email = "anmolsinha4321@gmail.com"
    
    print("Step 1: Loading account from database...")
    from token_cache import get_account_snapshot
    snap = await get_account_snapshot(email)
    
    if not snap:
        print(f"❌ Account not found: {email}")
        return
    
    print(f"✅ Account loaded")
    print(f"   ID: {snap['id']}")
    print(f"   State: {snap.get('account_state', 'unknown')}")
    print(f"   Active: {snap.get('is_active', False)}")
    print(f"   Last History ID: {snap.get('last_history_id', 'none')}")
    print(f"   Automation Enabled: {snap.get('automation_enabled', False)}")
    print()
    
    if snap.get('account_state') != 'active':
        print(f"❌ Account state is '{snap.get('account_state')}' - must be 'active'")
        print("   Run: python scripts/fix_account_state.py")
        return
    
    if not snap.get('is_active'):
        print("❌ Account is not active")
        return
    
    print("Step 2: Fetching latest message from Gmail API...")
    from token_cache import get_fresh_token
    
    try:
        token = await get_fresh_token(snap)
        print("✅ Token obtained")
    except Exception as e:
        print(f"❌ Token refresh failed: {e}")
        return
    
    # Fetch latest message
    import httpx
    http = httpx.AsyncClient(timeout=30.0)
    
    try:
        # Get latest message ID
        resp = await http.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {token}"},
            params={"maxResults": 1, "q": "in:inbox"},
        )
        
        if resp.status_code != 200:
            print(f"❌ Gmail API error: {resp.status_code}")
            print(f"   {resp.text[:200]}")
            return
        
        data = resp.json()
        messages = data.get("messages", [])
        
        if not messages:
            print("⚠️  No messages in inbox")
            print("   Send a test email to trigger processing")
            return
        
        msg_id = messages[0]["id"]
        thread_id = messages[0]["threadId"]
        
        print(f"✅ Latest message found")
        print(f"   Message ID: {msg_id}")
        print(f"   Thread ID: {thread_id}")
        print()
        
        # Fetch full message
        print("Step 3: Fetching full message details...")
        resp = await http.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
        )
        
        if resp.status_code != 200:
            print(f"❌ Message fetch error: {resp.status_code}")
            return
        
        msg = resp.json()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(No Subject)")
        from_email = headers.get("From", "")
        
        print(f"✅ Message details:")
        print(f"   Subject: {subject}")
        print(f"   From: {from_email}")
        print(f"   Labels: {msg.get('labelIds', [])}")
        print()
        
        # Check if message is in database
        print("Step 4: Checking if message is in database...")
        from shared.database import get_db_session
        from sqlalchemy import text as _text
        
        async with get_db_session() as session:
            row = await session.execute(
                _text("""
                    SELECT message_id, direction, subject, LENGTH(content)
                    FROM es_messages
                    WHERE message_id = :msg_id
                """),
                {"msg_id": msg_id}
            )
            db_msg = row.first()
            
            if db_msg:
                print(f"✅ Message found in database")
                print(f"   Direction: {db_msg[1]}")
                print(f"   Subject: {db_msg[2]}")
                print(f"   Content length: {db_msg[3]}")
                print()
                
                if db_msg[1] == "INCOMING":
                    print("Step 5: Checking if automation was triggered...")
                    
                    # Check if event was published to automation stream
                    from shared.cache import get_redis
                    redis = await get_redis()
                    
                    # Check automation_events stream
                    try:
                        stream_info = await redis.xinfo_stream("automation_events")
                        print(f"✅ automation_events stream exists")
                        print(f"   Length: {stream_info.get('length', 0)}")
                        print(f"   Last entry: {stream_info.get('last-generated-id', 'none')}")
                        print()
                    except Exception as e:
                        print(f"⚠️  automation_events stream: {e}")
                        print()
                    
                    # Check if reply was generated
                    async with get_db_session() as session:
                        row = await session.execute(
                            _text("""
                                SELECT id::text, status, subject, created_at
                                FROM es_outbox
                                WHERE in_reply_to_message_id = :msg_id
                                ORDER BY created_at DESC
                                LIMIT 1
                            """),
                            {"msg_id": msg_id}
                        )
                        reply = row.first()
                        
                        if reply:
                            print(f"✅ Reply found in outbox")
                            print(f"   ID: {reply[0]}")
                            print(f"   Status: {reply[1]}")
                            print(f"   Subject: {reply[2]}")
                            print(f"   Created: {reply[3]}")
                            print()
                            print("="*70)
                            print("✅ FULL PIPELINE WORKING!")
                            print("="*70)
                        else:
                            print("⚠️  No reply found in outbox")
                            print()
                            print("Possible reasons:")
                            print("  1. automation-service not running")
                            print("  2. automation-service not processing events")
                            print("  3. Message filtered by automation rules")
                            print("  4. Confidence too low (escalated instead)")
                            print()
                            print("Check automation-service logs for:")
                            print(f"  'Processing | msg={msg_id[:12]}'")
                else:
                    print(f"⚠️  Message direction is {db_msg[1]} (not INCOMING)")
                    print("   Only INCOMING messages trigger automation")
            else:
                print("⚠️  Message NOT in database")
                print()
                print("This means emailservice did not store the message.")
                print("Possible reasons:")
                print("  1. Message was filtered (SPAM, TRASH, DRAFT)")
                print("  2. Message fetch failed")
                print("  3. Storage worker error")
                print()
                print("Check emailservice logs for:")
                print(f"  'Gmail enqueued to store_ready | messages=1'")
                print(f"  'StorageWorker: stored=1'")
        
    finally:
        await http.aclose()
    
    print()


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
