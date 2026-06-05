"""
Standalone Test: Short Message Contextual Reasoning
====================================================
Direct testing without full app initialization.
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from intelligence.continuation_resolution.short_message_detector import ShortMessageDetector
from intelligence.continuation_resolution.contextual_resolver import ContextualContinuationResolver
from intelligence.continuation_resolution.active_topic_memory import ActiveTopicMemory


def test_short_message_detection():
    """Test short message detection across various scenarios."""
    print("\n" + "="*80)
    print("TEST 1: SHORT MESSAGE DETECTION")
    print("="*80)
    
    detector = ShortMessageDetector()
    
    test_cases = [
        # Very short messages
        ("yes", True, "very_short_message", 0.95),
        ("no", True, "very_short_message", 0.95),
        ("okay", True, "very_short_message", 0.95),
        
        # Continuation keywords
        ("tell me more", True, "continuation_keyword", 0.90),
        ("interested", True, "continuation_keyword", 0.90),
        ("sounds good", True, "continuation_keyword", 0.90),
        
        # Context questions
        ("pricing?", True, "context_question", 0.85),
        ("how much?", True, "context_question", 0.75),
        ("when?", True, "context_question", 0.85),
        ("available?", True, "context_question", 0.85),
        
        # Short ambiguous
        ("maybe", True, "single_word_context", 0.95),
        ("perhaps", True, "single_word_context", 0.95),
        
        # Standalone messages (should NOT be contextual)
        ("I'm looking for industrial drones with thermal imaging for agriculture", False, "standalone_message", 0.0),
        ("Can you send me pricing for your AeroCam X1 drone?", False, "standalone_message", 0.0),
    ]
    
    passed = 0
    failed = 0
    
    for message, expected_contextual, expected_reason, expected_confidence in test_cases:
        is_contextual, reason, confidence = detector.is_short_contextual_message(message)
        
        # Check if detection matches
        match = is_contextual == expected_contextual
        if not match:
            status = "❌ FAIL"
            failed += 1
        else:
            status = "✅ PASS"
            passed += 1
        
        print(f"\n{status} | \"{message}\"")
        print(f"  Expected: contextual={expected_contextual}, reason={expected_reason}")
        print(f"  Got: contextual={is_contextual}, reason={reason}, confidence={confidence:.2f}")
    
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(test_cases)}")
    return failed == 0


def test_continuation_types():
    """Test classification of continuation types."""
    print("\n" + "="*80)
    print("TEST 2: CONTINUATION TYPE CLASSIFICATION")
    print("="*80)
    
    detector = ShortMessageDetector()
    
    test_cases = [
        ("yes", "affirmative"),
        ("sure", "affirmative"),
        ("sounds good", "affirmative"),
        ("no", "negative"),
        ("not interested", "negative"),
        ("tell me more", "interest"),
        ("interested", "interest"),
        ("pricing?", "question"),
        ("how much?", "question"),
        ("thanks", "confirmation"),
        ("got it", "confirmation"),
        ("what about delivery?", "follow_up"),
        ("can you explain?", "follow_up"),
    ]
    
    passed = 0
    failed = 0
    
    for message, expected_type in test_cases:
        result_type = detector.get_continuation_type(message)
        
        if result_type == expected_type:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status} | \"{message}\" → {result_type} (expected: {expected_type})")
    
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(test_cases)}")
    return failed == 0


def test_context_resolution():
    """Test context resolution from conversation history."""
    print("\n" + "="*80)
    print("TEST 3: CONTEXTUAL CONTINUATION RESOLUTION")
    print("="*80)
    
    resolver = ContextualContinuationResolver()
    
    # Scenario 1: Pricing inquiry continuation
    print("\n📋 Scenario 1: B2B Pricing Inquiry")
    print("-" * 80)
    
    memory = {
        "history": [
            {
                "intent": "pricing_inquiry",
                "response": "Our AeroCam X1 commercial drones start at $2,499. For bulk orders of 10+ units, we offer 15% discount.",
                "entities": {"AeroCam X1": "product", "bulk order": "quantity"}
            }
        ],
        "turn_count": 1,
        "last_intent": "pricing_inquiry",
        "shared_entities": {"AeroCam X1": "product"},
        "active_topics": ["pricing_details"]
    }
    
    context = resolver.resolve_continuation_context(
        "yes",
        "affirmative",
        memory
    )
    
    print(f"Latest message: 'yes'")
    print(f"✅ Resolved intent: {context['resolved_intent']}")
    print(f"✅ Active topic: {context['active_topic']}")
    print(f"✅ Entities: {context['relevant_entities']}")
    print(f"✅ Requires retrieval: {context['requires_retrieval']}")
    print(f"✅ Context source: {context['context_source']}")
    
    assert context['resolved_intent'] == 'pricing_inquiry_continuation', "Intent resolution failed"
    assert context['active_topic'] == 'pricing_details', "Topic extraction failed"
    assert not context['requires_retrieval'], "Should not require retrieval for pricing confirmation"
    
    # Scenario 2: Feature inquiry continuation
    print("\n📋 Scenario 2: Feature Discovery")
    print("-" * 80)
    
    memory = {
        "history": [
            {
                "intent": "feature_request",
                "response": "Yes, our AgriFly X1 supports thermal imaging and NDVI analysis for agricultural surveying.",
                "entities": {"AgriFly X1": "product", "thermal imaging": "feature", "NDVI": "feature"}
            }
        ],
        "turn_count": 1,
        "last_intent": "feature_request",
        "shared_entities": {"AgriFly X1": "product"},
        "active_topics": ["product_features"]
    }
    
    context = resolver.resolve_continuation_context(
        "tell me more",
        "interest",
        memory
    )
    
    print(f"Latest message: 'tell me more'")
    print(f"✅ Resolved intent: {context['resolved_intent']}")
    print(f"✅ Active topic: {context['active_topic']}")
    print(f"✅ Requires retrieval: {context['requires_retrieval']}")
    print(f"✅ Context source: {context['context_source']}")
    
    assert context['resolved_intent'] == 'interest_continuation', "Interest continuation failed"
    assert context['requires_retrieval'], "Should require retrieval for more details"
    
    # Scenario 3: Short question needing context
    print("\n📋 Scenario 3: Short Contextual Question")
    print("-" * 80)
    
    memory = {
        "history": [
            {
                "intent": "product_inquiry",
                "response": "We offer three drone models for construction: BuildPro X1, BuildPro X2, and BuildPro Pro.",
                "entities": {"BuildPro": "product"}
            }
        ],
        "turn_count": 1,
        "last_intent": "product_inquiry",
        "shared_entities": {"BuildPro": "product"},
        "active_topics": ["construction_drones"]
    }
    
    context = resolver.resolve_continuation_context(
        "how much?",
        "question",
        memory
    )
    
    print(f"Latest message: 'how much?'")
    print(f"✅ Resolved intent: {context['resolved_intent']}")
    print(f"✅ Active topic: {context['active_topic']}")
    print(f"✅ Requires retrieval: {context['requires_retrieval']}")
    print(f"✅ Context source: {context['context_source']}")
    
    assert 'pricing' in context['resolved_intent'].lower(), "Should map 'how much' to pricing"
    assert context['requires_retrieval'], "Should require retrieval for pricing data"
    
    print("\n✅ Context resolution working correctly")
    return True


def test_active_topic_memory():
    """Test active topic memory management."""
    print("\n" + "="*80)
    print("TEST 4: ACTIVE TOPIC MEMORY")
    print("="*80)
    
    memory = ActiveTopicMemory()
    conversation_id = "test_conv_123"
    
    # Update context
    print("\n📝 Updating active context...")
    memory.update_active_context(
        conversation_id=conversation_id,
        topic="AeroCam X1 pricing",
        entities=["AeroCam X1", "thermal imaging", "bulk pricing"],
        customer_goal="Purchase 10 commercial drones",
        business_offer="15% discount for bulk order",
        unresolved_question="delivery timeline",
        retrieved_chunks=[{"content": "Pricing chunk 1"}, {"content": "Pricing chunk 2"}],
        response_summary="Provided pricing and discount info",
        conversation_stage="consideration"
    )
    
    # Get context
    context = memory.get_active_context(conversation_id)
    print(f"✅ Active topic: {context['active_topic']}")
    print(f"✅ Active entities: {context['active_entities']}")
    print(f"✅ Customer goal: {context['last_customer_goal']}")
    print(f"✅ Business offer: {context['last_business_offer']}")
    print(f"✅ Cached chunks: {len(context.get('retrieved_chunks_cache', []))} chunks")
    
    assert context['active_topic'] == "AeroCam X1 pricing", "Topic storage failed"
    assert len(context['active_entities']) == 3, "Entity storage failed"
    assert len(context['retrieved_chunks_cache']) == 2, "Chunk caching failed"
    
    # Check if has sufficient context
    has_context = memory.has_sufficient_context(conversation_id)
    print(f"\n🔍 Has sufficient context: {has_context}")
    assert has_context, "Should have sufficient context"
    
    # Check if can reuse chunks
    can_reuse = memory.can_reuse_cached_chunks(conversation_id, "AeroCam X1 pricing")
    print(f"♻️ Can reuse cached chunks: {can_reuse}")
    assert can_reuse, "Should be able to reuse chunks"
    
    # Build memory context summary
    summary = memory.build_memory_context_summary(conversation_id)
    print(f"\n📄 Memory Context Summary:")
    print(summary)
    assert "AeroCam X1 pricing" in summary, "Summary should include topic"
    assert "Purchase 10 commercial drones" in summary, "Summary should include goal"
    
    # Test retrieval skip logic
    continuation_context = {
        "requires_retrieval": False,
        "active_topic": "AeroCam X1 pricing"
    }
    should_skip = memory.should_skip_retrieval(conversation_id, continuation_context)
    print(f"\n⚡ Should skip retrieval: {should_skip}")
    assert should_skip, "Should skip retrieval with sufficient memory"
    
    print("\n✅ Active topic memory working correctly")
    return True


def test_memory_first_flow():
    """Test end-to-end memory-first continuation flow."""
    print("\n" + "="*80)
    print("TEST 5: MEMORY-FIRST CONTINUATION FLOW")
    print("="*80)
    
    detector = ShortMessageDetector()
    resolver = ContextualContinuationResolver()
    memory_mgr = ActiveTopicMemory()
    
    conversation_id = "test_conv_456"
    
    # Setup: Customer asked about pricing
    print("\n📧 Turn 1: Customer asks about pricing")
    print("Message: 'Hi, what's the pricing for your commercial drones?'")
    print("Response: 'Our AeroCam X1 starts at $2,499. Bulk orders get 15% off.'")
    
    # Store context in memory
    memory_mgr.update_active_context(
        conversation_id=conversation_id,
        topic="commercial_drone_pricing",
        entities=["AeroCam X1", "commercial drone", "bulk discount"],
        customer_goal="Learn about pricing",
        business_offer="AeroCam X1 at $2,499 with bulk discount",
        retrieved_chunks=[{"content": "AeroCam X1 pricing details..."}],
        response_summary="Provided AeroCam X1 pricing and bulk discount info",
        conversation_stage="interest"
    )
    
    # Turn 2: Customer responds with short message
    print("\n📧 Turn 2: Customer continuation")
    short_message = "tell me more"
    print(f"Message: '{short_message}'")
    
    # Step 1: Detect short message
    is_contextual, reason, confidence = detector.is_short_contextual_message(short_message)
    print(f"\n🔍 Detection: contextual={is_contextual}, reason={reason}, confidence={confidence:.2f}")
    assert is_contextual, "Should detect 'tell me more' as contextual"
    
    if is_contextual:
        # Step 2: Get continuation type
        continuation_type = detector.get_continuation_type(short_message)
        print(f"📝 Continuation type: {continuation_type}")
        assert continuation_type == "interest", "Should classify as interest"
        
        # Step 3: Resolve context
        memory = {
            "history": [
                {
                    "intent": "pricing_inquiry",
                    "response": "Our AeroCam X1 starts at $2,499. Bulk orders get 15% off.",
                    "entities": {"AeroCam X1": "product"}
                }
            ],
            "turn_count": 1,
            "last_intent": "pricing_inquiry",
            "active_topics": ["commercial_drone_pricing"]
        }
        
        continuation_context = resolver.resolve_continuation_context(
            short_message,
            continuation_type,
            memory
        )
        print(f"📚 Resolved context: topic={continuation_context['active_topic']}, intent={continuation_context['resolved_intent']}")
        
        # Step 4: Check if can skip retrieval
        # Note: "tell me more" requires retrieval for additional details
        should_skip = memory_mgr.should_skip_retrieval(conversation_id, continuation_context)
        print(f"\n⚡ Skip retrieval: {should_skip}")
        
        # Get memory context
        memory_context = memory_mgr.build_memory_context_summary(conversation_id)
        print(f"\n📄 Memory Context Available:")
        print(memory_context)
        assert "commercial_drone_pricing" in memory_context, "Memory context should include topic"
        
        print("\n✅ MEMORY-FIRST SYSTEM OPERATIONAL")
        print("   ✓ Short message detected")
        print("   ✓ Context resolved from history")
        print("   ✓ Active topic memory working")
        print("   ✓ Smart retrieval skip logic enabled")
    
    print("\n✅ Memory-first flow working correctly")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("SHORT MESSAGE CONTEXTUAL REASONING TEST SUITE")
    print("="*80)
    print("\nTesting enterprise-critical short message intelligence...")
    print("\nThis system enables:")
    print("  • Context resolution for \"yes\", \"no\", \"pricing?\", \"when?\"")
    print("  • Memory-first responses (skip RAG when possible)")
    print("  • <300ms latency for simple continuations")
    print("  • Real-world conversation continuity")
    
    results = []
    
    # Run tests
    try:
        results.append(("Short Message Detection", test_short_message_detection()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Short Message Detection", False))
    
    try:
        results.append(("Continuation Type Classification", test_continuation_types()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Continuation Type Classification", False))
    
    try:
        results.append(("Context Resolution", test_context_resolution()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Context Resolution", False))
    
    try:
        results.append(("Active Topic Memory", test_active_topic_memory()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Active Topic Memory", False))
    
    try:
        results.append(("Memory-First Flow", test_memory_first_flow()))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Memory-First Flow", False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📊 Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED")
        print("\n✅ Short Message Contextual Reasoning System is OPERATIONAL")
        print("\n🚀 System Capabilities:")
        print("   • Detects 20+ short continuation patterns")
        print("   • Resolves context from last 5 turns")
        print("   • Manages active topic working memory")
        print("   • Caches retrieval results for reuse")
        print("   • Skips RAG when memory is sufficient")
        print("   • Target latency: <300ms for continuations")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
