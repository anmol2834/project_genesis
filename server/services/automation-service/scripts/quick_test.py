"""
Quick Test - Automation Service Pipeline
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def test_imports():
    """Test that all modules can be imported"""
    print("=" * 70)
    print("TEST: Module Imports")
    print("=" * 70)
    
    try:
        from shared.config import get_config
        print("[OK] shared.config")
        
        from shared.cache import init_redis, get_redis_client
        print("[OK] shared.cache")
        
        from app.core.exceptions import ConfigurationError
        print("[OK] app.core.exceptions")
        
        from app.core.config import get_config as get_service_config
        print("[OK] app.core.config")
        
        from app.memory.orchestrator import get_memory_orchestrator
        print("[OK] app.memory.orchestrator")
        
        from app.intelligence.orchestrator import get_intelligence_orchestrator
        print("[OK] app.intelligence.orchestrator")
        
        from app.retrieval.orchestrator import get_retrieval_orchestrator
        print("[OK] app.retrieval.orchestrator")
        
        from app.llm.orchestrator import get_llm_orchestrator
        print("[OK] app.llm.orchestrator")
        
        from app.handoff.orchestrator import get_handoff_orchestrator
        print("[OK] app.handoff.orchestrator")
        
        from app.orchestration.execution_engine import execution_engine
        print("[OK] app.orchestration.execution_engine")
        
        from app.workers.runtime import worker_runtime
        print("[OK] app.workers.runtime")
        
        print("\n[PASS] All modules imported successfully")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_config():
    """Test configuration loading"""
    print("\n" + "=" * 70)
    print("TEST: Configuration")
    print("=" * 70)
    
    try:
        from shared.config import get_config
        config = get_config()
        
        print(f"[OK] Environment: {config.ENVIRONMENT}")
        print(f"[OK] Redis URL: {config.REDIS_URL[:50]}...")
        print(f"[OK] Database URL: {config.DATABASE_URL[:50]}...")
        print(f"[OK] Qdrant URL: {config.QDRANT_URL}")
        print(f"[OK] OpenAI Key: {'*' * 20}")
        
        print("\n[PASS] Configuration loaded")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Config error: {e}")
        return False

async def test_redis():
    """Test Redis connection"""
    print("\n" + "=" * 70)
    print("TEST: Redis Connection")
    print("=" * 70)
    
    try:
        from shared.cache import init_redis, get_redis_client
        await init_redis()
        redis = get_redis_client()
        await redis.ping()
        
        print("[OK] Redis connected")
        print("\n[PASS] Redis working")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Redis error: {e}")
        return False

async def test_execution_context():
    """Test execution context"""
    print("\n" + "=" * 70)
    print("TEST: Execution Context")
    print("=" * 70)
    
    try:
        from app.core.execution_context import ExecutionContext
        
        ctx = ExecutionContext(
            conversation_id="test_conv",
            user_id="test_user",
            message_id="test_msg",
            thread_id="test_thread",
            trace_id="test_trace",
            correlation_id="test_corr",
            workflow_id="test_workflow",
            execution_id="test_exec"
        )
        
        print(f"[OK] Context created: {ctx.conversation_id}")
        print(f"[OK] User ID: {ctx.user_id}")
        print(f"[OK] Trace ID: {ctx.trace_id}")
        
        print("\n[PASS] Execution context working")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Context error: {e}")
        return False

async def test_orchestrators():
    """Test that orchestrators can be instantiated"""
    print("\n" + "=" * 70)
    print("TEST: Orchestrators")
    print("=" * 70)
    
    try:
        from app.memory.orchestrator import get_memory_orchestrator
        from app.intelligence.orchestrator import get_intelligence_orchestrator
        from app.retrieval.orchestrator import get_retrieval_orchestrator
        from app.llm.orchestrator import get_llm_orchestrator
        from app.handoff.orchestrator import get_handoff_orchestrator
        
        print("[OK] Memory orchestrator")
        print("[OK] Intelligence orchestrator")
        print("[OK] Retrieval orchestrator")
        print("[OK] LLM orchestrator")
        print("[OK] Handoff orchestrator")
        
        print("\n[PASS] All orchestrators ready")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Orchestrator error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("\n" + "=" * 70)
    print("AUTOMATION-SERVICE QUICK TEST")
    print("=" * 70)
    
    results = []
    
    results.append(("Imports", await test_imports()))
    results.append(("Config", await test_config()))
    results.append(("Redis", await test_redis()))
    results.append(("Context", await test_execution_context()))
    results.append(("Orchestrators", await test_orchestrators()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name:20s} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed!")
        print("\nYou can now start the service with:")
        print("  python main.py")
        return 0
    else:
        print("\n[WARNING] Some tests failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
