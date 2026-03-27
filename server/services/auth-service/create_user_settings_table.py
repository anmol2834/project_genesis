"""
Database Migration: Create user_settings table
Run this script to add the user_settings table to the database

Usage:
    python create_user_settings_table.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from shared.database.postgres import get_engine, Base
from shared.logger import get_logger
from models.user_settings import UserSettings

logger = get_logger(__name__)


async def create_user_settings_table():
    """
    Create user_settings table in the database
    """
    try:
        engine = get_engine()
        
        logger.info("Creating user_settings table...")
        
        async with engine.begin() as conn:
            # Create the table using SQLAlchemy metadata
            await conn.run_sync(Base.metadata.create_all, tables=[UserSettings.__table__])
        
        logger.info("✓ user_settings table created successfully")
        
        # Verify table creation
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_settings'
            """))
            
            if result.fetchone():
                logger.info("✓ Table verification successful")
            else:
                logger.error("✗ Table verification failed")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False


async def migrate_existing_users():
    """
    Create default settings for existing users who don't have settings yet
    """
    try:
        from shared.database import get_db_session
        from models.user import User
        from sqlalchemy import select
        
        logger.info("Migrating existing users...")
        
        async with get_db_session() as session:
            # Get all users
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            logger.info(f"Found {len(users)} users")
            
            migrated_count = 0
            for user in users:
                # Check if settings already exist
                existing_settings = await session.execute(
                    select(UserSettings).where(UserSettings.user_id == user.id)
                )
                
                if not existing_settings.scalar_one_or_none():
                    # Create default settings
                    default_settings = UserSettings.create_default_settings(str(user.id))
                    default_settings.workspace_name = user.business_name
                    session.add(default_settings)
                    migrated_count += 1
                    logger.info(f"Created settings for user: {user.email}")
            
            await session.commit()
            logger.info(f"✓ Migrated {migrated_count} users")
        
        return True
        
    except Exception as e:
        logger.error(f"User migration failed: {e}", exc_info=True)
        return False


async def main():
    """
    Main migration function
    """
    logger.info("=" * 60)
    logger.info("Starting user_settings table migration")
    logger.info("=" * 60)
    
    # Step 1: Create table
    success = await create_user_settings_table()
    if not success:
        logger.error("Migration failed at table creation step")
        return
    
    # Step 2: Migrate existing users
    success = await migrate_existing_users()
    if not success:
        logger.error("Migration failed at user migration step")
        return
    
    logger.info("=" * 60)
    logger.info("Migration completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
