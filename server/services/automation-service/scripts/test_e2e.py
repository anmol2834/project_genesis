"""
Automation Service - End-to-End Test
=====================================
Tests the complete workflow from email ingestion to AI response.
"""
import asyncio
import sys
import os
import json
import time
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.config import get_config
from shared.cache import init_redis, get_redis_client


async def test_publish_to_automation_events():
    """Test publishing a message to automation_events stream"""
    
    print("\n" + "=" * 70)
    print("TEST 1: Publish to automation_events")
    print("=" * 70)
    
    await init_redis()
    redis = get_redis_client()
    
    # Create test message
    test_message = {
        "conversation_id": f"test_conv_{uuid.uuid4().hex[:8]}",
        "user_id": "test_user_123",
        "message_id": f"msg_{uuid.uuid4().hex[:8]}",
        "thread_id": "test_user_123:thread_001",
        "provider": "test",
        "trace_id": str(uuid.uuid4()),
        "automation_enabled": True,
        "_priority": 2,
        "_schema_version": 2,
        "ts": time.time(),
        "content": "Hello, I would like to know about your pricing plans.",
        "subject": "Inquiry about pricing"
    }
    
    print(f"\n📤 Publishing test message...")
    print(f"   Conversation: {test_message['conversation_id']}")
    print(f"   Message: {test_message['message_id']}")
    print(f"   Content: {test_message['content']}")
    
    try:
        # Publish to stream
        msg_id = await redis.xadd(
            "automation_events",
            {"data": json.dumps(test_message)},
            maxlen=10_000,
            approximate=True
        )
        
        print(f"\n✅ Message published successfully!")
        print(f"   Stream ID: {msg_id}")
        
        # Check stream length
        length = await redis.xlen("automation_events")
        print(f"   Stream length: {length}")
        
        return True, test_message
        
    except Exception as e:
        print(f"\n❌ Publish failed: {e}")
        return False, None


async def test_check_consumer_group():
    """Check if consumer group can read the message"""
    
    print("\n" + "=" * 70)
    print("TEST 2: Check Consumer Group")
    print("=" * 70)
    
    redis = get_redis_client()
    
    try:
        # Check pending messages
        pending = await redis.xpending(
            "automation_events",
            "automation_workers"
        )
        
        print(f"\n📊 Consumer Group Status:")
        print(f"   Pending messages: {pending['pending']}")
        print(f"   Consumer count: {pending.get('consumers', 0)}")
        
        if pending['pending'] > 0:
            print(f"\n✅ Messages are waiting to be processed")
        else:
            print(f"\n⚠️  No pending messages (they may have been processed already)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Consumer group check failed: {e}")
        return False


async def test_read_from_stream():
    """Test reading from stream as consumer"""
    
    print("\n" + "=" * 70)
    print("TEST 3: Read from Stream (as consumer)")
    print("=" * 70)
    
    redis = get_redis_client()
    consumer_id = f"test_consumer_{time.time_ns()}"
    
    try:
        # Read from consumer group
        messages = await redis.xreadgroup(
            groupname="automation_workers",
            consumername=consumer_id,
            streams={"automation_events": ">"},
            count=5,
            block=1000
        )
        
        if messages:
            print(f"\n✅ Read {len(messages[0][1])} messages:")
            
            for stream_name, stream_messages in messages:
                for msg_id, fields in stream_messages:
                    data = json.loads(fields.get("data", "{}"))
                    print(f"\n   Message ID: {msg_id}")
                    print(f"   Conversation: {data.get('conversation_id', 'N/A')}")
                    print(f"   Content: {data.get('content', 'N/A')[:50]}...")
                    
                    # ACK the message
                    await redis.xack("automation_events", "automation_workers", msg_id)
                    print(f"   ✓ Acknowledged")
            
            return True
        else:
            print(f"\n⚠️  No messages available (may have been processed already)")
            return True
        
    except Exception as e:
        print(f"\n❌ Read failed: {e}")
        return False


