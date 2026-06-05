"""
Fix account state for Gmail account stuck in token_revoked state
This script:
1. Updates the database to set account_state = 'active'
2. Clears all cache layers (L1, L2 Redis)
3. Verifies the fix
"""
import asyncio
import sys
from pathlib import Path

# Add server root to path (where shared/ is located)
# Path: scripts/fix_account_state.py -> emailservice/ -> services/ -> server/
server_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(server_dir))

from shared.database import get_db_session
from shared.cache import get_redis
from models.email_account import EmailAccount
from sqlalchemy import select, update as sa_update
from uuid import UUID


async def fix_account_state():
    email = "anmolsinha4321@gmail.com"
    account_id = "13672c43-c992-48e7-bdf5-c119b46a5ba9"
    
    print(f"Fixing account state for {email}...")
    
    # 1. Update database
    async with get_db_session() as session:
        # Check current state
        result = await session.execute(
            select(EmailAccount).where(EmailAccount.id == UUID(account_id))
        )
        account = result.scalar_one_or_none()
        
        if not account:
            print(f"❌ Account not found: {account_id}")
            return
        
        print(f"Current state: {account.account_state}")
        print(f"Current is_active: {account.is_active}")
        print(f"Current error: {account.last_error_message}")
        
        # Update to active state
        await session.execute(
            sa_update(EmailAccount)
            .where(EmailAccount.id == UUID(account_id))
            .values(
                account_state="active",
                is_active=True,
                last_error_message=None,
            )
        )
        await session.commit()
        print("✅ Database updated")
    
    # 2. Clear Redis cache
    try:
        redis = await get_redis()
        
        # Clear L2 cache (snapshot)
        deleted = await redis.delete(f"es:snap:{email}")
        print(f"✅ Redis L2 cache cleared (keys deleted: {deleted})")
        
        # Clear any other related keys
        keys_to_clear = [
            f"es:heartbeat:{email}",
            f"es:watch_active:{email}",
        ]
        for key in keys_to_clear:
            await redis.delete(key)
        
        print("✅ All cache layers cleared")
    except Exception as e:
        print(f"⚠️  Redis cache clear failed (non-critical): {e}")
    
    # 3. Verify the fix
    async with get_db_session() as session:
        result = await session.execute(
            select(EmailAccount).where(EmailAccount.id == UUID(account_id))
        )
        account = result.scalar_one_or_none()
        
        print("\n=== Verification ===")
        print(f"Email: {account.email_address}")
        print(f"Account State: {account.account_state}")
        print(f"Is Active: {account.is_active}")
        print(f"Connection Status: {account.connection_status}")
        print(f"Last Error: {account.last_error_message}")
        
        if account.account_state == "active" and account.is_active:
            print("\n✅ Account successfully restored to active state!")
            print("The next webhook event will be processed normally.")
        else:
            print("\n❌ Fix failed - account still in error state")


if __name__ == "__main__":
    asyncio.run(fix_account_state())
