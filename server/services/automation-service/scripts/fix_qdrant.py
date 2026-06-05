"""
Fix Qdrant Collection - Correct Vector Dimensions
==================================================
The automation-service uses sentence-transformers/all-MiniLM-L6-v2 which produces
384-dimensional vectors, but the Qdrant collection is configured for 768 dimensions.

This script recreates the collection with the correct dimensions.
"""
import sys
import os

# Fix import paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from shared.config import get_config

def fix_qdrant_collection():
    print("=" * 70)
    print("QDRANT COLLECTION FIX")
    print("=" * 70)
    
    config = get_config()
    
    # Connect to Qdrant
    print(f"\nConnecting to Qdrant: {config.QDRANT_URL}")
    client = QdrantClient(url=config.QDRANT_URL)
    
    collection_name = config.QDRANT_COLLECTION
    print(f"Collection: {collection_name}")
    
    # Check current collection
    try:
        collections = client.get_collections()
        existing_collections = [c.name for c in collections.collections]
        
        if collection_name in existing_collections:
            info = client.get_collection(collection_name)
            current_size = info.config.params.vectors.size
            print(f"\n[INFO] Collection exists with vector size: {current_size}")
            
            if current_size == 384:
                print("[OK] Collection already has correct dimensions (384)")
                print("No changes needed.")
                return True
            
            print(f"[WARNING] Current size ({current_size}) != Expected size (384)")
            print("This will DELETE the existing collection and recreate it.")
            response = input("Continue? (yes/no): ")
            
            if response.lower() != "yes":
                print("Aborted.")
                return False
            
            print(f"\nDeleting collection '{collection_name}'...")
            client.delete_collection(collection_name)
            print("[OK] Collection deleted")
    except Exception as e:
        print(f"[INFO] Collection check: {e}")
    
    # Create collection with correct dimensions
    print(f"\nCreating collection...")
    print("  Model: sentence-transformers/all-MiniLM-L6-v2")
    print("  Dimensions: 384")
    print("  Distance: Cosine")
    
    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=384,  # Match all-MiniLM-L6-v2
                distance=Distance.COSINE
            )
        )
        print("[OK] Collection created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create collection: {e}")
        return False
    
    # Verify collection
    try:
        collection_info = client.get_collection(collection_name)
        print(f"\n[VERIFICATION]")
        print(f"  Vector size: {collection_info.config.params.vectors.size}")
        print(f"  Distance: {collection_info.config.params.vectors.distance}")
        print(f"  Points count: {collection_info.points_count}")
        
        if collection_info.config.params.vectors.size != 384:
            print("[ERROR] Vector size mismatch!")
            return False
        
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        return False
    
    client.close()
    
    print("\n" + "=" * 70)
    print("COLLECTION FIX COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Populate collection with drone business knowledge")
    print("  2. Run pipeline test: python test_pipeline_mock.py")
    print("  3. Verify retrieval is working")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = fix_qdrant_collection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