async def test_check_response_stream():
    """Check if responses are being published"""
    
    print("\n" + "=" * 70)
    print("TEST 4: Check automation_responses Stream")
    print("=" * 70)
    
    redis = get_redis_client()
    
    try:
        # Check if stream exists and has messages
        length = await redis.xlen("automation_responses")
        
        print(f"\n📊 Response Stream Status:")
        print(f"   Stream length: {length}")
        
        if length > 0:
            # Read last few messages
            messages = await redis.xrevrange("automation_responses", "+", "-", count=3)
            
            print(f"\n✅ Recent responses:")
            for msg_id, fields in messages:
                data = json.loads(fields.get("data", "{}"))
                print(f"\n   Response ID: {msg_id}")
                print(f"   Conversation: {data.get('conversation_id', 'N/A')}")
                print(f"   Action: {data.get('action', 'N/A')}")
                print(f"   Confidence: {data.get('confidence', 0):.2f}")
                print(f"   Response: {data.get('response_text', 'N/A')[:100]}...")
        else:
            print(f"\n⚠️  No responses yet. Worker may not be processing messages.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Response check failed: {e}")
        return False


async def test_workflow_latency():
    """Test end-to-end workflow latency"""
    
    print("\n" + "=" * 70)
    print("TEST 5: Workflow Latency Test")
    print("=" * 70)
    
    redis = get_redis_client()
    
    # Record current stream lengths
    events_before = await redis.xlen("automation_events")
    responses_before = await redis.xlen("automation_responses")
    
    print(f"\n📊 Before test:")
    print(f"   Events stream: {events_before}")
    print(f"   Responses stream: {responses_before}")
    
    # Publish test message
    test_message = {
        "conversation_id": f"latency_test_{uuid.uuid4().hex[:8]}",
        "user_id": "test_user_latency",
        "message_id": f"msg_{uuid.uuid4().hex[:8]}",
        "thread_id": "test_user_latency:thread_001",
        "provider": "test",
        "trace_id": str(uuid.uuid4()),
        "automation_enabled": True,
        "_priority": 0,  # High priority
        "_schema_version": 2,
        "ts": time.time(),
        "content": "What are your business hours?",
        "subject": "Business hours inquiry"
    }
    
    start_time = time.time()
    
    await redis.xadd(
        "automation_events",
        {"data": json.dumps(test_message)},
        maxlen=10_000,
        approximate=True
    )
    
    print(f"\n⏱️  Test message published at {start_time:.2f}")
    print(f"   Waiting for response (max 30 seconds)...")
    
    # Poll for response
    for i in range(30):
        await asyncio.sleep(1)
        
        responses_after = await redis.xlen("automation_responses")
        
        if responses_after > responses_before:
            end_time = time.time()
            latency = end_time - start_time
            
            print(f"\n✅ Response detected!")
            print(f"   Latency: {latency:.2f} seconds")
            
            if latency < 5:
                print(f"   🚀 Excellent performance!")
            elif latency < 10:
                print(f"   ✓ Good performance")
            else:
                print(f"   ⚠️  Slow performance (check workers)")
            
            return True
        
        if i % 5 == 0:
            print(f"   ... waiting ({i}s)")
    
    print(f"\n⚠️  No response received within 30 seconds")
    print(f"   This may indicate:")
    print(f"   - Worker runtime not started")
    print(f"   - Pipeline error occurring")
    print(f"   - Check automation-service logs")
    
    return False


async def main():
    """Run all tests"""
    
    print("\n" + "=" * 70)
    print("AUTOMATION SERVICE - END-TO-END TEST SUITE")
    print("=" * 70)
    print("\nThis test validates the complete workflow:")
    print("  1. Message publishing to automation_events")
    print("  2. Consumer group setup")
    print("  3. Message consumption by workers")
    print("  4. Response generation and publishing")
    print("  5. End-to-end latency")
    
    results = []
    
    # Test 1: Publish
    success, test_msg = await test_publish_to_automation_events()
    results.append(("Publish to Stream", success))
    
    if not success:
        print("\n❌ Cannot proceed without successful publish")
        return 1
    
    # Test 2: Consumer group
    success = await test_check_consumer_group()
    results.append(("Consumer Group", success))
    
    # Test 3: Read from stream
    success = await test_read_from_stream()
    results.append(("Read from Stream", success))
    
    # Test 4: Check responses
    success = await test_check_response_stream()
    results.append(("Response Stream", success))
    
    # Test 5: Latency
    success = await test_workflow_latency()
    results.append(("Workflow Latency", success))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:30s} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All tests passed! Workflow is functioning correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the automation-service logs.")
        print("\nCommon issues:")
        print("  - Worker runtime not started in main.py")
        print("  - OpenAI API key not configured")
        print("  - Qdrant collection not populated with data")
        print("  - Pipeline errors in orchestrators")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
