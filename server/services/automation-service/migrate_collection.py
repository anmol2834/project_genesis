"""
Qdrant Collection Migration — 384-dim → 768-dim
================================================
Recreates the business_context collection at 768-dim (Cosine) to match
intfloat/e5-base-v2. Uses the same AsyncQdrantClient connection the service uses.

Run:
    cd server/services/automation-service
    python migrate_collection.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from shared.config import get_config


async def migrate():
    cfg = get_config()
    url = cfg.QDRANT_URL
    collection = cfg.QDRANT_COLLECTION
    target_dim = cfg.QDRANT_VECTOR_SIZE  # 768

    print("=" * 60)
    print("QDRANT COLLECTION MIGRATION")
    print("=" * 60)
    print(f"URL        : {url}")
    print(f"Collection : {collection}")
    print(f"Target dim : {target_dim}")

    # Connect exactly as resource_management.py does
    raw_url = url.replace("http://", "").replace("https://", "")
    parts = raw_url.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 6333

    client = AsyncQdrantClient(host=host, port=port, timeout=30)

    # Check existing
    cols = await client.get_collections()
    names = [c.name for c in cols.collections]
    print(f"\nExisting collections: {names}")

    if collection in names:
        info = await client.get_collection(collection)
        current_dim = info.config.params.vectors.size
        points = info.points_count or 0
        print(f"Current dim    : {current_dim}")
        print(f"Current points : {points}")

        if current_dim == target_dim:
            print(f"\n[OK] Collection already at {target_dim}-dim. Nothing to do.")
            await client.close()
            return

        print(f"\n[MISMATCH] {current_dim}-dim != {target_dim}-dim")
        if points > 0:
            print(f"WARNING: {points} existing vectors will be DELETED.")
            print("Re-upload via user-service Celery tasks after this runs.")
        confirm = input("Delete and recreate at 768-dim? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            await client.close()
            return

        await client.delete_collection(collection)
        print(f"[OK] Deleted '{collection}'")
    else:
        print(f"\nCollection '{collection}' not found — will create.")

    await client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
    )
    print(f"[OK] Created '{collection}' at {target_dim}-dim (Cosine)")

    # Verify
    info = await client.get_collection(collection)
    actual = info.config.params.vectors.size
    assert actual == target_dim, f"Verification failed: {actual} != {target_dim}"
    print(f"[VERIFIED] {collection}: {actual}-dim, Cosine, 0 points")

    await client.close()

    print("\n" + "=" * 60)
    print("DONE. Next steps:")
    print("  1. Re-ingest data via user-service (Celery embed tasks)")
    print("  2. Restart automation-service")
    print("  3. python validate_rc_all.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
