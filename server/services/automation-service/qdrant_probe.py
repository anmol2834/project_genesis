import sys, os, asyncio, json, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.config import get_config
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams


async def run():
    cfg = get_config()
    url = cfg.QDRANT_URL.replace("http://", "").replace("https://", "")
    parts = url.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 6333
    target_dim = cfg.QDRANT_VECTOR_SIZE
    collection = cfg.QDRANT_COLLECTION

    print(f"QDRANT_URL  = {cfg.QDRANT_URL}")
    print(f"host={host}  port={port}")
    print(f"collection  = {collection}")
    print(f"target_dim  = {target_dim}")

    qc = AsyncQdrantClient(host=host, port=port, timeout=15)

    try:
        t0 = time.perf_counter()
        cols = await qc.get_collections()
        ms = (time.perf_counter() - t0) * 1000
        names = [c.name for c in cols.collections]
        print(f"\nConnected in {ms:.1f}ms  collections={names}")
    except Exception as e:
        print(f"\nCONNECTION FAILED: {e}")
        return

    if collection not in names:
        print(f"\nCollection '{collection}' MISSING — creating at {target_dim}-dim")
        await qc.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
        )
        info = await qc.get_collection(collection)
        print(f"Created: dim={info.config.params.vectors.size}")
        await qc.close()
        return

    info = await qc.get_collection(collection)
    current_dim = info.config.params.vectors.size
    points = info.points_count or 0
    print(f"\nCollection '{collection}': dim={current_dim}  points={points}")

    if current_dim == target_dim:
        print(f"\n[OK] Collection already at {target_dim}-dim. No migration needed.")
        print("IMPORTANT: Check that data is uploaded (points > 0).")
        await qc.close()
        return

    print(f"\n[MISMATCH] {current_dim}-dim vs target {target_dim}-dim")
    print(f"  {points} points will be DELETED.")
    confirm = input("Recreate at 768-dim? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        await qc.close()
        return

    await qc.delete_collection(collection)
    print(f"Deleted '{collection}'")

    await qc.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=target_dim, distance=Distance.COSINE),
    )
    info = await qc.get_collection(collection)
    actual = info.config.params.vectors.size
    assert actual == target_dim, f"Verification failed: {actual}"
    print(f"\n[OK] Recreated '{collection}': {actual}-dim, Cosine, 0 points")
    print("\nNext steps:")
    print("  1. Re-ingest data via user-service Celery embed tasks")
    print("  2. Restart automation-service")
    print("  3. python validate_rc_all.py")

    await qc.close()


if __name__ == "__main__":
    asyncio.run(run())
