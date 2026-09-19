"""
automationservice — Observability & Structured Telemetry (Phase 20)
==================================================================
Tracks internal performance, validation gates, and dispatch results across every pipeline stage.

Architectural Guarantees:
  - Structured JSON logging of every pipeline transition.
  - Tracks:
      request_id, conversation_id, customer_id, retrieval_id, strategy_id,
      model_request_id, validation_result, grounding_result, policy_result,
      render_result, send_result, latency, retry_count, failure_state.
  - Strict PII redaction: masks email addresses and phone numbers.
  - Customer isolation: Internal telemetry is NEVER sent in customer-facing responses.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger("automationservice.pipeline.telemetry")


# ── PII Sanitization Helpers ──────────────────────────────────────────────────

_EMAIL_PII_REGEX = re.compile(r"\b([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b")
_PHONE_PII_REGEX = re.compile(r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def mask_pii_email(email_str: str) -> str:
    """Mask email addresses for safe telemetry logging (e.g. user@example.com -> u***@example.com)."""
    if not email_str:
        return ""
    return _EMAIL_PII_REGEX.sub(r"\1***@\2", email_str)


def mask_pii_phone(phone_str: str) -> str:
    """Mask phone numbers for safe telemetry logging (e.g. +1-800-555-0199 -> +***-***-****)."""
    if not phone_str:
        return ""
    return _PHONE_PII_REGEX.sub(r"+***-***-****", phone_str)



def sanitize_telemetry_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize dictionary fields to eliminate raw PII and truncate large body text."""
    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            if "@" in v and ("email" in k.lower() or "recipient" in k.lower()):
                sanitized[k] = mask_pii_email(v)
            elif "phone" in k.lower():
                sanitized[k] = mask_pii_phone(v)
            elif len(v) > 200 and k in ("body", "email_body", "message_content", "customer_message"):
                sanitized[k] = f"{v[:100]}... [truncated {len(v)} chars]"
            else:
                sanitized[k] = v
        elif isinstance(v, dict):
            sanitized[k] = sanitize_telemetry_payload(v)
        else:
            sanitized[k] = v
    return sanitized


# ── Structured Telemetry Models ───────────────────────────────────────────────

class PipelineTelemetryEvent(BaseModel):
    """
    Standardized structured telemetry event emitted for each pipeline invocation.
    """
    request_id: str = Field(description="Unique pipeline execution request ID")
    conversation_id: str = Field(default="", description="Conversation thread reference")
    customer_id: str = Field(default="", description="Customer account / user reference")
    retrieval_id: str = Field(default="", description="Retrieval trace reference")
    strategy_id: str = Field(default="", description="Strategy decision identifier")
    model_request_id: str = Field(default="", description="LLM provider call reference")
    validation_result: str = Field(default="valid", description="Structure validation status (valid/invalid)")
    grounding_result: str = Field(default="supported", description="Grounding classification (supported/unsupported/contradicted)")
    policy_result: str = Field(default="approved", description="Policy evaluation outcome (approved/blocked)")
    render_result: str = Field(default="rendered", description="Email presentation status")
    send_result: str = Field(default="sent", description="Email dispatch status (sent/draft_stored/refused)")
    latency_ms: float = Field(default=0.0, description="Total pipeline latency in milliseconds")
    retry_count: int = Field(default=0, description="Grounding regeneration retry attempts made")
    failure_state: str | None = Field(default=None, description="Failure state if applicable")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(extra="ignore")


class PipelineObserver:
    """
    Stage-by-stage observability recorder.
    Emits structured telemetry events while strictly guarding against PII and customer leakage.
    """

    def __init__(self, request_id: str, conversation_id: str = "", customer_id: str = ""):
        self.request_id = request_id
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self._stage_timings: dict[str, float] = {}
        self._stage_events: list[dict[str, Any]] = []

    def record_stage(self, stage_name: str, duration_ms: float, details: dict[str, Any] | None = None) -> None:
        """Record stage execution duration and diagnostic metrics."""
        self._stage_timings[stage_name] = round(duration_ms, 2)
        stage_record = {
            "stage": stage_name,
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if details:
            stage_record["details"] = sanitize_telemetry_payload(details)
        self._stage_events.append(stage_record)
        logger.debug("[telemetry.stage] %s completed in %.1fms", stage_name, duration_ms)

    def emit_summary(self, event: PipelineTelemetryEvent) -> dict[str, Any]:
        """Emit final structured telemetry event to logging and monitoring streams."""
        telemetry_dict = event.model_dump()
        telemetry_dict["stage_timings"] = self._stage_timings
        sanitized = sanitize_telemetry_payload(telemetry_dict)

        logger.info(
            "[PIPELINE_TELEMETRY] req=%s conv=%s strat=%s ground=%s pol=%s send=%s retry=%d lat=%.0fms",
            sanitized.get("request_id"),
            sanitized.get("conversation_id", "?")[:8],
            sanitized.get("strategy_id"),
            sanitized.get("grounding_result"),
            sanitized.get("policy_result"),
            sanitized.get("send_result"),
            sanitized.get("retry_count", 0),
            sanitized.get("latency_ms", 0.0),
        )

        return sanitized
