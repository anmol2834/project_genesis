#!/usr/bin/env python3
"""
Quick Validation Script
========================
Validates that all automation-service components can be imported and basic setup works.
"""
import sys
import os

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(BASE_DIR, "../.."))
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, BASE_DIR)

# Force UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("=" * 80)
print("AUTOMATION-SERVICE VALIDATION")
print("=" * 80)

def test_import(module_name: str, description: str):
    """Test if module can be imported"""
    try:
        __import__(module_name)
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ {description} - {e}")
        return False

print("\n[1/10] Testing Core Imports...")
success = True
success &= test_import("app.core.config", "Core Configuration")
success &= test_import("app.core.resource_management", "Resource Management")
success &= test_import("app.observability", "Observability")

print("\n[2/10] Testing Intelligence Models...")
success &= test_import("app.intelligence.models.enterprise_intelligence", "Enterprise Intelligence Models")

print("\n[3/10] Testing Orchestrators...")
success &= test_import("app.memory.orchestrator", "Memory Orchestrator")

# Try both old and new intelligence orchestrator
try:
    from app.intelligence.orchestrator import get_intelligence_orchestrator
    print(f"✅ Intelligence Orchestrator (checking version...)")
    orch = get_intelligence_orchestrator()
    # Check if it's the enterprise version by checking return type
    import inspect
    sig = inspect.signature(orch.understand_intent)
    return_annotation = sig.return_annotation
    if 'EnterpriseIntelligenceResult' in str(return_annotation):
        print(f"   → ✅ ENTERPRISE VERSION ACTIVE")
    else:
        print(f"   → ⚠️  OLD VERSION (needs upgrade)")
except Exception as e:
    print(f"❌ Intelligence Orchestrator - {e}")
    import traceback
    print(f"   Debug traceback:")
    traceback.print_exc()
    success = False

success &= test_import("app.retrieval.orchestrator", "Retrieval Orchestrator")
success &= test_import("app.llm.orchestrator", "LLM Orchestrator")
success &= test_import("app.handoff.orchestrator", "Handoff Orchestrator")

print("\n[4/10] Testing Workers...")
success &= test_import("app.workers.consumer", "Stream Consumer")
success &= test_import("app.workers.processor", "Message Processor")
success &= test_import("app.workers.runtime", "Worker Runtime")

print("\n[5/10] Testing Models...")
success &= test_import("app.models.events", "Event Models")
success &= test_import("app.models.observability", "Observability Models")

print("\n[6/10] Testing Configuration...")
try:
    from app.core.config import get_config
    from shared.config import get_config as get_shared_config
    config = get_config()
    shared_config = get_shared_config()
    print(f"✅ Configuration Manager")
    print(f"   → Service: {config.service.service_name} v{config.service.version}")
    print(f"   → Port: {config.service.service_port}")
    print(f"   → Redis: {config.get_redis_url()[:50]}...")
    print(f"   → OpenAI Model: {shared_config.OPENAI_MODEL}")
except Exception as e:
    print(f"❌ Configuration Manager - {e}")
    success = False

print("\n[7/10] Checking OpenAI API Key...")
try:
    from app.core.config import get_config
    config = get_config()
    api_key = config.get_openai_api_key()
    if api_key and len(api_key) > 10:
        print(f"✅ OpenAI API Key Configured")
        print(f"   → Key prefix: {api_key[:15]}...")
    else:
        print(f"⚠️  OpenAI API Key Missing or Invalid")
        print(f"   → Set OPENAI_API_KEY in server/.env file")
except Exception as e:
    print(f"❌ OpenAI API Key Check Failed - {e}")

print("\n[8/10] Testing Enterprise Intelligence...")
try:
    from app.intelligence.models.enterprise_intelligence import (
        EnterpriseIntelligenceResult,
        ConversationAnalysis,
        IntentDefinition,
        EntityExtraction,
        SearchPlan,
        ConversationStage,
        CustomerType,
        Sentiment,
        Urgency,
        IntentType
    )
    print(f"✅ Enterprise Intelligence Models")
    print(f"   → ConversationStage: {len(ConversationStage)} stages")
    print(f"   → IntentType: {len(IntentType)} types")
    print(f"   → Sentiment: {len(Sentiment)} levels")
except Exception as e:
    print(f"❌ Enterprise Intelligence Models - {e}")
    success = False

print("\n[9/10] Testing Observability...")
try:
    from app.observability import get_logger, get_metrics_collector, get_tracer
    logger = get_logger("test")
    metrics = get_metrics_collector()
    tracer = get_tracer()
    print(f"✅ Observability Stack")
    print(f"   → Logger: {type(logger).__name__}")
    print(f"   → Metrics: {type(metrics).__name__}")
    print(f"   → Tracer: {type(tracer).__name__}")
except Exception as e:
    print(f"❌ Observability Stack - {e}")
    success = False

print("\n[10/10] Testing Orchestration...")
success &= test_import("app.orchestration.execution_engine", "Execution Engine")

print("\n" + "=" * 80)
if success:
    print("✅ ALL VALIDATION CHECKS PASSED")
    print("=" * 80)
    print("\nThe automation-service is properly configured and ready to run.")
    print("\nNext steps:")
    print("  1. Activate enterprise intelligence:")
    print("     copy app\\intelligence\\enterprise_orchestrator.py app\\intelligence\\orchestrator.py")
    print("  2. Run full pipeline test:")
    print("     python test_enterprise_pipeline.py")
    print("  3. Start the service:")
    print("     python main.py")
else:
    print("❌ VALIDATION FAILED")
    print("=" * 80)
    print("\nSome components failed to load. Check the errors above.")
    print("Common issues:")
    print("  - Missing dependencies: pip install -r requirements.txt")
    print("  - Missing .env file: copy .env.example to server/.env")
    print("  - Python path issues: run from automation-service directory")

print("=" * 80)
