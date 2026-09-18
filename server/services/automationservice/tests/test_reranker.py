import asyncio
import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_TESTS_DIR)
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.reranker import rerank_candidates, format_retrieved_context_block

async def test():
    query = "Do you have any gaming laptops with 16GB RAM and 512GB SSD under $1200?"
    candidates = [
        {
            "entry_id": "laptop_1",
            "title": "Office Laptop 14",
            "category": "product_service",
            "subtype": "hardware",
            "score": 0.85,
            "payload": {
                "title": "Office Laptop 14",
                "category": "product_service",
                "structured_data": {"price": 799, "ram": "8GB", "storage": "256GB SSD"},
                "search_text": "Affordable office laptop with 8GB RAM and 256GB SSD storage for everyday productivity."
            }
        },
        {
            "entry_id": "laptop_2",
            "title": "IngenAI Gaming Pro 15",
            "category": "product_service",
            "subtype": "hardware",
            "score": 0.89,
            "payload": {
                "title": "IngenAI Gaming Pro 15",
                "category": "product_service",
                "structured_data": {"price": 1099, "ram": "16GB", "storage": "512GB SSD", "gpu": "RTX 4060"},
                "search_text": "High performance gaming laptop with 16GB RAM, 512GB NVMe SSD, and RTX 4060 graphics."
            }
        },
        {
            "entry_id": "policy_1",
            "title": "Return Policy 30 Days",
            "category": "policies_legal",
            "subtype": "terms",
            "score": 0.60,
            "payload": {
                "title": "Return Policy 30 Days",
                "category": "policies_legal",
                "structured_data": {"return_window": "30 days", "condition": "Original packaging"},
                "search_text": "Customers may return laptops within 30 days of delivery in original condition."
            }
        }
    ]

    print("Running rerank_candidates...")
    reranked = await rerank_candidates(query, candidates, top_k=3)
    for idx, r in enumerate(reranked, 1):
        print(f"Rank {idx}: {r['title']} | Rerank Score: {r.get('rerank_score')} | Base Score: {r.get('score')}")
    
    assert reranked[0]["entry_id"] == "laptop_2", f"Expected laptop_2 to be top rank, got {reranked[0]['entry_id']}"
    
    context_block = format_retrieved_context_block(reranked)
    print("\nFormatted Context Block Preview:")
    print(context_block[:300] + "...")
    print("\nRERANKER TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test())
