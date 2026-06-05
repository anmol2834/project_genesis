"""
Automation Service - Initialization Script
===========================================
Run this before starting the service to ensure all infrastructure is ready.
"""
import asyncio
import sys
import os

# Add paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.config import get_config
from shared.cache import init_redis, get_redis_client
from shared.database import init_database, get_engine
from app.core.resource_management import get_resource_manager, initialize_resources


async def check_redis_connection():
    """Check Redis connection"""
    print("🔍 Checking Redis connection...")
    config = get_config()
    print(f"   Redis URL: {config.REDIS_URL[:50]}...")
    
    await init_redis()
    redis = get_redis_client()
    
    try:
        await redis.ping()
        print("✅ Redis connection OK")
        return True
    except Exception as e:
        print(f"❌ Redis connection FAILED: {e}")
        return False


async def check_postgres_connection():
    """Check Postgres connection"""
    print("\n🔍 Checking Postgres connection...")
    config = get_config()
    print(f"   Database URL: {config.DATABASE_URL[:50]}...")
    
    await init_database()
    engine = get_engine()
    
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            row = result.fetchone()
            if row and row[0] == 1:
                print("✅ Postgres connection OK")
                return True
    except Exception as e:
        print(f"❌ Postgres connection FAILED: {e}")
        return False


async def check_qdrant_connection():
    """Check Qdrant connection"""
    print("\n🔍 Checking Qdrant connection...")
    config = get_config()
    print(f"   Qdrant URL: {config.QDRANT_URL}")
    
    try:
        await initialize_resources()
        manager = get_resource_manager()
        qdrant = manager.get_qdrant()
        
        collections = await qdrant.get_collections()
        print(f"✅ Qdrant connection OK ({len(collections.collections)} collections)")
        
        # Check if business_context collection exists
        collection_names = [c.name for c in collections.collections]
        if config.QDRANT_COLLECTION in collection_names:
            print(f"✅ Collection '{config.QDRANT_COLLECTION}' exists")
        else:
            print(f"⚠️  Collection '{config.QDRANT_COLLECTION}' NOT FOUND")
            print(f"   Available collections: {collection_names}")
        
        return True
    except Exception as e:
        print(f"❌ Qdrant connection FAILED: {e}")
        return False


async def ensure_consumer_group():
    """Ensure automation_events consumer group exists"""
    print("\n🔍 Setting up Redis Streams consumer group...")
    
    redis = get_redis_client()
    stream_name = "automation_events"
    group_name = "automation_workers"
    
    try:
        # Try to create consumer group
        await redis.xgroup_create(
            stream_name,
            group_name,
            id="0",
            mkstream=True
        )
        print(f"✅ Created consumer group: {group_name} on stream: {stream_name}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            print(f"✅ Consumer group already exists: {group_name}")
        else:
            print(f"❌ Consumer group creation FAILED: {e}")
            return False
    
    # Check stream length
    try:
        length = await redis.xlen(stream_name)
        print(f"   Stream '{stream_name}' has {length} pending messages")
    except:
        print(f"   Stream '{stream_name}' is empty or doesn't exist yet")
    
    return True


async def check_openai_config():
    """Check OpenAI configuration"""
    print("\n🔍 Checking OpenAI configuration...")
    config = get_config()
    
    api_key = config.OPENAI_API_KEY
    if api_key and len(api_key) > 20:
        masked_key = api_key[:10] + "..." + api_key[-4:]
        print(f"✅ OpenAI API Key configured: {masked_key}")
        print(f"   Model: {config.OPENAI_MODEL}")
        return True
    else:
        print("❌ OpenAI API Key NOT configured")
        return False


async def check_embedding_model():
    """Check if embedding model can be loaded"""
    print("\n🔍 Checking embedding model...")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        print("   Loading model: all-MiniLM-L6-v2...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Test embedding
        test_text = "Hello world"
        embedding = model.encode(test_text)
        
        print(f"✅ Embedding model loaded (dim={len(embedding)})")
        return True
    except Exception as e:
        print(f"❌ Embedding model load FAILED: {e}")
        print("   You may need to run: pip install sentence-transformers")
        return False


async def main():
    """Run all checks"""
    print("=" * 70)
    print("AUTOMATION-SERVICE INITIALIZATION CHECK")
    print("=" * 70)
    
    checks = []
    
    # Run checks
    checks.append(("Redis", await check_redis_connection()))
    checks.append(("Postgres", await check_postgres_connection()))
    checks.append(("Qdrant", await check_qdrant_connection()))
    checks.append(("Consumer Group", await ensure_consumer_group()))
    checks.append(("OpenAI", await check_openai_config()))
    checks.append(("Embeddings", await check_embedding_model()))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All checks passed! Service is ready to start.")
        print("\nStart the service with:")
        print("  python -m uvicorn app.main:app --host 0.0.0.0 --port 8009")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues before starting.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
