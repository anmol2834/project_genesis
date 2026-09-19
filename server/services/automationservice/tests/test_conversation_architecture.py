"""
Unit & Integration Tests for Enterprise Multi-Tenant Conversational Architecture
================================================================================
Validates:
1. State machine & slot extraction (temporal, contact, action signals)
2. Conditional retrieval engine (skips on yes/thanks/booking, includes exclusions)
3. Exclusion filtering (presented and rejected entries never repeated)
4. Continuation requests ("show me more", "what else?")
5. Rejection handling ("not this", "too expensive")
6. Domain shifts (contact_support and delivery_shipping isolation)
7. Response planning & delta-only answers
8. Response deduplication & anti-repetition guard
9. Secret URL credential masking
10. Multi-tenant generic compliance (zero domain hardcoding)
"""
from __future__ import annotations

import os
import sys
import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR = os.path.dirname(_TESTS_DIR)
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))

for _p in (_SERVER_DIR, _SVC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.utils.security import mask_url_credentials
from services.conversation_state import (
    ConversationState,
    ConversationStage,
    BookingStatus,
    parse_conversation_state,
)
from pipeline.slot_tracker import (
    extract_signals_and_slots,
    update_conversation_state_with_signals,
)
from pipeline.retrieval_decision import RetrievalDecisionEngine
from pipeline.response_planner import ResponsePlanner
from pipeline.response_deduplicator import ResponseDeduplicator, compute_response_hash


# ─────────────────────────────────────────────────────────────────────────────
# 1. SECRET MASKING TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_mask_url_credentials():
    redis_url = "rediss://default:gQAAAAAABFiKAAIgcDI5MmFhMTg0YmQyNDk0MDRlYTI@us1-quick-bat-38291.upstash.io:6379"
    masked = mask_url_credentials(redis_url)
    assert "gQAAAAAABFiKAAIgcDI5MmFhMTg0YmQyNDk0MDRlYTI" not in masked
    assert "default:***@us1-quick-bat-38291.upstash.io" in masked

    postgres_url = "postgresql+asyncpg://neondb_owner:npg_x7yZ_secret@ep-cool-dawn-12345.ap-southeast-1.aws.neon.tech/neondb"
    masked_pg = mask_url_credentials(postgres_url)
    assert "npg_x7yZ_secret" not in masked_pg
    assert "neondb_owner:***@ep-cool-dawn-12345" in masked_pg

    # Non-credential URL remains intact
    plain_url = "http://localhost:6333"
    assert mask_url_credentials(plain_url) == "http://localhost:6333"


# ─────────────────────────────────────────────────────────────────────────────
# 2. SLOT EXTRACTION & STATE MACHINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_slot_extraction_temporal_and_affirmation():
    # Customer message specifying time and agreement
    text = "Yes, please schedule it for today after 3:30 PM."
    signals = extract_signals_and_slots(text)

    assert signals.is_confirmation is True
    assert signals.extracted_slots.get("preferred_date") == "today"
    assert "3:30" in signals.extracted_slots.get("preferred_time", "")

    state = ConversationState(conversation_id="conv_1", user_id="user_1")
    state.stage = ConversationStage.INFORMATION
    state.presented_entry_ids = ["entry_prod_101"]

    update_conversation_state_with_signals(state, signals, text)

    assert state.confirmed_slots["preferred_date"] == "today"
    assert state.is_slot_known("preferred_date") is True
    assert state.is_slot_known("preferred_time") is True
    assert state.booking_state.status == BookingStatus.CONFIRMED
    assert state.stage == ConversationStage.ACTION_CONFIRMED


def test_rejection_signal_and_exclusion_tracking():
    text = "No, that's too expensive, show me something else"
    signals = extract_signals_and_slots(text)

    assert signals.is_rejection is True

    state = ConversationState(conversation_id="conv_2", user_id="user_2")
    state.presented_entry_ids = ["entry_prod_expensive"]

    update_conversation_state_with_signals(state, signals, text)

    assert "entry_prod_expensive" in state.rejected_entry_ids


def test_gratitude_signal_and_closure():
    text = "Thank you very much, that's all I needed!"
    signals = extract_signals_and_slots(text)

    assert signals.is_gratitude is True

    state = ConversationState(conversation_id="conv_3", user_id="user_3")
    state.stage = ConversationStage.ACTION_CONFIRMED

    update_conversation_state_with_signals(state, signals, text)

    assert state.status == "closed"
    assert state.stage == ConversationStage.CLOSED


# ─────────────────────────────────────────────────────────────────────────────
# 3. CONDITIONAL RETRIEVAL DECISION ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieval_decision_skips_on_confirmation():
    state = ConversationState(
        conversation_id="conv_4",
        user_id="user_4",
        stage=ConversationStage.ACTION_IN_PROGRESS,
        presented_entry_ids=["item_1"],
        confirmed_slots={"preferred_date": "today", "preferred_time": "after 3:30 PM"},
    )
    signals = extract_signals_and_slots("Yes")

    decision = RetrievalDecisionEngine.evaluate(
        latest_message="Yes",
        state=state,
        signals=signals,
    )

    # Must NOT retrieve Qdrant on simple confirmation!
    assert decision.should_retrieve is False
    assert decision.reason == "booking_action_confirmation"


def test_retrieval_decision_skips_on_gratitude():
    state = ConversationState(
        conversation_id="conv_5",
        user_id="user_5",
        stage=ConversationStage.CLOSED,
    )
    signals = extract_signals_and_slots("Thank you!")

    decision = RetrievalDecisionEngine.evaluate(
        latest_message="Thank you!",
        state=state,
        signals=signals,
    )

    assert decision.should_retrieve is False
    assert decision.reason == "gratitude_closure"


def test_retrieval_decision_on_continuation():
    state = ConversationState(
        conversation_id="conv_6",
        user_id="user_6",
        stage=ConversationStage.INFORMATION,
        presented_entry_ids=["entry_a", "entry_b"],
        rejected_entry_ids=["entry_rejected"],
    )
    msg = "What other services do you have?"
    signals = extract_signals_and_slots(msg)

    decision = RetrievalDecisionEngine.evaluate(
        latest_message=msg,
        state=state,
        signals=signals,
    )

    assert decision.should_retrieve is True
    assert decision.is_continuation is True
    # Exclusions MUST contain all previously presented and rejected entries!
    assert "entry_a" in decision.exclude_entry_ids
    assert "entry_b" in decision.exclude_entry_ids
    assert "entry_rejected" in decision.exclude_entry_ids


def test_retrieval_decision_on_rejection():
    state = ConversationState(
        conversation_id="conv_7",
        user_id="user_7",
        stage=ConversationStage.INFORMATION,
        presented_entry_ids=["entry_x"],
        rejected_entry_ids=["entry_x"],
    )
    msg = "No, not this one. Do you have anything different?"
    signals = extract_signals_and_slots(msg)

    decision = RetrievalDecisionEngine.evaluate(
        latest_message=msg,
        state=state,
        signals=signals,
    )

    assert decision.should_retrieve is True
    assert decision.is_rejection is True
    assert "entry_x" in decision.exclude_entry_ids


def test_domain_isolation_contact_support():
    state = ConversationState(conversation_id="conv_8", user_id="user_8")
    msg = "Can you share your phone number and email address?"
    signals = extract_signals_and_slots(msg)

    decision = RetrievalDecisionEngine.evaluate(
        latest_message=msg,
        state=state,
        signals=signals,
        p1_intent={"category": "contact_support"},
    )

    assert decision.should_retrieve is True
    assert decision.target_domain == "contact_support"


def test_domain_isolation_delivery_shipping():
    state = ConversationState(conversation_id="conv_9", user_id="user_9")
    msg = "Do you deliver to my area and what is the shipping time?"
    signals = extract_signals_and_slots(msg)

    decision = RetrievalDecisionEngine.evaluate(
        latest_message=msg,
        state=state,
        signals=signals,
        p1_intent={"category": "delivery_shipping"},
    )

    assert decision.should_retrieve is True
    assert decision.target_domain == "delivery_shipping"


# ─────────────────────────────────────────────────────────────────────────────
# 4. RESPONSE PLANNER & DEDUPLICATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_response_planner_booking_confirmed_delta():
    state = ConversationState(
        conversation_id="conv_10",
        user_id="user_10",
        stage=ConversationStage.ACTION_CONFIRMED,
        confirmed_slots={"preferred_date": "today", "preferred_time": "after 3:30 PM"},
    )
    signals = extract_signals_and_slots("Yes")
    decision = RetrievalDecisionEngine.evaluate("Yes", state, signals)

    plan = ResponsePlanner.create_plan(
        state=state,
        signals=signals,
        decision=decision,
        latest_message="Yes",
    )

    assert plan.action_type == "booking_confirmed"
    assert plan.should_ask_question is False
    assert plan.should_close is True
    assert "Do NOT ask if the customer would like to proceed" in plan.answer_goal


def test_response_deduplicator_prevents_repetitive_pitch():
    # Simulates the bug shown in screenshot 2 & 3:
    # Previous assistant message pitched the full service and re-asked to proceed
    last_assistant_msg = (
        "Dear Customer, Thank you for your inquiry about scheduling our service. "
        "We offer standard service which includes full inspection and performance check. "
        "This service is priced at 699 and is currently available for booking. "
        "Please let us know if you would like to proceed with the booking for today after 3:30 PM, "
        "and we will do our best to accommodate your request."
    )

    messages = [
        {"direction": "inbound", "content": "I want to schedule for today after 3:30 PM"},
        {"direction": "outgoing", "content": last_assistant_msg},
        {"direction": "inbound", "content": "Yes"},
    ]

    state = ConversationState(
        conversation_id="conv_11",
        user_id="user_11",
        stage=ConversationStage.ACTION_CONFIRMED,
        confirmed_slots={"preferred_date": "today", "preferred_time": "after 3:30 PM"},
    )
    signals = extract_signals_and_slots("Yes")
    decision = RetrievalDecisionEngine.evaluate("Yes", state, signals)
    plan = ResponsePlanner.create_plan(state, signals, decision, "Yes")

    # Suppose LLM Call #2 naively regenerated almost the exact same repetitive pitch:
    naive_proposed_body = (
        "Dear Customer, Thank you for confirming your request for our service. "
        "We are pleased to schedule the service for today after 3:30 PM. "
        "This service includes full inspection and performance check and is priced at 699. "
        "Please let us know if you would like to proceed with the booking for today after 3:30 PM."
    )

    deduped_body = ResponseDeduplicator.inspect_and_deduplicate(
        proposed_body=naive_proposed_body,
        messages=messages,
        state=state,
        plan=plan,
        signals=signals,
        business_name="Acme Solutions",
    )

    # Assert that the repetitive pitch and question were eliminated!
    assert "Please let us know if you would like to proceed" not in deduped_body
    assert "is priced at 699" not in deduped_body
    assert "scheduled for today after 3:30 PM" in deduped_body
    assert "Thank you for confirming" in deduped_body


# ─────────────────────────────────────────────────────────────────────────────
# 5. MULTI-TENANT GENERIC DOMAIN INDEPENDENCE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("domain_msg,domain_cat", [
    ("How much does the legal consultation contract review cost?", "product_service"),
    ("What are the pricing tiers for the cloud infrastructure API subscription?", "product_service"),
    ("Can I book a health screening appointment for tomorrow morning?", "product_service"),
    ("Do you offer express freight shipping for industrial equipment?", "delivery_shipping"),
    ("What is your enterprise emergency support hotline?", "contact_support"),
])
def test_domain_agnostic_evaluation(domain_msg: str, domain_cat: str):
    signals = extract_signals_and_slots(domain_msg)
    state = ConversationState(conversation_id="conv_generic", user_id="user_generic")
    decision = RetrievalDecisionEngine.evaluate(
        latest_message=domain_msg,
        state=state,
        signals=signals,
        p1_intent={"category": domain_cat},
    )

    assert decision.should_retrieve is True
    assert decision.target_domain == domain_cat


