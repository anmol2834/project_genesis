"""
automationservice — Grounded Response Generation Pipeline Contracts
====================================================================
Strictly typed Pydantic models defining boundaries between:
  1. Verified Retrieval
  2. Grounded Context Building & Conflict Detection
  3. Customer Requirements Extraction
  4. Response Input Contract
  5. Response Strategy Engine
  6. LLM Call #2 Generation
  7. Output Structure Validation
  8. Grounding Validation
  9. Response Policy Engine
  10. Final Response Payload
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ── Stage 1: Verified Evidence Schema ─────────────────────────────────────────

SourceType = Literal[
    "product",
    "company",
    "policy",
    "analytics",
    "customer",
    "availability",
    "delivery",
    "support",
    "general",
]

EvidenceStatus = Literal["verified", "unverified", "deprecated"]


class VerifiedEvidence(BaseModel):
    """
    Atomic piece of factual business evidence verified by upstream systems.
    The generation model is NEVER allowed to treat unverified data as trustworthy.
    """
    evidence_id: str = Field(description="Unique stable evidence identifier, e.g. ev_prod_101_price")
    source_type: SourceType = Field(description="Domain origin of this evidence")
    source_id: str = Field(description="Internal entity identifier, e.g. entry_id, user_id")
    entity_name: str = Field(default="", description="Name of the product, service, or policy subject")
    attribute: str = Field(default="", description="Specific property name, e.g. price, ram, return_window")
    claim: str = Field(description="Human-readable fact assertion, e.g. 'IngenAI Gaming Pro 15 price is $1099'")
    value: Any = Field(default=None, description="Typed value, e.g. 1099, '16GB', True")
    status: EvidenceStatus = Field(default="verified", description="Authoritative approval status")
    valid_from: str | None = Field(default=None, description="ISO timestamp or date validity start")
    valid_until: str | None = Field(default=None, description="ISO timestamp or date validity expiry")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context or provenance")
    allowed_for_customer_response: bool = Field(
        default=True,
        description="Whether this fact is permitted to be stated to the customer"
    )

    model_config = ConfigDict(extra="ignore")


# ── Stage 2: Conflict Representation ──────────────────────────────────────────

class EvidenceConflict(BaseModel):
    """
    Explicit representation of contradictory verified facts.
    OpenAI #2 must NOT resolve authoritative business conflicts on its own.
    """
    conflict: bool = True
    conflict_group_id: str = Field(description="Unique ID grouping conflicting facts")
    entity_name: str = Field(default="", description="Subject of the conflict")
    attribute: str = Field(default="", description="Attribute with contradicting claims")
    facts: list[str] = Field(default_factory=list, description="List of conflicting evidence_ids")
    conflicting_values: list[Any] = Field(default_factory=list, description="Contradicting values observed")
    resolution: Literal["unresolved", "resolved"] = "unresolved"
    resolution_reason: str | None = Field(default=None, description="Upstream reason if resolved")

    model_config = ConfigDict(extra="ignore")


# ── Stage 3: Customer Requirements Schema ─────────────────────────────────────

class HardRequirement(BaseModel):
    """Non-negotiable requirement that cannot be violated."""
    field: str = Field(description="Requirement attribute, e.g. budget, ram, location, product_type")
    operator: str = Field(default="==", description="Comparison operator: <=, >=, ==, in, contains")
    value: Any = Field(description="Required target value")
    raw_text: str = Field(default="", description="Original customer phrasing")

    model_config = ConfigDict(extra="ignore")


class SoftPreference(BaseModel):
    """Desirable preference that may be satisfied when possible."""
    field: str = Field(description="Preference attribute, e.g. preferred_brand, color, delivery_window")
    value: Any = Field(description="Preferred target value")
    raw_text: str = Field(default="", description="Original customer phrasing")
    weight: float = Field(default=0.5, description="Relative priority 0.0 - 1.0")

    model_config = ConfigDict(extra="ignore")


class CommunicationRequirements(BaseModel):
    """Directives on tone, language, and styling."""
    tone: str = Field(default="professional", description="e.g. professional, warm, formal, concise")
    language: str = Field(default="English", description="Target response language")
    length: Literal["concise", "standard", "detailed"] = "standard"
    include_pricing: bool = True
    include_alternatives: bool = True

    model_config = ConfigDict(extra="ignore")


class CustomerRequirements(BaseModel):
    """Structured representation of customer inquiry requirements."""
    hard: list[HardRequirement] = Field(default_factory=list)
    soft: list[SoftPreference] = Field(default_factory=list)
    communication: CommunicationRequirements = Field(default_factory=CommunicationRequirements)

    model_config = ConfigDict(extra="ignore")


# ── Stage 4: Response Strategy Schema ─────────────────────────────────────────

ResponseMode = Literal[
    "answer",          # Fully answered with verified facts
    "clarify",         # Clarification required from customer
    "partial_result",  # Some questions answered, others require details
    "no_match",        # No matching products or information in catalog
    "escalate",        # Critical conflict, customer complaint, or manual review required
]


class ResponseStrategy(BaseModel):
    """
    Determined by Response Strategy Engine BEFORE OpenAI Call #2.
    OpenAI #2 CANNOT override this mode.
    """
    mode: ResponseMode = Field(default="answer", description="Mandated response mode")
    objective: str = Field(description="Clear operational objective for Call #2")
    required_sections: list[str] = Field(
        default_factory=lambda: ["greeting", "direct_answer", "next_steps", "closing"],
        description="Mandatory sections in the generated response"
    )
    allowed_actions: list[str] = Field(default_factory=list, description="Permitted actions, e.g. quote_price")
    missing_information: list[str] = Field(default_factory=list, description="Known missing information items")
    required_clarifications: list[str] = Field(
        default_factory=list,
        description="Specific questions customer must be asked if mode=clarify"
    )
    allowed_facts: list[str] = Field(
        default_factory=list,
        description="Whitelist of evidence_ids permitted in the response"
    )
    prohibited_facts: list[str] = Field(
        default_factory=list,
        description="Blacklist of evidence_ids forbidden from mention (e.g. conflicting)"
    )
    allow_pricing: bool = True
    allow_availability: bool = True
    allow_alternatives: bool = True

    model_config = ConfigDict(extra="ignore")


# ── Stage 5: Response Input Contract ──────────────────────────────────────────

class RequestContext(BaseModel):
    customer_message: str = Field(description="The latest triggering customer message")
    subject: str = Field(default="", description="Conversation subject line")
    thread_id: str = Field(default="", description="Thread or conversation reference")
    objective: Literal["recommend", "answer", "clarify", "follow_up", "other"] = "answer"
    history_summary: str = Field(default="", description="Clean historical conversation context")

    model_config = ConfigDict(extra="ignore")


class BusinessContextSummary(BaseModel):
    company_name: str = Field(default="Our Team")
    business_type: str = Field(default="")
    industry: list[str] = Field(default_factory=list)
    communication_style: str = Field(default="professional")
    brand_rules: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class ResponseConstraints(BaseModel):
    must_not_claim: list[str] = Field(default_factory=list)
    must_not_offer: list[str] = Field(default_factory=list)
    required_disclosures: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class ResponseInputContract(BaseModel):
    """
    Strict input contract passed to OpenAI Call #2.
    Contains ONLY verified facts, customer requirements, business context,
    constraints, and the mandated strategy mode.
    No internal infrastructure noise is sent.
    """
    request: RequestContext
    customer_requirements: CustomerRequirements
    business_context: BusinessContextSummary
    verified_facts: list[VerifiedEvidence]
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    constraints: ResponseConstraints = Field(default_factory=ResponseConstraints)
    response_strategy: ResponseStrategy

    model_config = ConfigDict(extra="ignore")


# ── Stage 6: Claim-Level Traceability Schema (Phase 9 & 11) ──────────────────

ClaimClassification = Literal[
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
]

ViolationType = Literal[
    "none",
    "hallucination",
    "unsupported_expansion",
    "unsupported_inference",
    "contradiction",
    "policy_violation",
]


class ClaimItem(BaseModel):
    """
    Atomic customer-facing claim mapped to supporting verified evidence IDs.
    Directly enforces: CUSTOMER CLAIM -> EVIDENCE REFERENCE -> VERIFIED SOURCE.
    """
    claim_id: str = Field(description="Unique claim ID, e.g. c1, c2")
    text: str = Field(description="Specific factual assertion stated in the email body")
    evidence_ids: list[str] = Field(default_factory=list, description="Verified evidence_ids directly supporting this claim")

    model_config = ConfigDict(extra="ignore")


class ValidatedClaimItem(BaseModel):
    """
    Result of claim-by-claim verification in Phase 11 Grounding Validator.
    """
    claim_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    classification: ClaimClassification = "supported"
    violation_type: ViolationType = "none"
    reason: str = ""
    violations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class LLMCall2Output(BaseModel):
    """
    Strict structured output produced by OpenAI Call #2 with Claim-Level Traceability.
    """
    response_mode: ResponseMode = Field(description="Echoes the mandated response mode")
    subject: str = Field(default="", description="Customer-facing email subject line")
    body: str = Field(default="", description="Customer-facing email body prose")
    claims: list[ClaimItem] = Field(default_factory=list, description="List of atomic claims with evidence citations")
    missing_information: list[str] = Field(default_factory=list, description="Known missing information items")
    limitations: list[str] = Field(default_factory=list, description="Operational or catalog limitations stated")
    requires_human_review: bool = Field(default=False, description="Whether LLM flagged need for manual attention")
    clarification_questions: list[str] = Field(default_factory=list, description="Clarification questions if mode=clarify")

    # Backward compatibility aliases
    email_subject: str = Field(default="", description="Alias for subject")
    email_body: str = Field(default="", description="Alias for body")
    sources_used: list[str] = Field(default_factory=list, description="Aggregated list of evidence_ids")
    claims_made: list[str] = Field(default_factory=list, description="List of raw claim strings")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def model_post_init(self, __context: Any) -> None:
        # Sync subject / email_subject
        if not self.subject and self.email_subject:
            self.subject = self.email_subject
        elif self.subject and not self.email_subject:
            self.email_subject = self.subject

        # Sync body / email_body
        if not self.body and self.email_body:
            self.body = self.email_body
        elif self.body and not self.email_body:
            self.email_body = self.body

        # Aggregate sources_used from claims if not provided
        if not self.sources_used and self.claims:
            ev_set: list[str] = []
            for c in self.claims:
                for eid in c.evidence_ids:
                    if eid and eid not in ev_set:
                        ev_set.append(eid)
            self.sources_used = ev_set

        # Aggregate claims_made strings
        if not self.claims_made and self.claims:
            self.claims_made = [c.text for c in self.claims if c.text]


# ── Stage 7: Output Structure Validation Report (Phase 10) ───────────────────

class OutputStructureValidationReport(BaseModel):
    """
    Detailed report from Output Structure Validator immediately after Call #2.
    """
    is_valid: bool = Field(description="True if output satisfies all structural criteria")
    errors: list[str] = Field(default_factory=list, description="Structural failure reasons")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal structural warnings")
    missing_fields: list[str] = Field(default_factory=list, description="Required fields that were absent")
    forbidden_metadata_detected: list[str] = Field(default_factory=list, description="Internal architectural strings leaked")
    strategy_compatible: bool = True

    model_config = ConfigDict(extra="ignore")


# ── Stage 8: Grounding Validation Report (Phase 11) ───────────────────────────

GroundingOverallClassification = Literal[
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "policy_violation",
]


class GroundingReport(BaseModel):
    """
    Comprehensive report produced by Grounding Validator verifying factual grounding.
    """
    is_grounded: bool = Field(description="True if all claims are fully supported by verified evidence")
    grounding_score: float = Field(default=1.0, description="0.0 to 1.0 confidence in factuality")
    overall_classification: GroundingOverallClassification = "supported"
    claims_evaluation: list[ValidatedClaimItem] = Field(default_factory=list)
    supported_claims_count: int = 0
    partially_supported_claims_count: int = 0
    unsupported_claims_count: int = 0
    contradicted_claims_count: int = 0
    policy_violations_count: int = 0
    cited_evidence_valid: bool = True
    invalid_citations: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    prohibited_claims_detected: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    regeneration_count: int = 0
    max_regenerations_reached: bool = False

    model_config = ConfigDict(extra="ignore")


# ── Stage 8b: Grounding Action Directive (Phase 12) ───────────────────────────

class GroundingActionDirective(BaseModel):
    """
    Deterministic routing directive produced by Grounding Failure Handler.
    """
    decision: Literal["continue", "regenerate", "sanitize", "block", "escalate"]
    can_send: bool = False
    requires_human_review: bool = False
    reason: str = ""
    corrective_instructions: str | None = None
    sanitized_output: LLMCall2Output | None = None

    model_config = ConfigDict(extra="ignore")


# ── Stage 9: Response Policy Report (Phase 13) ────────────────────────────────

class PolicyReport(BaseModel):
    """
    Report produced by Response Policy Engine deciding operational actions.
    """
    approved_for_sending: bool = Field(description="Whether the response satisfies all policies to auto-send")
    action: Literal["reply", "draft", "escalate"] = "reply"
    send_email: bool = Field(description="Strict boolean whether to dispatch email to customer")
    escalation_requested: bool = False
    escalation_reason: str | None = None
    confidence_score: float = Field(default=0.0, description="Overall pipeline confidence score")
    disclaimers_added: list[str] = Field(default_factory=list)
    policy_violations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


# ── Stage 10: Email Presentation & Authorization (Phases 14 & 15) ──────────────

class SendAuthorization(BaseModel):
    """
    Cryptographic send authorization gate.
    OpenAI #2 NEVER calls email providers directly.
    EmailSender MUST REFUSE to send unless status == 'approved' and signature is valid.
    """
    status: Literal["approved", "rejected", "draft_only", "escalated"] = "draft_only"
    authorized_by: str = "ResponsePolicyEngine"
    structure_approved: bool = False
    grounding_approved: bool = False
    policy_approved: bool = False
    signature_token: str = Field(default="", description="Cryptographic HMAC-SHA256 signature")
    timestamp: str = Field(default="", description="ISO timestamp of authorization")

    model_config = ConfigDict(extra="ignore")


class RenderedEmailPayload(BaseModel):
    """
    Semantically passive email presentation output.
    Contains HTML and plain text versions with zero newly introduced claims or pricing changes.
    """
    recipient: str = ""
    subject: str = ""
    html_body: str = ""
    text_body: str = ""
    approval_status: Literal["approved", "rejected", "draft_only", "escalated"] = "draft_only"
    authorization: SendAuthorization | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class SendResult(BaseModel):
    """
    Final result from Email Sender execution.
    """
    sent: bool = False
    status: Literal["sent", "refused", "draft_stored", "escalated"] = "refused"
    reason: str | None = None
    dispatch_id: str | None = None

    model_config = ConfigDict(extra="ignore")


# ── Stage 10b: Customer vs Internal Isolation (Phase 18) ──────────────────────

class CustomerResponse(BaseModel):
    """
    Strictly isolated customer-facing payload.
    Contains ZERO internal diagnostics, Qdrant references, or confidence scores.
    """
    subject: str = ""
    body: str = ""
    html_body: str = ""
    text_body: str = ""
    action: Literal["reply", "draft", "escalate"] = "reply"
    send_email: bool = False
    approval_status: str = "draft_only"
    disclaimers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class InternalValidationDiagnostics(BaseModel):
    """
    Strictly internal validation diagnostics and telemetry.
    NEVER exposed to customer or serialized into customer emails.
    """
    request_id: str = ""
    conversation_id: str = ""
    customer_id: str = ""
    retrieval_id: str = ""
    strategy_id: str = ""
    composite_confidence: float = 0.0
    retrieval_scores: list[float] = Field(default_factory=list)
    ranking_values: dict[str, float] = Field(default_factory=dict)
    model_name: str = ""
    latency_ms: float = 0.0
    structure_valid: bool = True
    grounding_report: GroundingReport | None = None
    policy_report: PolicyReport | None = None
    send_authorization: SendAuthorization | None = None
    send_result: SendResult | None = None
    retry_count: int = 0
    injection_detected: bool = False
    failure_state: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


# ── Final Pipeline Response ───────────────────────────────────────────────────

class GroundedPipelineResponse(BaseModel):
    """
    Comprehensive result of the Grounded Response Generation Pipeline.
    Strictly enforces separation between customer_response and internal_validation (Phase 18).
    Maintains 100% backward compatibility for all existing properties.
    """
    customer_response: CustomerResponse | None = None
    internal_validation: InternalValidationDiagnostics | None = None

    # Backward-compatible fields
    answerable: bool
    confidence: float
    action: Literal["reply", "draft", "escalate"]
    send_email: bool
    email_subject: str
    email_body: str
    strategy_mode: ResponseMode
    escalation_requested: bool = False
    escalation_reason: str | None = None
    requires_human_review: bool = False
    missing_information: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    grounding_report: GroundingReport
    policy_report: PolicyReport
    rendered_email: RenderedEmailPayload | None = None
    send_authorization: SendAuthorization | None = None
    send_result: SendResult | None = None
    contract_summary: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict, alias="_meta")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    def model_post_init(self, __context: Any) -> None:
        # Populate customer_response if not explicitly set
        if self.customer_response is None:
            self.customer_response = CustomerResponse(
                subject=self.email_subject,
                body=self.email_body,
                html_body=self.rendered_email.html_body if self.rendered_email else "",
                text_body=self.rendered_email.text_body if self.rendered_email else self.email_body,
                action=self.action,
                send_email=self.send_email,
                approval_status=self.send_authorization.status if self.send_authorization else "draft_only",
                disclaimers=self.policy_report.disclaimers_added if self.policy_report else [],
            )

        # Populate internal_validation if not explicitly set
        if self.internal_validation is None:
            self.internal_validation = InternalValidationDiagnostics(
                composite_confidence=self.confidence,
                model_name=str(self.meta.get("model", "")),
                latency_ms=float(self.meta.get("elapsed_ms", 0.0)),
                structure_valid=bool(self.contract_summary.get("structure_valid", True)),
                grounding_report=self.grounding_report,
                policy_report=self.policy_report,
                send_authorization=self.send_authorization,
                send_result=self.send_result,
                retry_count=self.grounding_report.regeneration_count if self.grounding_report else 0,
                diagnostics=self.contract_summary,
            )



