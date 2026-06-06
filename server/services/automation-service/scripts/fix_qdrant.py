"""
Fix Qdrant Collection — Correct Vector Dimensions
===================================================
The collection was previously (incorrectly) created at 384-dim by an old script.
automation-service uses intfloat/e5-base-v2 which produces 768-dim vectors.
QDRANT_VECTOR_SIZE in shared config is 768 (Cosine).

This script recreates the collection at 768-dim.
WARNING: All existing points are deleted — re-upload data via user-service afterwards.

Run from automation-service directory:
    python scripts/fix_qdrant.py
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from shared.config import get_config


def fix_qdrant_collection():
    print("=" * 70)
    print("QDRANT COLLECTION FIX — restoring 768-dim for intfloat/e5-base-v2")
    print("=" * 70)

    config = get_config()
    target_dim = config.QDRANT_VECTOR_SIZE   # 768 from shared config
    collection = config.QDRANT_COLLECTION    # business_context

    print(f"\nQdrant URL  : {config.QDRANT_URL}")
    print(f"Collection  : {collection}")
    print(f"Target dim  : {target_dim}  (must match intfloat/e5-base-v2 output)")

    url = config.QDRANT_URL.replace("http://", "").replace("https://", "")
    host, port = (url.split(":") + ["6333"])[:2]
    client = QdrantClient(host=host, port=int(port), timeout=30)

    existing = [c.name for c in client.get_collections().collections]
    if collection in existing:
        info = client.get_collection(collection)
        current_dim = info.config.params.vectors.size
        print(f"\nExisting collection dim : {current_dim}")

        if current_dim == target_dim:
            print(f"[OK] Collection already at {target_dim}-dim — no action needed.")
            client.close()
            return True

        print(f"[MISMATCH] {current_dim}-dim != {target_dim}-dim")
        print("This will DELETE all existing vectors. Re-upload via user-service after.")
        confirm = input("Delete and recreate? (yes/no): ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            client.close()
            return False

        client.delete_collection(collection)
        print(f"[OK] Deleted '{collection}'")
    else:
        print(f"\nCollection '{collection}' does not exist — creating.")

    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
    )
    print(f"[OK] Created '{collection}' at {target_dim}-dim (Cosine)")

    # Verify
    info = client.get_collection(collection)
    actual = info.config.params.vectors.size
    if actual != target_dim:
        print(f"[ERROR] Verification failed: got {actual}, expected {target_dim}")
        client.close()
        return False

    print(f"[VERIFIED] Collection '{collection}': {actual}-dim, Cosine, 0 points")
    client.close()

    print("\n" + "=" * 70)
    print("DONE. Required next steps:")
    print("  1. Re-ingest ALL business knowledge via user-service Celery tasks")
    print("     The collection is now empty. All vectors must be re-uploaded.")
    print("  2. Restart automation-service")
    print("  3. Run: python validate_rc_all.py")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        ok = fix_qdrant_collection()
        sys.exit(0 if ok else 1)
    except Exception as exc:
        print(f"\n[FATAL] {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
