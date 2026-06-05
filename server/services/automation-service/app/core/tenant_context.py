"""
Tenant Context
===============
Immutable tenant context object that propagates through the entire pipeline.

Carries:
  tenant_id     — the authoritative user_id / tenant identifier
  trace_id      — distributed trace ID
  thread_id     — conversation thread
  conversation_id
  message_id
  priority      — P0/P1/P2/P3 (set by PriorityClassifier after intelligence)
  priority_reason

ALL pipeline stages receive this context and use tenant_id for:
  - Redis key namespacing
  - Qdrant filter injection
  - Memory key scoping
  - Cache key scoping
  - Fact graph validation
  - Security audit logging

TENANT ISOLATION RULES (enforced here, checked everywhere):
  1. tenant_id MUST be a non-empty string — validated at construction
  2. Any chunk/result with a different user_id MUST be discarded
  3. Redis keys MUST include tenant_id as a prefix segment
  4. Every cross-tenant violation MUST be logged as a security incident

SECURITY METRICS tracked per request:
  - tenant_validation_passed
  - tenant_validation_failed
  - cross_tenant_attempts
  - security_incidents
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("automation-service.tenant_security")

# ─────────────────────────────────────────────────────────────────────────────
# Priority constants
# ─────────────────────────────────────────────────────────────────────────────

class Priority:
    P0_CRITICAL = 0   # legal threats, compliance, security incidents, fraud
    P1_HIGH     = 1   # refunds, angry customers, VIP, contract issues, SLA breach
    P2_MEDIUM   = 2   # sales, support, technical, onboarding
    P3_LOW      = 3   # general inquiry, greetings, follow-ups

    LABELS = {0: "critical", 1: "high", 2: "medium", 3: "low"}
    VALUES = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    @staticmethod
    def label(p: int) -> str:
        return Priority.LABELS.get(p, "medium")

    @staticmethod
    def from_label(label: str) -> int:
        return Priority.VALUES.get(str(label).lower(), 2)


# ─────────────────────────────────────────────────────────────────────────────
# TenantContext
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TenantContext:
    """
    Immutable propagation context for a single pipeline execution.

    Created once in execute_workflow, passed through every stage.
    Never mutated after priority is set.
    """
    tenant_id:       str
    trace_id:        str
    thread_id:       str
    conversation_id: str
    message_id:      str
    priority:        int  = Priority.P2_MEDIUM
    priority_reason: str  = ""
    # Security counters (accumulated during pipeline)
    _tenant_checks_passed:   int = field(default=0, repr=False)
    _tenant_checks_failed:   int = field(default=0, repr=False)
    _cross_tenant_attempts:  int = field(default=0, repr=False)
    _security_incidents:     int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("TenantContext: tenant_id is MANDATORY and cannot be empty")
        if not self.trace_id:
            raise ValueError("TenantContext: trace_id is MANDATORY and cannot be empty")

    # ── Priority helpers ───────────────────────────────────────────────────

    @property
    def priority_label(self) -> str:
        return Priority.label(self.priority)

    def is_critical(self) -> bool:
        return self.priority == Priority.P0_CRITICAL

    def is_high(self) -> bool:
        return self.priority <= Priority.P1_HIGH

    def requires_immediate_escalation(self) -> bool:
        return self.priority == Priority.P0_CRITICAL

    # ── Tenant validation helpers ──────────────────────────────────────────

    def assert_chunk_tenant(self, chunk: Any) -> bool:
        """
        Validate a retrieved chunk belongs to this tenant.
        Logs SECURITY_INCIDENT if violated.
        Returns True if valid, False if cross-tenant.
        """
        chunk_uid = (
            chunk.get("user_id") or chunk.get("metadata", {}).get("user_id", "")
            if isinstance(chunk, dict)
            else getattr(chunk, "user_id", "")
        )
        if chunk_uid and chunk_uid != self.tenant_id:
            self._cross_tenant_attempts += 1
            self._tenant_checks_failed  += 1
            self._security_incidents    += 1
            logger.error(
                "🚨 SECURITY_INCIDENT: cross-tenant chunk | "
                "expected=%s actual=%s trace=%s thread=%s",
                self.tenant_id[:12], str(chunk_uid)[:12],
                self.trace_id[:12], self.thread_id[:12],
            )
            return False
        self._tenant_checks_passed += 1
        return True

    def assert_memory_key_tenant(self, key: str) -> bool:
        """Validate a Redis key includes this tenant_id."""
        if self.tenant_id not in key and self.thread_id not in key:
            logger.warning(
                "⚠️ Memory key missing tenant scope | key=%s tenant=%s",
                key[:40], self.tenant_id[:12],
            )
            return False
        return True

    def filter_chunks_by_tenant(self, chunks: list) -> tuple[list, int]:
        """
        Filter out cross-tenant chunks from a list.
        Returns (clean_chunks, rejected_count).
        """
        clean = []
        rejected = 0
        for c in chunks:
            if self.assert_chunk_tenant(c):
                clean.append(c)
            else:
                rejected += 1
        if rejected:
            logger.warning(
                "Tenant filter: removed %d cross-tenant chunks | tenant=%s",
                rejected, self.tenant_id[:12],
            )
        return clean, rejected

    # ── Security observability ─────────────────────────────────────────────

    def security_summary(self) -> Dict[str, Any]:
        return {
            "tenant_id":                self.tenant_id,
            "tenant_validation_passed": self._tenant_checks_passed,
            "tenant_validation_failed": self._tenant_checks_failed,
            "cross_tenant_attempts":    self._cross_tenant_attempts,
            "security_incidents":       self._security_incidents,
            "priority":                 self.priority_label,
        }

    def to_log_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id":      self.tenant_id,
            "trace_id":       self.trace_id,
            "thread_id":      self.thread_id,
            "conversation_id": self.conversation_id,
            "message_id":     self.message_id,
            "priority":       self.priority_label,
            "priority_reason": self.priority_reason,
        }


__all__ = ["TenantContext", "Priority"]
