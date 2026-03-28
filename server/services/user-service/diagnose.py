"""
Diagnostic script for User Service Celery Worker
Checks all dependencies and configurations
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def check_redis():
    """Check Redis connection"""
    print("1. Checking Redis connection...")
    try:
        from shared.config import get_config
        import redis
        
        config = get_config()
        r = redis.from_url(config.REDIS_URL, decode_responses=True)
        r.ping()
        
        # Check connection info
        info = r.info('clients')
        print(f"   ✓ Redis connected: {config.REDIS_URL.split('@')[1]}")
        print(f"   ✓ Connected clients: {info.get('connected_clients', 'N/A')}")
        return True
    except Exception as e:
        print(f"   ✗ Redis connection failed: {e}")
        return False


def check_qdrant():
    """Check Qdrant connection"""
    print("\n2. Checking Qdrant connection...")
    try:
        from shared.vector_db import check_qdrant_health, get_qdrant_client
        from shared.config import get_config
        
        config = get_config()
        
        if not check_qdrant_health():
            print(f"   ✗ Qdrant not accessible at {config.QDRANT_URL}")
            print("   → Start Qdrant: docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant")
            return False
        
        client = get_qdrant_client()
        collections = client.get_collections()
        
        print(f"   ✓ Qdrant connected: {config.QDRANT_URL}")
        print(f"   ✓ Collections: {len(collections.collections)}")
        
        # Check if business_context collection exists
        collection_names = [c.name for c in collections.collections]
        if config.QDRANT_COLLECTION in collection_names:
            print(f"   ✓ Collection '{config.QDRANT_COLLECTION}' exists")
        else:
            print(f"   ⚠ Collection '{config.QDRANT_COLLECTION}' not found (will be created)")
        
        return True
    except Exception as e:
        print(f"   ✗ Qdrant connection failed: {e}")
        return False


def check_database():
    """Check PostgreSQL connection"""
    print("\n3. Checking PostgreSQL connection...")
    try:
        from sqlalchemy import create_engine, text
        from shared.config import get_config
        
        config = get_config()
        sync_url = config.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        connect_args = {}
        if "rds.amazonaws.com" in sync_url:
            connect_args["sslmode"] = "require"
        
        engine = create_engine(sync_url, connect_args=connect_args)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            count = result.scalar()
        
        engine.dispose()
        
        print(f"   ✓ PostgreSQL connected")
        print(f"   ✓ Users table accessible ({count} users)")
        return True
    except Exception as e:
        print(f"   ✗ PostgreSQL connection failed: {e}")
        return False


def check_celery_config():
    """Check Celery configuration"""
    print("\n4. Checking Celery configuration...")
    try:
        from shared.celery import get_celery_app
        
        app = get_celery_app()
        
        print(f"   ✓ Celery app name: {app.main}")
        print(f"   ✓ Broker: {app.conf.broker_url.split('@')[1] if '@' in app.conf.broker_url else app.conf.broker_url}")
        print(f"   ✓ Result backend: {app.conf.result_backend.split('@')[1] if '@' in app.conf.result_backend else app.conf.result_backend}")
        
        # Check registered tasks
        tasks = [t for t in app.tasks.keys() if not t.startswith('celery.')]
        print(f"   ✓ Registered tasks: {tasks}")
        
        return True
    except Exception as e:
        print(f"   ✗ Celery configuration failed: {e}")
        return False


def check_dependencies():
    """Check Python dependencies"""
    print("\n5. Checking Python dependencies...")
    required = [
        'celery',
        'redis',
        'qdrant_client',
        'sentence_transformers',
        'sqlalchemy',
        'psycopg2'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"   ✓ {package}")
        except ImportError:
            print(f"   ✗ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\n   Install missing packages: pip install {' '.join(missing)}")
        return False
    
    return True


def main():
    print("=" * 60)
    print("User Service Celery Worker - Diagnostic Check")
    print("=" * 60)
    
    results = {
        "Redis": check_redis(),
        "Qdrant": check_qdrant(),
        "PostgreSQL": check_database(),
        "Celery": check_celery_config(),
        "Dependencies": check_dependencies()
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_ok = True
    for name, status in results.items():
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}: {'OK' if status else 'FAILED'}")
        if not status:
            all_ok = False
    
    print("=" * 60)
    
    if all_ok:
        print("\n✓ All checks passed! You can start the worker.")
        print("\nRun: start-worker.bat")
    else:
        print("\n✗ Some checks failed. Fix the issues above before starting the worker.")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