# ─────────────────────────────────────────────────────────────────────────────
# 6. END-TO-END MULTI-TURN CONVERSATION SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

def test_multi_turn_conversation_lifecycle():
    """
    Simulates the exact 6-turn lifecycle requested in Section 39 & Section 45:
    Turn 1: Initial service inquiry -> RAG runs, records presented entry.
    Turn 2: Slot provision & confirmation ("Yes, today after 3:30 PM") -> RAG skipped, booking confirmed.
    Turn 3: Gratitude ("Thank you!") -> RAG skipped, closed.
    Turn 4: Reopening inquiry ("What other services do you offer?") -> Reopened, RAG runs with exclusions.
    Turn 5: Customer rejection ("No, not that, something else") -> Rejection added, alternatives excluded.
    Turn 6: Topic shift to contact ("How can I contact support?") -> Routes to contact_support domain only.
    """
    # ── TURN 1: Initial service inquiry ───────────────────────────────────────
    conv = ConversationState(conversation_id="conv_lifecycle", user_id="tenant_alpha")
    t1_msg = "Can you tell me about your primary inspection service?"
    t1_sig = extract_signals_and_slots(t1_msg)
    update_conversation_state_with_signals(conv, t1_sig, t1_msg)

    t1_dec = RetrievalDecisionEngine.evaluate(t1_msg, conv, t1_sig, p1_intent={"category": "product_service"})
    assert t1_dec.should_retrieve is True
    assert t1_dec.target_domain == "product_service"

    t1_plan = ResponsePlanner.create_plan(conv, t1_sig, t1_dec, t1_msg)
    assert t1_plan.action_type == "answer"
    assert t1_plan.should_ask_question is True

    # Assistant presents service entry "srv_entry_101"
    conv.mark_presented(["srv_entry_101"])
    conv.stage = ConversationStage.INFORMATION

    # ── TURN 2: Slot provision & confirmation ("Yes, today after 3:30 PM") ─────
    t2_msg = "Yes, please schedule it for today after 3:30 PM."
    t2_sig = extract_signals_and_slots(t2_msg)
    update_conversation_state_with_signals(conv, t2_sig, t2_msg)

    assert conv.is_slot_known("preferred_date") is True
    assert conv.is_slot_known("preferred_time") is True
    assert conv.stage == ConversationStage.ACTION_CONFIRMED
    assert conv.booking_state.status == BookingStatus.CONFIRMED

    t2_dec = RetrievalDecisionEngine.evaluate(t2_msg, conv, t2_sig)
    # RAG must be SKIPPED!
    assert t2_dec.should_retrieve is False
    assert t2_dec.reason == "booking_action_confirmation"

    t2_plan = ResponsePlanner.create_plan(conv, t2_sig, t2_dec, t2_msg)
    assert t2_plan.action_type == "booking_confirmed"
    assert t2_plan.should_ask_question is False
    assert t2_plan.should_close is True
    assert "Do NOT ask if the customer would like to proceed" in t2_plan.answer_goal

    # ── TURN 3: Gratitude & Closure ("Thank you!") ────────────────────────────
    t3_msg = "Thank you very much, that's perfect!"
    t3_sig = extract_signals_and_slots(t3_msg)
    update_conversation_state_with_signals(conv, t3_sig, t3_msg)

    assert conv.status == "closed"
    assert conv.stage == ConversationStage.CLOSED

    t3_dec = RetrievalDecisionEngine.evaluate(t3_msg, conv, t3_sig)
    assert t3_dec.should_retrieve is False
    assert t3_dec.reason == "gratitude_closure"

    t3_plan = ResponsePlanner.create_plan(conv, t3_sig, t3_dec, t3_msg)
    assert t3_plan.action_type == "closure"
    assert t3_plan.should_ask_question is False

    # ── TURN 4: Reopening inquiry ("What other services do you offer?") ────────
    t4_msg = "What other services do you offer?"
    t4_sig = extract_signals_and_slots(t4_msg)
    update_conversation_state_with_signals(conv, t4_sig, t4_msg)

    assert conv.status == "reopened"
    assert conv.stage == ConversationStage.REOPENED

    t4_dec = RetrievalDecisionEngine.evaluate(t4_msg, conv, t4_sig)
    assert t4_dec.should_retrieve is True
    assert t4_dec.is_continuation is True
    # Initial service srv_entry_101 MUST be excluded!
    assert "srv_entry_101" in t4_dec.exclude_entry_ids

    # Assistant presents new service "srv_entry_202"
    conv.mark_presented(["srv_entry_202"])
    conv.stage = ConversationStage.INFORMATION

    # ── TURN 5: Rejection ("No, not that, something different") ───────────────
    t5_msg = "No, not that, do you have something different?"
    t5_sig = extract_signals_and_slots(t5_msg)
    update_conversation_state_with_signals(conv, t5_sig, t5_msg)

    assert "srv_entry_202" in conv.rejected_entry_ids

    t5_dec = RetrievalDecisionEngine.evaluate(t5_msg, conv, t5_sig)
    assert t5_dec.should_retrieve is True
    assert t5_dec.is_rejection is True
    # BOTH the original service and the rejected service MUST be in exclusions!
    assert "srv_entry_101" in t5_dec.exclude_entry_ids
    assert "srv_entry_202" in t5_dec.exclude_entry_ids

    # ── TURN 6: Topic shift to contact ("How can I contact support?") ──────────
    t6_msg = "By the way, how can I contact your customer support team?"
    t6_sig = extract_signals_and_slots(t6_msg)
    update_conversation_state_with_signals(conv, t6_sig, t6_msg)

    t6_dec = RetrievalDecisionEngine.evaluate(t6_msg, conv, t6_sig)
    assert t6_dec.should_retrieve is True
    assert t6_dec.target_domain == "contact_support"
    assert t6_dec.target_domain != "product_service"

