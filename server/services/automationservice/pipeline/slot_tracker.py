"""
automationservice — Generic Conversational Slot & Action Signal Tracker
======================================================================
Extracts generic, domain-agnostic conversation slots (temporal, contact, action signals)
from inbound customer messages and updates ConversationState.

Design Principle:
- 100% domain-agnostic: operates purely on semantic temporal patterns, contact structures,
  affirmations, rejections, continuations, and gratitude.
- NEVER hard-codes business-specific products or services.
"""
from __future__ import annotations

import re
import logging
from typing import Any
from pydantic import BaseModel
from services.conversation_state import ConversationState, ConversationStage, BookingStatus

logger = logging.getLogger("automationservice.slot_tracker")

# Regular expressions for generic temporal slot extraction
_TIME_PATTERNS = [
    # "after 3:30 PM", "before 5 pm", "at 4:00 PM", "around 2 PM"
    re.compile(r"\b(?:after|before|at|around|by|from)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))\b", re.IGNORECASE),
    # "between 2 and 4 pm", "from 2 to 4 PM"
    re.compile(r"\b(?:between|from)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:and|to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", re.IGNORECASE),
    # "in the morning", "afternoon", "evening", "night"
    re.compile(r"\b(morning|afternoon|evening|tonight)\b", re.IGNORECASE),
]

