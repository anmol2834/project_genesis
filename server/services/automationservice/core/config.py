"""
automationservice — Service Configuration

sys.path note:
  This file lives at:  server/services/automationservice/core/config.py
  server/ is 4 levels up from this file's directory:
    dirname(__file__)   = .../core
    up 1                = .../automationservice
    up 2                = .../services
    up 3                = .../server   ← shared/ lives here
"""
from __future__ import annotations
import os
import sys

_CORE_DIR     = os.path.dirname(os.path.abspath(__file__))
_SVC_DIR      = os.path.dirname(_CORE_DIR)
_SERVICES_DIR = os.path.dirname(_SVC_DIR)
_SERVER_DIR   = os.path.dirname(_SERVICES_DIR)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from shared.config import get_config  # noqa — re-exported for convenience

# ── Service identity ───────────────────────────────────────────────────────────
SERVICE_PORT = 8009
SERVICE_NAME = "automationservice"

# ── Redis keys — MUST match emailservice/workers/ai_handoff_worker.py exactly ──
AUTOMATION_STREAM           = "automation_events"   # emailservice XADD here
AUTOMATION_NOTIFY           = "automation_notify"   # emailservice LPUSH here (wake signal)
AUTOMATION_RESPONSES        = "automation_responses"  # we XADD here → emailservice AutomationResponseWorker
AUTOMATION_RESPONSES_NOTIFY = "automation_responses_notify"  # we LPUSH here to wake AutomationResponseWorker

NOTIFY_BLPOP_TIMEOUT = 8     # seconds — BLPOP wait interval (< Upstash 10s idle timeout)
MAX_EVENTS_PER_CYCLE = 100   # max automation_events drained per wake cycle

# ── Dynamic fetch thresholds (implementation_plan.md spec) ────────────────────
SHORT_MSG_CHAR_THRESHOLD = 20   # if latest message body < 20 chars → fetch more context
FETCH_COUNT_SHORT        = 20   # msgs to fetch when body is short/ambiguous
FETCH_COUNT_NORMAL       = 10   # msgs to fetch for normal-length messages

# ── Dedup TTL ─────────────────────────────────────────────────────────────────
PROCESSED_DEDUP_TTL = 3600  # 1 hour — Redis SET NX key TTL for at-most-once processing
