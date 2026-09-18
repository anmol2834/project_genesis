import asyncio
import os
import sys

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_TESTS_DIR)
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from llm.processor_2 import run_processor_2

async def test():
    messages = [
        {"sender_type": "Customer", "content": "Hi there, I'm looking for a new gaming laptop."},
        {"sender_type": "Support", "content": "Hello! We would be happy to help. Do you have any specific specs or budget in mind?"},
    ]
    latest_message = {
        "content": "Yes, I need at least 16GB of RAM and 512GB SSD storage, preferably with an RTX card, under $1200. Do you have anything that fits?",
        "direction": "inbound"
    }
    conversation_meta = {
        "subject": "Gaming laptop inquiry",
        "thread_id": "thread_abc123"
    }
    business_context = {
        "_loaded": True,
        "business_name": "IngenAI Hardware & Solutions",
        "business_type": "E-commerce & Computer Hardware",
        "communication_tone": "professional and friendly",
        "industry": ["Technology", "Electronics"],
        "business_description": "We build and sell premium high-performance laptops, custom workstations, and gaming rigs."
    }
    p1_output = {
        "conversation_analysis": {
            "customer_goal": "Find a gaming laptop with 16GB RAM, 512GB SSD under $1200",
            "standalone_query": "gaming laptop 16GB RAM 512GB SSD RTX under 1200",
            "customer_sentiment": "positive",
        },
        "intent_analysis": {
            "primary_intent": {"category": "product_service"}
        },
        "routing_decision": {
            "escalation_requested": False
        }
    }
    retrieved_chunks = [
        {
            "entry_id": "laptop_2",
            "title": "IngenAI Gaming Pro 15",
            "category": "product_service",
            "subtype": "hardware",
            "rerank_score": 0.9926,
            "payload": {
                "title": "IngenAI Gaming Pro 15",
                "category": "product_service",
                "structured_data": {"price": 1099, "ram": "16GB DDR5", "storage": "512GB NVMe SSD", "gpu": "NVIDIA RTX 4060", "warranty": "2 years"},
                "search_text": "IngenAI Gaming Pro 15 features an Intel Core i7, 16GB DDR5 RAM, 512GB NVMe SSD, and NVIDIA RTX 4060 8GB GPU for $1,099. Includes 2-year warranty."
            }
        }
    ]

    print("Executing Processor #2...")
    result = await run_processor_2(
        messages=messages,
        latest_message=latest_message,
        conversation_meta=conversation_meta,
        business_context=business_context,
        p1_output=p1_output,
        retrieved_chunks=retrieved_chunks,
    )

    print("\n--- PROCESSOR #2 RESULT ---")
    print("Answerable :", result.get("answerable"))
    print("Action     :", result.get("action"))
    print("Confidence :", result.get("confidence"))
    print("Send Email :", result.get("send_email"))
    print("Subject    :", result.get("email_subject"))
    print("\n--- EMAIL BODY ---\n")
    print(result.get("email_body"))

    assert result.get("answerable") is True, "Expected answerable to be True"
    assert "IngenAI Gaming Pro 15" in result.get("email_body"), "Expected laptop model in email body"
    assert "1099" in result.get("email_body") or "$1,099" in result.get("email_body"), "Expected price in email body"
    print("\nPROCESSOR #2 TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test())
