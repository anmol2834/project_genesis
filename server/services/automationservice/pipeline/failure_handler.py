"""
automationservice — Failure States Engine (Phase 19)
===================================================
Defines explicit, deterministic behavior for all system failure states.

Architectural Guarantees:
  - NEVER convert a system failure into a fabricated customer answer.
  - Deterministically maps failure conditions to authorized actions:
      clarify | partial_result | escalate | temporary_failure
  - Prevents hallucination when data, pricing, availability, or models fail.
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict

from pipeline.contracts import ResponseMode

logger = logging.getLogger("automationservice.pipeline.failure_handler")

FailureState = Literal[
    "NO_RETRIEVAL_RESULTS",
    "NO_RELEVANT_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "MISSING_PRICE",
    "MISSING_AVAILABILITY",
    "MISSING_CUSTOMER_REQUIREMENT",
    "INVALID_STRATEGY",
    "LLM_TIMEOUT",
    "LLM_MALFORMED_OUTPUT",
    "GROUNDING_FAILURE",
    "POLICY_FAILURE",
    "EMAIL_RENDERING_FAILURE",
    "EMAIL_PROVIDER_FAILURE",
]


class FailureResolution(BaseModel):
    """
    Deterministic operational resolution for a specific failure state.
    """
    failure_state: FailureState
    target_mode: ResponseMode
    action: Literal["reply", "draft", "escalate"]
    send_email: bool
    requires_human_review: bool
    fallback_subject: str
    fallback_body: str
    explanation: str

    model_config = ConfigDict(extra="ignore")


def resolve_failure_state(
    failure_state: FailureState,
    business_name: str = "Our Support Team",
    inquiry_subject: str = "your inquiry",
    custom_details: str | None = None,
) -> FailureResolution:
    """
    Deterministically resolve a pipeline failure into an authorized operational action
    without ever inventing business facts.
    """
    re_subject = inquiry_subject if inquiry_subject.lower().startswith("re:") else f"Re: {inquiry_subject}"

    # ── 1. No Retrieval Results ───────────────────────────────────────────────
    if failure_state == "NO_RETRIEVAL_RESULTS":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="no_match",
            action="reply",
            send_email=True,
            requires_human_review=False,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}.\n\n"
                "We could not locate any matching items or services in our current catalog for your inquiry. "
                "Please let us know if you would like information on our standard product lineup.\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="No candidate chunks retrieved from vector index; replied with polite catalog boundary notice.",
        )

    # ── 2. No Relevant Evidence ───────────────────────────────────────────────
    if failure_state == "NO_RELEVANT_EVIDENCE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="no_match",
            action="reply",
            send_email=True,
            requires_human_review=False,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for reaching out to {business_name}.\n\n"
                "We currently do not have verified information matching your specific inquiry. "
                "Feel free to reply with additional details or questions about our available offerings.\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Retrieved chunks fell below similarity threshold; replied with boundary notice.",
        )

    # ── 3. Conflicting Evidence ───────────────────────────────────────────────
    if failure_state == "CONFLICTING_EVIDENCE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="escalate",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}.\n\n"
                "We are currently reviewing your inquiry with our product specialists to verify current details. "
                "A representative will get back to you shortly.\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Unresolved contradictory facts detected; escalated for manual reconciliation.",
        )

    # ── 4. Missing Price ──────────────────────────────────────────────────────
    if failure_state == "MISSING_PRICE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="partial_result",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}.\n\n"
                "We have located the requested specifications; however, pricing is currently undergoing seasonal verification. "
                "Our sales team will follow up with an official quotation.\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Price was requested but not available in verified facts; pricing withheld and saved as draft.",
        )

    # ── 5. Missing Availability ───────────────────────────────────────────────
    if failure_state == "MISSING_AVAILABILITY":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="clarify",
            action="reply",
            send_email=True,
            requires_human_review=False,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}.\n\n"
                "Current warehouse availability for this configuration is pending confirmation. "
                "Could you please share your expected timeline or order quantity so we can check allocation?\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Stock availability unverified; clarification requested without false promises.",
        )

    # ── 6. Missing Customer Requirement ───────────────────────────────────────
    if failure_state == "MISSING_CUSTOMER_REQUIREMENT":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="clarify",
            action="reply",
            send_email=True,
            requires_human_review=False,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for reaching out to {business_name}.\n\n"
                "To help us recommend the best option for your needs, could you please clarify your preferred budget and primary use case?\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Customer inquiry lacked essential requirements; requested clarification.",
        )

    # ── 7. Invalid Strategy ───────────────────────────────────────────────────
    if failure_state == "INVALID_STRATEGY":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="escalate",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}. Your inquiry has been routed to our support team for review."
            ),
            explanation="Response strategy failed or returned invalid configuration; escalated.",
        )

    # ── 8. LLM Timeout ────────────────────────────────────────────────────────
    if failure_state == "LLM_TIMEOUT":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}.\n\n"
                "We received your message and are processing your request. A team member will assist you shortly.\n\n"
                f"Best regards,\n{business_name}"
            ),
            explanation="Generation model timed out; saved safe draft and flagged for review.",
        )

    # ── 9. LLM Malformed Output ───────────────────────────────────────────────
    if failure_state == "LLM_MALFORMED_OUTPUT":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for reaching out to {business_name}. Your message is being reviewed by our team."
            ),
            explanation="Model generated malformed JSON or failed schema criteria; flagged for human review.",
        )

    # ── 10. Grounding Failure ─────────────────────────────────────────────────
    if failure_state == "GROUNDING_FAILURE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for reaching out to {business_name}. We are reviewing your inquiry with our specialists."
            ),
            explanation="Grounding validation detected hallucinations or unverified assertions; auto-send blocked.",
        )

    # ── 11. Policy Failure ────────────────────────────────────────────────────
    if failure_state == "POLICY_FAILURE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="escalate",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for reaching out to {business_name}. Your request is being reviewed under our standard commercial terms."
            ),
            explanation="Response policy violation detected; auto-send blocked.",
        )

    # ── 12. Email Rendering Failure ───────────────────────────────────────────
    if failure_state == "EMAIL_RENDERING_FAILURE":
        return FailureResolution(
            failure_state=failure_state,
            target_mode="partial_result",
            action="draft",
            send_email=False,
            requires_human_review=True,
            fallback_subject=re_subject,
            fallback_body=(
                f"Thank you for contacting {business_name}. We are preparing your response."
            ),
            explanation="Email renderer encountered an error or semantic drift; preserved as draft.",
        )

    # ── 13. Email Provider Failure ────────────────────────────────────────────
    return FailureResolution(
        failure_state=failure_state,
        target_mode="escalate",
        action="draft",
        send_email=False,
        requires_human_review=True,
        fallback_subject=re_subject,
        fallback_body=(
            f"Thank you for contacting {business_name}. Outbound delivery experienced a provider error."
        ),
        explanation="Email sender provider failure occurred; status recorded safely without corrupting conversation state.",
    )
