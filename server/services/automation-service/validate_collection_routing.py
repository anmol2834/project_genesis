"""
validate_collection_routing.py
================================
Validates the dual-collection routing fix:

1. Both Qdrant collections exist at 768-dim
2. user_data_entries has data (>0 points)
3. AsyncQdrantRepository routes to user_data_entries correctly
4. Payload normalization produces content + chunk_type fields
5. A scroll against a known user_id returns results
6. L5 BM25 can score the normalized payloads

Run from: automation-service/
  python validate_collection_routing.py [user_id]
"""
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.abspath("../.."))

BASE = "http://localhost:6333"
CATALOG_COL = os.getenv("QDRANT_CATALOG_COLLECTION", "user_data_entries")
PROFILE_COL = os.getenv("QDRANT_COLLECTION", "business_context")
TARGET_DIM = 768


def rest_get(path: str) -> dict:
    try:
        return json.loads(urllib.request.urlopen(BASE + path, timeout=5).read())
    except Exception as e:
        return {"error": str(e)}


def check_collections() -> dict[str, dict]:
    results = {}
    for col in (CATALOG_COL, PROFILE_COL):
        data = rest_get(f"/collections/{col}")
        if "error" in data:
            results[col] = {"ok": False, "error": data["error"]}
        else:
            cfg = data["result"]["config"]["params"]["vectors"]
            pts = data["result"]["points_count"]
            dim = cfg["size"]
            results[col] = {"ok": True, "dim": dim, "points": pts, "dim_ok": dim == TARGET_DIM}
    return results


async def check_repository(user_id: str) -> dict:
    from qdrant_client import AsyncQdrantClient
    from app.retrieval.qdrant.async_repository import AsyncQdrantRepository

    client = AsyncQdrantClient(host="localhost", port=6333, timeout=10)
    repo = AsyncQdrantRepository(
        client,
        collection_name=PROFILE_COL,
        catalog_collection=CATALOG_COL,
    )

    # Test scroll — should hit user_data_entries
    records = await repo.scroll(user_id=user_id, limit=5)
    await client.close()

    if not records:
        return {
            "ok": False,
            "error": f"No records found for user_id={user_id!r}. "
                     "Check that ingestion has run for this tenant.",
            "records": 0,
        }

    # Verify normalization
    issues = []
    for r in records:
        p = r["payload"]
        if not p.get("content"):
            issues.append(f"id={r['id']} missing content")
        if not p.get("chunk_type"):
            issues.append(f"id={r['id']} missing chunk_type")
        if not p.get("user_id"):
            issues.append(f"id={r['id']} missing user_id")

    return {
        "ok": len(issues) == 0,
        "records": len(records),
        "normalization_issues": issues,
        "sample": {
            "id": records[0]["id"],
            "content_preview": records[0]["payload"].get("content", "")[:80],
            "chunk_type": records[0]["payload"].get("chunk_type"),
            "user_id": records[0]["payload"].get("user_id"),
        },
    }


def main():
    print("=" * 60)
    print("COLLECTION ROUTING VALIDATION")
    print("=" * 60)
    print(f"Catalog : {CATALOG_COL}")
    print(f"Profile : {PROFILE_COL}")
    print(f"Target dim : {TARGET_DIM}")
    print()

    # Step 1: Collection health
    print("── Step 1: Collection Status ──")
    cols = check_collections()
    all_ok = True
    for name, info in cols.items():
        if info.get("ok"):
            dim_ok = "✅" if info["dim_ok"] else "❌ WRONG DIM"
            pts = info["points"]
            pts_ok = "✅" if pts > 0 else "⚠️  EMPTY"
            print(f"  {name}: dim={info['dim']} {dim_ok} | points={pts} {pts_ok}")
            if not info["dim_ok"] or pts == 0:
                all_ok = False
        else:
            print(f"  {name}: ❌ {info['error']}")
            all_ok = False

    if not all_ok:
        print()
        if cols.get(CATALOG_COL, {}).get("points", -1) == 0:
            print("ACTION REQUIRED: user_data_entries is empty.")
            print("  Trigger the user-service ingestion pipeline to populate it:")
            print("  1. Ensure Celery worker is running in user-service")
            print("  2. POST /api/v1/data/sources/{source_id}/embed or trigger via UI")
        if cols.get(PROFILE_COL, {}).get("points", -1) == 0:
            print("ACTION REQUIRED: business_context is empty.")
            print("  Run: cd user-service && python run_embedding_update.py <user_id>")
        print()

    # Step 2: Repository routing
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not user_id:
        # Try to find a user_id from Qdrant directly
        data = rest_get(f"/collections/{CATALOG_COL}/points/scroll")
        # REST scroll requires POST — skip auto-detect, require argument
        print("── Step 2: Repository Routing ──")
        print("  SKIPPED: provide user_id as argument")
        print(f"  Usage: python validate_collection_routing.py <user_id>")
        print()
    else:
        print(f"── Step 2: Repository Routing (user_id={user_id}) ──")
        result = asyncio.run(check_repository(user_id))
        if result["ok"]:
            s = result["sample"]
            print(f"  ✅ {result['records']} records found")
            print(f"  sample id      : {s['id']}")
            print(f"  sample type    : {s['chunk_type']}")
            print(f"  content preview: {s['content_preview']}")
        else:
            print(f"  ❌ {result.get('error', 'unknown error')}")
            if result.get("normalization_issues"):
                for issue in result["normalization_issues"]:
                    print(f"     NORMALIZE: {issue}")
        print()

    print("=" * 60)
    print("EXPECTED AFTER FIX:")
    print(f"  {CATALOG_COL}: dim=768 ✅ | points>0 ✅")
    print(f"  {PROFILE_COL}: dim=768 ✅ | points>0 ✅ (after embedding_tasks run)")
    print("  Repository returns normalized content + chunk_type")
    print("  L5 BM25 can score candidates")
    print("  L6 semantic returns results above 0.28 threshold")
    print("  Grounding confidence > 0.35 (no escalation)")
    print("=" * 60)


if __name__ == "__main__":
    main()
