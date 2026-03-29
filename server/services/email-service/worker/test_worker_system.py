"""
Worker + Database Layer Testing
Comprehensive tests for email event processing and storage.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from shared.logger import setup_logging
from worker.json_manager import JSONConversationManager
from worker.processor import EventProcessor
from database.repository import EmailConversationRepository
from database.optimizer import DatabaseWriteOptimizer
from database.index_manager import IndexManager

logger = setup_logging("worker-test")


async def test_json_manager():
    """Test JSON conversation manager with 24h logic."""
    logger.info("=" * 60)
    logger.info("TEST 1: JSON Conversation Manager")
    logger.info("=" * 60)
    
    manager = JSONConversationManager()
    
    # Create test messages
    now = datetime.utcnow()
    
    messages = []
    
    # Add message from 30 hours ago (should be filtered)
    old_message = manager.create_message_object(
        message_id="msg_old",
        from_email="old@example.com",
        to_emails=["user@example.com"],
        content="Old message",
        timestamp=now - timedelta(hours=30),
        direction="incoming"
    )
    
    messages = manager.update_messages(messages, old_message)
    
    # Add message from 12 hours ago (should be kept)
    recent_message = manager.create_message_object(
        message_id="msg_recent",
        from_email="recent@example.com",
        to_emails=["user@example.com"],
        content="Recent message",
        timestamp=now - timedelta(hours=12),
        direction="incoming"
    )
    
    messages = manager.update_messages(messages, recent_message)
    
    # Add current message
    current_message = manager.create_message_object(
        message_id="msg_current",
        from_email="current@example.com",
        to_emails=["user@example.com"],
        content="Current message",
        timestamp=now,
        direction="incoming"
    )
    
    messages = manager.update_messages(messages, current_message)
    
    # Verify 24h filter
    if len(messages) == 2:  # Old message should be filtered
        logger.info("✅ 24h filter working correctly")
        logger.info(f"   Messages: {len(messages)} (expected 2)")
    else:
        logger.error(f"❌ 24h filter failed: {len(messages)} messages (expected 2)")
        return False
    
    # Test duplicate detection
    duplicate = manager.update_messages(messages, current_message)
    if len(duplicate) == 2:  # Should not add duplicate
        logger.info("✅ Duplicate detection working")
    else:
        logger.error("❌ Duplicate detection failed")
        return False
    
    # Test sorting
    latest = manager.get_latest_message(messages)
    if latest and latest["message_id"] == "msg_current":
        logger.info("✅ Message sorting working")
    else:
        logger.error("❌ Message sorting failed")
        return False
    
    return True


async def test_database_repository():
    """Test database repository operations."""
    logger.info("=" * 60)
    logger.info("TEST 2: Database Repository")
    logger.info("=" * 60)
    
    repo = EmailConversationRepository()
    manager = JSONConversationManager()
    
    # Create test conversation
    test_user_id = "test_user_123"
    test_thread_id = f"test_thread_{datetime.utcnow().timestamp()}"
    
    message = manager.create_message_object(
        message_id=f"test_msg_{datetime.utcnow().timestamp()}",
        from_email="test@example.com",
        to_emails=["user@example.com"],
        content="Test message content",
        timestamp=datetime.utcnow(),
        direction="incoming",
        subject="Test Subject"
    )
    
    # Test upsert (insert)
    conversation = await repo.upsert_conversation(
        user_id=test_user_id,
        email_account_id="test_account_123",
        provider="gmail",
        thread_id=test_thread_id,
        message_id=message["message_id"],
        from_email=message["from"],
        to_emails=message["to"],
        cc_emails=[],
        bcc_emails=[],
        subject="Test Subject",
        last_24h_messages=[message],
        last_message_at=datetime.utcnow(),
        direction="incoming"
    )
    
    if conversation:
        logger.info("✅ Conversation created successfully")
        logger.info(f"   ID: {conversation.id}")
        logger.info(f"   Thread: {conversation.thread_id}")
    else:
        logger.error("❌ Failed to create conversation")
        return False
    
    # Test fetch by thread
    fetched = await repo.get_conversation_by_thread(test_user_id, test_thread_id)
    if fetched and fetched.id == conversation.id:
        logger.info("✅ Fetch by thread working")
    else:
        logger.error("❌ Fetch by thread failed")
        return False
    
    # Test upsert (update)
    new_message = manager.create_message_object(
        message_id=f"test_msg_2_{datetime.utcnow().timestamp()}",
        from_email="test2@example.com",
        to_emails=["user@example.com"],
        content="Second test message",
        timestamp=datetime.utcnow(),
        direction="incoming"
    )
    
    updated_messages = manager.update_messages([message], new_message)
    
    updated_conversation = await repo.upsert_conversation(
        user_id=test_user_id,
        email_account_id="test_account_123",
        provider="gmail",
        thread_id=test_thread_id,
        message_id=new_message["message_id"],
        from_email=new_message["from"],
        to_emails=new_message["to"],
        cc_emails=[],
        bcc_emails=[],
        subject="Test Subject",
        last_24h_messages=updated_messages,
        last_message_at=datetime.utcnow(),
        direction="incoming"
    )
    
    if updated_conversation and len(updated_conversation.last_24h_messages) == 2:
        logger.info("✅ Conversation updated successfully")
        logger.info(f"   Messages: {len(updated_conversation.last_24h_messages)}")
    else:
        logger.error("❌ Conversation update failed")
        return False
    
    return True


async def test_event_processor():
    """Test event processor end-to-end."""
    logger.info("=" * 60)
    logger.info("TEST 3: Event Processor")
    logger.info("=" * 60)
    
    processor = EventProcessor()
    
    # Create test event
    test_event = {
        "user_id": "test_user_456",
        "email_account_id": "test_account_456",
        "provider": "gmail",
        "message_id": f"test_event_{datetime.utcnow().timestamp()}",
        "thread_id": f"test_thread_{datetime.utcnow().timestamp()}",
        "from_email": "sender@example.com",
        "to_emails": ["recipient@example.com"],
        "cc_emails": [],
        "bcc_emails": [],
        "subject": "Test Event",
        "content": "This is a test event content",
        "timestamp": datetime.utcnow().isoformat(),
        "direction": "incoming",
        "has_attachments": False
    }
    
    # Process event
    success = await processor.process_event(test_event)
    
    if success:
        logger.info("✅ Event processed successfully")
    else:
        logger.error("❌ Event processing failed")
        return False
    
    # Verify in database
    repo = EmailConversationRepository()
    conversation = await repo.get_conversation_by_thread(
        test_event["user_id"],
        test_event["thread_id"]
    )
    
    if conversation:
        logger.info("✅ Event stored in database")
        logger.info(f"   Messages: {len(conversation.last_24h_messages)}")
    else:
        logger.error("❌ Event not found in database")
        return False
    
    return True


async def test_high_load():
    """Test high load scenario."""
    logger.info("=" * 60)
    logger.info("TEST 4: High Load (100 events)")
    logger.info("=" * 60)
    
    processor = EventProcessor()
    
    start_time = datetime.utcnow()
    success_count = 0
    
    test_user_id = "test_user_load"
    test_thread_id = f"test_thread_load_{datetime.utcnow().timestamp()}"
    
    for i in range(100):
        test_event = {
            "user_id": test_user_id,
            "email_account_id": "test_account_load",
            "provider": "gmail",
            "message_id": f"test_load_{i}_{datetime.utcnow().timestamp()}",
            "thread_id": test_thread_id,
            "from_email": f"sender{i}@example.com",
            "to_emails": ["recipient@example.com"],
            "cc_emails": [],
            "bcc_emails": [],
            "subject": f"Test Load {i}",
            "content": f"Test content {i}",
            "timestamp": datetime.utcnow().isoformat(),
            "direction": "incoming",
            "has_attachments": False
        }
        
        success = await processor.process_event(test_event)
        if success:
            success_count += 1
    
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    logger.info(f"✅ Processed {success_count}/100 events in {duration:.2f}s")
    logger.info(f"✅ Rate: {success_count/duration:.2f} events/sec")
    
    # Verify final conversation
    repo = EmailConversationRepository()
    conversation = await repo.get_conversation_by_thread(test_user_id, test_thread_id)
    
    if conversation:
        logger.info(f"✅ Final conversation has {len(conversation.last_24h_messages)} messages")
    
    return success_count >= 95  # Allow 5% failure


async def test_index_manager():
    """Test index manager."""
    logger.info("=" * 60)
    logger.info("TEST 5: Index Manager")
    logger.info("=" * 60)
    
    manager = IndexManager()
    
    # Verify indexes
    indexes = await manager.verify_indexes()
    
    if indexes:
        logger.info(f"✅ Found {len(indexes)} indexes")
        for index_name, exists in indexes.items():
            status = "✅" if exists else "❌"
            logger.info(f"   {status} {index_name}")
    else:
        logger.warning("⚠️  Could not verify indexes")
    
    # Get table size
    size_info = await manager.get_table_size()
    if size_info:
        logger.info(f"✅ Table size: {size_info.get('total_size', 'unknown')}")
        logger.info(f"   Rows: {size_info.get('row_count', 0)}")
    
    return True


async def run_all_tests():
    """Run all tests."""
    logger.info("🚀 Starting Worker + Database Layer Tests")
    logger.info("")
    
    results = []
    
    # Test 1: JSON Manager
    try:
        result = await test_json_manager()
        results.append(("JSON Manager", result))
    except Exception as e:
        logger.error(f"Test 1 failed: {e}", exc_info=True)
        results.append(("JSON Manager", False))
    
    await asyncio.sleep(1)
    
    # Test 2: Database Repository
    try:
        result = await test_database_repository()
        results.append(("Database Repository", result))
    except Exception as e:
        logger.error(f"Test 2 failed: {e}", exc_info=True)
        results.append(("Database Repository", False))
    
    await asyncio.sleep(1)
    
    # Test 3: Event Processor
    try:
        result = await test_event_processor()
        results.append(("Event Processor", result))
    except Exception as e:
        logger.error(f"Test 3 failed: {e}", exc_info=True)
        results.append(("Event Processor", False))
    
    await asyncio.sleep(1)
    
    # Test 4: High Load
    try:
        result = await test_high_load()
        results.append(("High Load", result))
    except Exception as e:
        logger.error(f"Test 4 failed: {e}", exc_info=True)
        results.append(("High Load", False))
    
    await asyncio.sleep(1)
    
    # Test 5: Index Manager
    try:
        result = await test_index_manager()
        results.append(("Index Manager", result))
    except Exception as e:
        logger.error(f"Test 5 failed: {e}", exc_info=True)
        results.append(("Index Manager", False))
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
