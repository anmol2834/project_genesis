"""
Qdrant collection migration via raw HTTP REST API.
Bypasses qdrant-client get_collection parsing bug with newer Qdrant server.
"""
import sys, os, json, urllib.request, urllib.error

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from shared.config import get_config

cfg = get_config()
BASE = cfg.QDRANT_URL.rstrip("/")
COLLECTION = cfg.QDRANT_COLLECTION
TARGET_DIM = cfg.QDRANT_VECTOR_SIZE  # 768


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())


def delete(path):
    req = urllib.request.Request(f"{BASE}{path}", method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def put(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


print("=" * 60)
print("QDRANT COLLECTION MIGRATION (REST)")
print("=" * 60)
print(f"URL        : {BASE}")
print(f"Collection : {COLLECTION}")
print(f"Target dim : {TARGET_DIM}")

# List collections
cols = get("/collections")
names = [c["name"] for c in cols["result"]["collections"]]
print(f"\nCollections: {names}")

# Check current dim
if COLLECTION in names:
    info = get(f"/collections/{COLLECTION}")
    current_dim = info["result"]["config"]["params"]["vectors"]["size"]
    points = info["result"]["points_count"]
    print(f"Current dim : {current_dim}")
    print(f"Points      : {points}")

    if current_dim == TARGET_DIM:
        print(f"\n[OK] Already at {TARGET_DIM}-dim.")
        if points == 0:
            print("WARNING: 0 points — data must be re-ingested via user-service.")
        sys.exit(0)

    print(f"\n[MISMATCH] {current_dim}-dim != {TARGET_DIM}-dim")
    if points:
        print(f"  {points} vectors will be deleted. Re-ingest via user-service after.")
    confirm = input("Recreate at 768-dim? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(1)

    result = delete(f"/collections/{COLLECTION}")
    print(f"Deleted: {result}")
else:
    print(f"Collection not found — creating.")

# Create at 768-dim
result = put(f"/collections/{COLLECTION}", {
    "vectors": {"size": TARGET_DIM, "distance": "Cosine"}
})
print(f"Create result: {result}")

# Verify
info = get(f"/collections/{COLLECTION}")
actual = info["result"]["config"]["params"]["vectors"]["size"]
assert actual == TARGET_DIM, f"Verification FAILED: {actual}"
points = info["result"]["points_count"]
print(f"\n[VERIFIED] '{COLLECTION}': {actual}-dim, Cosine, {points} points")

print("\n" + "=" * 60)
print("DONE. Required next steps:")
print("  1. Re-ingest data: user-service Celery embed tasks must run")
print("     (run the knowledge ingestion job or trigger via user-service API)")
print("  2. Restart automation-service")
print("  3. python validate_rc_all.py")
print("=" * 60)
