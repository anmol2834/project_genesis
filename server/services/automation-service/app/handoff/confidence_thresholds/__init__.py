from app.handoff.confidence_engine import ConfidenceEngine

# Threshold constants used across the pipeline
SEND_THRESHOLD = 0.55
SKIP_THRESHOLD = 0.25
ESCALATE_THRESHOLD = 0.35
P1_SEND_THRESHOLD = 0.70
P3_SEND_THRESHOLD = 0.45

__all__ = [
    'ConfidenceEngine',
    'SEND_THRESHOLD',
    'SKIP_THRESHOLD',
    'ESCALATE_THRESHOLD',
    'P1_SEND_THRESHOLD',
    'P3_SEND_THRESHOLD',
]
