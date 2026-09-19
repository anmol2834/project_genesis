"""
automationservice — Pipeline Package
====================================
Public interfaces for the Grounded Response Generation Pipeline (Phases 1-20).
"""
from pipeline.contracts import (
    VerifiedEvidence,
    EvidenceConflict,
    HardRequirement,
    SoftPreference,
    CommunicationRequirements,
    CustomerRequirements,
    ResponseStrategy,
    ResponseMode,
    ResponseInputContract,
    ClaimItem,
    ValidatedClaimItem,
    LLMCall2Output,
    OutputStructureValidationReport,
    GroundingReport,
    GroundingActionDirective,
    PolicyReport,
    SendAuthorization,
    RenderedEmailPayload,
    SendResult,
    CustomerResponse,
    InternalValidationDiagnostics,
    GroundedPipelineResponse,
)
from pipeline.evidence_retrieval import extract_verified_evidence
from pipeline.customer_requirements import extract_customer_requirements
from pipeline.grounded_context_builder import build_grounded_context, GroundedContextPackage
from pipeline.strategy_engine import determine_response_strategy
from pipeline.output_validator import validate_generation_output
from pipeline.grounding_validator import validate_grounding
from pipeline.grounding_failure_handler import handle_grounding_result, sanitize_partially_supported_output
from pipeline.policy_engine import evaluate_response_policy
from pipeline.email_renderer import render_email, verify_semantic_passivity
from pipeline.email_sender import (
    issue_send_authorization,
    verify_send_authorization,
    GroundedEmailSender,
    SendAuthorizationError,
)
from pipeline.injection_defense import (
    InjectionScanResult,
    scan_untrusted_input,
    sanitize_untrusted_input,
    fence_untrusted_content,
    verify_no_injection_compliance,
)
from pipeline.failure_handler import (
    FailureState,
    FailureResolution,
    resolve_failure_state,
)
from pipeline.observability import (
    PipelineTelemetryEvent,
    PipelineObserver,
    mask_pii_email,
    mask_pii_phone,
    sanitize_telemetry_payload,
)
from pipeline.response_pipeline import run_grounded_response_pipeline

__all__ = [
    "VerifiedEvidence",
    "EvidenceConflict",
    "HardRequirement",
    "SoftPreference",
    "CommunicationRequirements",
    "CustomerRequirements",
    "ResponseStrategy",
    "ResponseMode",
    "ResponseInputContract",
    "ClaimItem",
    "ValidatedClaimItem",
    "LLMCall2Output",
    "OutputStructureValidationReport",
    "GroundingReport",
    "GroundingActionDirective",
    "PolicyReport",
    "SendAuthorization",
    "RenderedEmailPayload",
    "SendResult",
    "CustomerResponse",
    "InternalValidationDiagnostics",
    "GroundedPipelineResponse",
    "extract_verified_evidence",
    "extract_customer_requirements",
    "build_grounded_context",
    "GroundedContextPackage",
    "determine_response_strategy",
    "validate_generation_output",
    "validate_grounding",
    "handle_grounding_result",
    "sanitize_partially_supported_output",
    "evaluate_response_policy",
    "render_email",
    "verify_semantic_passivity",
    "issue_send_authorization",
    "verify_send_authorization",
    "GroundedEmailSender",
    "SendAuthorizationError",
    "InjectionScanResult",
    "scan_untrusted_input",
    "sanitize_untrusted_input",
    "fence_untrusted_content",
    "verify_no_injection_compliance",
    "FailureState",
    "FailureResolution",
    "resolve_failure_state",
    "PipelineTelemetryEvent",
    "PipelineObserver",
    "mask_pii_email",
    "mask_pii_phone",
    "sanitize_telemetry_payload",
    "run_grounded_response_pipeline",
]
