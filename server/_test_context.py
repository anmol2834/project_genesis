"""Verify scroll → rank → assemble pipeline with real Qdrant data."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services/automation-service"))
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from shared.vector_db import scroll_vectors
from shared.config import get_config
from ai_engine.context_builder.schema import ContextBlock, ContextSource
from ai_engine.context_builder.ranker import rank_blocks, build_recency_map

config = get_config()
user_id = "8d6b613a-6214-49d6-8fcb-7d2f69a93f28"

results = scroll_vectors(collection_name=config.QDRANT_COLLECTION, user_id=user_id, limit=10)
print(f"Scroll: {len(results)} results")

blocks = []
for r in results:
    payload = r.get("payload", {})
    b = ContextBlock(
        content=payload.get("content", ""),
        score=0.95,
        source=ContextSource.QDRANT,
        chunk_type=payload.get("type", "unknown"),
    )
    blocks.append(b)

print("\nBlocks before ranking:")
for b in blocks:
    print(f"  type={b.chunk_type:15s} score={b.score} content={b.content[:50]}")

recency_map = build_recency_map(blocks)
ranked = rank_blocks(blocks, recency_map)

print("\nBlocks after ranking:")
mandatory = {"instruction", "business_core", "tone", "use_case", "audience"}
for b in ranked:
    kept = b.chunk_type in mandatory or b.score >= 0.40
    print(f"  type={b.chunk_type:15s} score={b.score} kept={kept}")

knowledge_by_type = {b.chunk_type: b.content for b in ranked}
print("\nContext assembly result:")
print(f"  business_instruction: {bool(knowledge_by_type.get('instruction', ''))}")
print(f"  business_core:        {bool(knowledge_by_type.get('business_core', ''))}")
print(f"  tone:                 {bool(knowledge_by_type.get('tone', ''))}")
print(f"  use_case:             {bool(knowledge_by_type.get('use_case', ''))}")

all_present = all([
    knowledge_by_type.get("instruction"),
    knowledge_by_type.get("business_core"),
    knowledge_by_type.get("tone"),
    knowledge_by_type.get("use_case"),
])
print(f"\nResult: {'ALL MANDATORY CONTEXT PRESENT' if all_present else 'MISSING CONTEXT'}")
