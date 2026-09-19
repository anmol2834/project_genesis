"""
automationservice — Email Sender & Authorization Gate (Phase 15)
================================================================
Completely decoupled email dispatch layer enforcing strict authorization gates.

Architectural Guarantees:
  - OpenAI #2 NEVER calls email providers directly.
  - The sender accepts ONLY a policy-approved RenderedEmailPayload with valid SendAuthorization.
  - The sender MUST REFUSE to send unless:
      1. approval_status == 'approved'
      2. structure validation passed
      3. grounding validation passed (zero hallucinations, zero contradictions)
      4. policy engine approved sending
      5. cryptographic HMAC authorization token is valid
  - Architecture:
      OpenAI #2
          ↓
      Structure Validator
          ↓
      Grounding Validator
          ↓
      Policy Engine
          ↓
      Email Renderer
          ↓
      Send Authorization
          ↓
      Email Sender
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from uuid import uuid4

from pipeline.contracts import (
    RenderedEmailPayload,
    SendAuthorization,
    SendResult,
    GroundingReport,
    PolicyReport,
)

logger = logging.getLogger("automationservice.pipeline.email_sender")

# Secret key for HMAC token generation (in production loaded from environment)
_AUTH_SECRET_KEY = "genesis_grounded_pipeline_auth_secret"


class SendAuthorizationError(Exception):
    """Raised when an unauthorized or unapproved email payload attempts dispatch."""
    pass


def issue_send_authorization(
    recipient: str,
    subject: str,
    text_body: str,
    grounding_report: GroundingReport,
    policy_report: PolicyReport,
    structure_valid: bool = True,
    secret_key: str = _AUTH_SECRET_KEY,
) -> SendAuthorization:
    """
    Issue a cryptographically signed authorization token for outbound email.

    Status is 'approved' ONLY if:
      - structure_valid is True
      - grounding_report.is_grounded is True
      - policy_report.approved_for_sending is True
    """
    is_approved = (
        structure_valid
        and grounding_report.is_grounded
        and policy_report.approved_for_sending
    )

    status = "approved" if is_approved else (
        "escalated" if policy_report.action == "escalate" else "draft_only"
    )

    timestamp = datetime.now(timezone.utc).isoformat()
    body_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()

    # Generate HMAC-SHA256 signature binding message elements and approval state
    message_to_sign = f"{recipient}|{subject}|{body_hash}|{status}|{timestamp}"
    signature_token = hmac.new(
        secret_key.encode("utf-8"),
        message_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    logger.info(
        "[email_sender.auth] issued authorization | status=%s grounding=%s policy=%s sig=%s",
        status, grounding_report.is_grounded, policy_report.approved_for_sending, signature_token[:12],
    )

    return SendAuthorization(
        status=status,
        authorized_by="ResponsePolicyEngine",
        structure_approved=structure_valid,
        grounding_approved=grounding_report.is_grounded,
        policy_approved=policy_report.approved_for_sending,
        signature_token=signature_token,
        timestamp=timestamp,
    )


def verify_send_authorization(
    authorization: SendAuthorization,
    recipient: str,
    subject: str,
    text_body: str,
    secret_key: str = _AUTH_SECRET_KEY,
) -> bool:
    """
    Verify the cryptographic signature and criteria of a SendAuthorization.
    """
    if authorization.status != "approved":
        return False
    if not (authorization.structure_approved and authorization.grounding_approved and authorization.policy_approved):
        return False

    body_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    expected_message = f"{recipient}|{subject}|{body_hash}|{authorization.status}|{authorization.timestamp}"
    expected_token = hmac.new(
        secret_key.encode("utf-8"),
        expected_message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(authorization.signature_token, expected_token)


class GroundedEmailSender:
    """
    Decoupled email sender.
    Refuses to send unless response has passed all validation and policy stages.
    """

    def __init__(self, dispatch_callback: Callable[[dict[str, Any]], Awaitable[bool]] | None = None):
        self._dispatch_callback = dispatch_callback

    async def send(self, payload: RenderedEmailPayload) -> SendResult:
        """
        Execute safe outbound email dispatch.

        Strictly enforces:
          - payload.approval_status == 'approved'
          - authorization is present and valid
          - cryptographic token verification passes
        """
        # Gate 1: Check approval status
        if payload.approval_status != "approved":
            logger.warning(
                "[email_sender] REFUSED to send: approval_status is '%s' (must be 'approved')",
                payload.approval_status,
            )
            return SendResult(
                sent=False,
                status="refused",
                reason=f"Sender refused unapproved payload: approval_status is '{payload.approval_status}'.",
            )

        # Gate 2: Check authorization presence
        auth = payload.authorization
        if not auth:
            logger.error("[email_sender] REFUSED to send: SendAuthorization object is missing.")
            return SendResult(
                sent=False,
                status="refused",
                reason="Sender refused unapproved payload: Missing SendAuthorization.",
            )

        # Gate 3: Check authorization status and gates
        if auth.status != "approved" or not auth.grounding_approved or not auth.policy_approved:
            logger.warning(
                "[email_sender] REFUSED to send: authorization status=%s grounding=%s policy=%s",
                auth.status, auth.grounding_approved, auth.policy_approved,
            )
            return SendResult(
                sent=False,
                status="refused",
                reason=f"Sender refused: Authorization status is '{auth.status}'.",
            )

        # Gate 4: Verify cryptographic HMAC token
        if not verify_send_authorization(
            authorization=auth,
            recipient=payload.recipient,
            subject=payload.subject,
            text_body=payload.text_body,
        ):
            logger.error("[email_sender] REFUSED to send: Invalid or tampered SendAuthorization signature.")
            return SendResult(
                sent=False,
                status="refused",
                reason="Sender refused unapproved payload: Invalid cryptographic authorization signature.",
            )

        # Authorized! Proceed with dispatch
        dispatch_id = f"disp_{uuid4().hex[:12]}"
        logger.info(
            "[email_sender] AUTHORIZED & DISPATCHING | recipient=%s subject='%s' dispatch_id=%s",
            payload.recipient, payload.subject, dispatch_id,
        )

        if self._dispatch_callback:
            try:
                await self._dispatch_callback({
                    "dispatch_id": dispatch_id,
                    "recipient": payload.recipient,
                    "subject": payload.subject,
                    "html_body": payload.html_body,
                    "text_body": payload.text_body,
                    "metadata": payload.metadata,
                })
            except Exception as e:
                logger.error("[email_sender] dispatch callback error: %s", e)
                return SendResult(
                    sent=False,
                    status="refused",
                    reason=f"Outbound dispatch callback failed: {e}",
                    dispatch_id=dispatch_id,
                )

        return SendResult(
            sent=True,
            status="sent",
            reason="Payload verified and dispatched via authorized channel.",
            dispatch_id=dispatch_id,
        )
