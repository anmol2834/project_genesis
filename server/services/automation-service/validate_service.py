"""
Final Validation Test - Complete Pipeline
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("=" * 70)
print("AUTOMATION-SERVICE FINAL VALIDATION")
print("=" * 70)

# Test 1: Import all critical modules
print("\n[TEST 1] Import Critical Modules")
try:
    from app.memory.orchestrator import get_memory_orchestrator
    print("  [OK] Memory Orchestrator")
    
    from app.intelligence.orchestrator import get_intelligence_orchestrator  
    print("  [OK] Intelligence Orchestrator")
    
    from app.retrieval.orchestrator import get_retrieval_orchestrator
    print("  [OK] Retrieval Orchestrator")
    
    from app.llm.orchestrator import get_llm_orchestrator
    print("  [OK] LLM Orchestrator")
    
    from app.handoff.orchestrator import get_handoff_orchestrator
    print("  [OK] Handoff Orchestrator")
    
    from app.orchestration.execution_engine import execution_engine
    print("  [OK] Execution Engine")
    
    from app.workers.runtime import get_worker_runtime
    print("  [OK] Worker Runtime")
    
    print("\n[PASS] All imports successful")
except Exception as e:
    print(f"\n[FAIL] Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Check configuration
print("\n[TEST 2] Configuration")
try:
    from shared.config import get_config
    config = get_config()
    print(f"  Environment: {config.ENVIRONMENT}")
    print(f"  Redis: {config.REDIS_URL[:50]}...")
    print(f"  Database: {config.DATABASE_URL[:50]}...")
    print(f"  Qdrant: {config.QDRANT_URL}")
    print(f"  OpenAI Key: {'SET' if config.OPENAI_API_KEY else 'MISSING'}")
    print("\n[PASS] Configuration loaded")
except Exception as e:
    print(f"\n[FAIL] Config error: {e}")
    sys.exit(1)

# Test 3: Create execution context
print("\n[TEST 3] Execution Context")
try:
    from app.models.events import AutomationEvent
    from app.models.enums import EventType
    from datetime import datetime
    
    event = AutomationEvent(
        event_id="test_123",
        event_type=EventType.INCOMING_MESSAGE,
        user_id="test_user",
        trace_id="test_trace",
        correlation_id="test_corr",
        created_at=datetime.utcnow(),
        message_id="msg_123",
        conversation_id="conv_123",
        thread_id="test_user:thread_123",
        content="Hello, what are your pricing plans?",
        subject="Pricing inquiry"
    )
    
    print(f"  Event ID: {event.event_id}")
    print(f"  User ID: {event.user_id}")
    print(f"  Content: {event.content[:50]}...")
    print("\n[PASS] Event model working")
except Exception as e:
    print(f"\n[FAIL] Event error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test orchestrator instantiation
print("\n[TEST 4] Orchestrator Instantiation")
try:
    memory_orch = get_memory_orchestrator()
    print("  [OK] Memory Orchestrator instance")
    
    intelligence_orch = get_intelligence_orchestrator()
    print("  [OK] Intelligence Orchestrator instance")
    
    retrieval_orch = get_retrieval_orchestrator()
    print("  [OK] Retrieval Orchestrator instance")
    
    llm_orch = get_llm_orchestrator()
    print("  [OK] LLM Orchestrator instance")
    
    handoff_orch = get_handoff_orchestrator()
    print("  [OK] Handoff Orchestrator instance")
    
    print("\n[PASS] All orchestrators instantiated")
except Exception as e:
    print(f"\n[FAIL] Orchestrator error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: FastAPI app creation
print("\n[TEST 5] FastAPI Application")
try:
    import main
    app = main.app
    
    print(f"  App title: {app.title}")
    print(f"  App version: {app.version}")
    print(f"  Routes: {len(app.routes)}")
    
    print("\n[PASS] FastAPI app created")
except Exception as e:
    print(f"\n[FAIL] FastAPI error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("VALIDATION COMPLETE - ALL TESTS PASSED")
print("=" * 70)
print("\nPipeline stages:")
print("  1. Conversation Memory Engine")
print("  2. Intent Understanding (ChatGPT Brain #1)")
print("  3. Query Planning")
print("  4. Multi-Stage Retrieval")
print("  5. Context Validation + Compression")
print("  6. Grounded Prompt Builder")
print("  7. LLM Reasoning (ChatGPT Brain #2)")
print("  8. Hallucination Guard")
print("  9. Confidence + Risk Engine")
print("  10. Human Handoff OR Send Reply")
print("\nService is ready to start with:")
print("  python main.py")
print("=" * 70)
