"""
Initialize Qdrant collection for user embeddings
Run this before starting the Celery worker
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.vector_db import create_collection, check_qdrant_health

config = get_config()

def init_qdrant_collection():
    """Initialize Qdrant collection if it doesn't exist"""
    print("Checking Qdrant connection...")
    
    if not check_qdrant_health():
        print("ERROR: Cannot connect to Qdrant at", config.QDRANT_URL)
        print("Please ensure Qdrant is running:")
        print("  docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant")
        return False
    
    print("Qdrant connection OK")
    print(f"Creating collection '{config.QDRANT_COLLECTION}' if not exists...")
    
    success = create_collection(
        collection_name=config.QDRANT_COLLECTION,
        vector_size=config.QDRANT_VECTOR_SIZE,
        distance=config.QDRANT_DISTANCE_METRIC
    )
    
    if success:
        print(f"Collection '{config.QDRANT_COLLECTION}' is ready")
        return True
    else:
        print(f"Failed to create collection '{config.QDRANT_COLLECTION}'")
        return False

if __name__ == "__main__":
    success = init_qdrant_collection()
    sys.exit(0 if success else 1)
