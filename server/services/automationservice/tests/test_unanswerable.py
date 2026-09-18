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
    messages = []
    latest_message = {
        "content": "Do you sell medical MRI machines or diagnostic imaging equipment?",
        "direction": "inbound"
    }
    conversation_meta = {
        "subject": "MRI Machine catalog inquiry",
        "thread_id": "thread_med1"
    }
    business_context = {
        "_loaded": True,
        "business_name": "IngenAI Hardware & Solutions",
        "business_type": "E-commerce & Computer Hardware",
        "communication_tone": "professional",
        "industry": ["Technology", "Electronics"],
        "business_description": "We build and sell premium high-performance laptops and computer workstations."
    }
    p1_output = {
        "conversation_analysis": {
            "customer_goal": "Inquire about medical MRI machines",
            "standalone_query": "medical MRI machines diagnostic imaging equipment",
            "customer_sentiment": "neutral",
        },
        "intent_analysis": {
            "primary_intent": {"category": "product_service"}
        },
        "routing_decision": {
            "escalation_requested": False
        }
    }
    retrieved_chunks = []

    print("Executing Processor #2 on unanswerable query...")
    result = await run_processor_2(
        messages=messages,
        latest_message=latest_message,
        conversation_meta=conversation_meta,
        business_context=business_context,
        p1_output=p1_output,
        retrieved_chunks=retrieved_chunks,
    )

    print("\n--- PROCESSOR #2 UNANSWERABLE RESULT ---")
    print("Answerable :", result.get("answerable"))
    print("Action     :", result.get("action"))
    print("Confidence :", result.get("confidence"))
    print("Send Email :", result.get("send_email"))
    print("Missing    :", result.get("missing_information"))
    print("\n--- EMAIL BODY ---\n")
    print(result.get("email_body"))

    assert result.get("answerable") is False, "Expected answerable to be False"
    print("\nUNANSWERABLE TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test())