_DATE_PATTERNS = [
    # "today", "tomorrow", "tonight", "this weekend"
    re.compile(r"\b(today|tomorrow|this weekend|next week|this evening)\b", re.IGNORECASE),
    # Day names: "this monday", "next friday", "on wednesday"
    re.compile(r"\b(?:this|next|on)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    # Specific date: "20th sept", "september 25th", "15-10-2026", "2026-09-20"
    re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\b", re.IGNORECASE),
    re.compile(r"\b((?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?)\b", re.IGNORECASE),
]

# Action and conversational signals
_CONFIRMATION_EXACT = {
    "yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "confirmed",
    "please proceed", "go ahead", "book it", "schedule it", "do it",
    "sounds good", "that works", "perfect", "done", "that's fine",
    "yes please", "yes schedule it", "yes book it", "yes proceed", "yes confirm",
}

_REJECTION_PATTERNS = [
    re.compile(r"\b(not\s+this|too\s+expensive|too\s+costly|something\s+else|something\s+different|another\s+option|different\s+one|don't\s+want\s+this|not\s+interested)\b", re.IGNORECASE),
    re.compile(r"^\s*no\b", re.IGNORECASE),
]

_CONTINUATION_PATTERNS = [
    re.compile(r"\b(what\s+else|anything\s+else|show\s+me\s+more|other\s+options|other\s+services|other\s+products|more\s+options|more\s+services|more\s+products|what\s+other|any\s+other)\b", re.IGNORECASE),
]

_GRATITUDE_PATTERNS = [
    re.compile(r"\b(thank\s+you|thanks|thank\s+u|thx|much\s+appreciated|great\s+thanks|see\s+you)\b", re.IGNORECASE),
]

_CONTACT_DOMAIN_PATTERNS = [
    re.compile(r"\b(contact|phone|call|email|reach|speak|talk|customer\s+care|support\s+team|office\s+address|location)\b", re.IGNORECASE),
]

_DELIVERY_DOMAIN_PATTERNS = [
    re.compile(r"\b(deliver|delivery|shipping|ship|dispatch|courier|serviceable|service\s+area|service\s+radius)\b", re.IGNORECASE),
]


class ExtractedSignals(BaseModel):
    is_confirmation: bool = False
    is_rejection: bool = False
    is_continuation: bool = False
    is_gratitude: bool = False
    is_contact_inquiry: bool = False
    is_delivery_inquiry: bool = False
    extracted_slots: dict[str, Any] = {}


def extract_signals_and_slots(text: str) -> ExtractedSignals:
    """Extract semantic action signals and generic slots from a customer message."""
    raw = (text or "").strip()
    lower = raw.lower()
    clean = re.sub(r"[^\w\s]", " ", lower)
    tokens = clean.split()
    normalized_phrase = " ".join(tokens)

    signals = ExtractedSignals()

    # 1. Exact or prefix confirmation check
    if normalized_phrase in _CONFIRMATION_EXACT:
        signals.is_confirmation = True
    elif any(normalized_phrase.startswith(p) for p in ("yes ", "yeah ", "sure ", "ok ", "okay ")):
        signals.is_confirmation = True

    # 2. Rejection check
    for pat in _REJECTION_PATTERNS:
        if pat.search(raw):
            signals.is_rejection = True
            break

    # 3. Continuation check
    for pat in _CONTINUATION_PATTERNS:
        if pat.search(raw):
            signals.is_continuation = True
            break

    # 4. Gratitude check
    for pat in _GRATITUDE_PATTERNS:
        if pat.search(raw):
            signals.is_gratitude = True
            break

    # 5. Domain shifts
    for pat in _CONTACT_DOMAIN_PATTERNS:
        if pat.search(raw):
            signals.is_contact_inquiry = True
            break

    for pat in _DELIVERY_DOMAIN_PATTERNS:
        if pat.search(raw):
            signals.is_delivery_inquiry = True
            break

    # 6. Temporal slot extraction
    extracted = {}

    # Extract date
    for pat in _DATE_PATTERNS:
        m = pat.search(raw)
        if m:
            extracted["preferred_date"] = m.group(1).strip()
            break

    # Extract time
    for pat in _TIME_PATTERNS:
        m = pat.search(raw)
        if m:
            if m.lastindex and m.lastindex >= 2:
                extracted["preferred_time"] = f"{m.group(1)} to {m.group(2)}".strip()
            else:
                # Include context prefix like "after 3:30 PM"
                full_span = m.group(0).strip()
                extracted["preferred_time"] = full_span
            break

    signals.extracted_slots = extracted
    return signals


def update_conversation_state_with_signals(
    state: ConversationState,
    signals: ExtractedSignals,
    customer_message: str,
) -> None:
    """
    Updates the ConversationState in place based on extracted slots and action signals.
    """
    # 1. Merge extracted slots into state
    for slot_k, slot_v in signals.extracted_slots.items():
        state.confirmed_slots[slot_k] = slot_v
        state.booking_state.confirmed_slots[slot_k] = slot_v
        logger.info("[SLOT_TRACKER] Confirmed slot: %s = '%s'", slot_k, slot_v)

    # 2. If rejection detected, mark current candidate entries as rejected
    if signals.is_rejection:
        # Move recently presented entries into rejected_entry_ids
        if state.presented_entry_ids:
            latest_id = state.presented_entry_ids[-1]
            if latest_id not in state.rejected_entry_ids:
                state.rejected_entry_ids.append(latest_id)
                logger.info("[SLOT_TRACKER] Marked entry as rejected: %s", latest_id)

    # 3. Check booking / scheduling flow transitions
    has_date = state.is_slot_known("preferred_date")
    has_time = state.is_slot_known("preferred_time")

    if signals.is_confirmation:
        if has_date or has_time or state.stage in (
            ConversationStage.ACTION_REQUESTED,
            ConversationStage.ACTION_IN_PROGRESS,
            ConversationStage.SELECTION,
            ConversationStage.INFORMATION,
        ):
            # Customer says "Yes" / confirms
            state.booking_state.status = BookingStatus.CONFIRMED
            state.transition_to(ConversationStage.ACTION_CONFIRMED, reason="customer_confirmed_action")

    elif has_date or has_time:
        # Customer supplied booking details (e.g. "today after 3:30 PM")
        if state.booking_state.status != BookingStatus.CONFIRMED:
            state.booking_state.status = BookingStatus.IN_PROGRESS
            state.transition_to(ConversationStage.ACTION_IN_PROGRESS, reason="customer_provided_schedule_slots")

    was_already_closed = (state.status == "closed")

    # 4. Gratitude / Closure transition
    if signals.is_gratitude and not signals.is_continuation and not signals.is_contact_inquiry:
        # Only close if no active action is pending
        if state.stage in (ConversationStage.ACTION_CONFIRMED, ConversationStage.COMPLETED, ConversationStage.INFORMATION):
            state.close(reason="customer_gratitude_closure")

    # 5. Reopening if customer sends a new inquiry while already closed
    if was_already_closed and not signals.is_gratitude:
        if signals.is_continuation or signals.is_contact_inquiry or signals.is_delivery_inquiry or len(customer_message.split()) > 3:
            state.reopen(reason="new_inquiry_on_closed_conversation")
