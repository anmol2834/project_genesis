"""
Database Migration: Create email_provider_subscriptions table
Run this script to create the subscription tracking table.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.database import init_database, close_database, get_engine
from shared.logger import setup_logging
from models.email_provider_subscription import EmailProviderSubscription

logger = setup_logging("migration")


async def create_subscription_table():
    """Create email_provider_subscriptions table."""
    logger.info("Starting migration: create email_provider_subscriptions table")
    
    try:
        # Initialize database
        await init_database()
        
        # Get engine
        engine = get_engine()
        
        # Create table
        async with engine.begin() as conn:
            await conn.run_sync(EmailProviderSubscription.__table__.create, checkfirst=True)
        
        logger.info("✅ Table email_provider_subscriptions created successfully")
        
        # Close database
        await close_database()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


async def verify_table():
    """Verify table was created."""
    logger.info("Verifying table creation")
    
    try:
        await init_database()
        engine = get_engine()
        
        async with engine.begin() as conn:
            result = await conn.execute(
                "SELECT COUNT(*) FROM email_provider_subscriptions"
            )
            count = result.scalar()
            logger.info(f"✅ Table verified. Current row count: {count}")
        
        await close_database()
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False


async def main():
    """Run migration."""
    print("=" * 60)
    print("Email Provider Subscriptions Table Migration")
    print("=" * 60)
    print()
    
    # Create table
    success = await create_subscription_table()
    
    if not success:
        print("\n❌ Migration failed!")
        return 1
    
    # Verify
    verified = await verify_table()
    
    if not verified:
        print("\n⚠️  Table created but verification failed")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
