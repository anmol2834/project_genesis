"""
Handoff Metrics Collector - Complete observability for escalation system.

Task 6 fix (R8): all Redis calls are now async-safe.
record_* methods fire-and-forget coroutines on the running event loop.
get_* read methods are async def for use in API/dashboard handlers.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _get_redis():
    from app.core.resource_management import get_resource_manager
    return get_resource_manager().get_redis()


def _fire(coro):
    """Schedule coro on running loop; discard if no loop."""
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        try:
            coro.close()
        except Exception:
            pass


class HandoffMetrics:
    """
    Collects handoff system metrics.

    record_* -- sync-callable, fire-and-forget async Redis writes.
    get_*    -- async, for use in async API handlers / dashboards.
    """

    def __init__(self, redis_client=None, postgres_conn=None):
        self.metrics_prefix = "handoff:metrics:"

    # ------------------------------------------------------------------
    # Sync-safe write methods
    # ------------------------------------------------------------------

    def record_handoff_decision(self, tenant_id, decision, confidence_score, risk_level, latency_ms):
        _fire(self._write_decision(tenant_id, decision, confidence_score, risk_level, latency_ms))

    def record_escalation(self, tenant_id, priority, escalation_reason, queue_time_ms):
        _fire(self._write_escalation(tenant_id, priority, escalation_reason, queue_time_ms))

    def record_sla_breach(self, tenant_id, priority, breach_minutes):
        _fire(self._write_sla_breach(tenant_id, priority, breach_minutes))

    def record_ai_reentry(self, tenant_id, success, confidence):
        _fire(self._write_ai_reentry(tenant_id, success, confidence))

    # ------------------------------------------------------------------
    # Async write implementations
    # ------------------------------------------------------------------

    async def _write_decision(self, tenant_id, decision, confidence_score, risk_level, latency_ms):
        try:
            redis = _get_redis()
            date_key = datetime.utcnow().strftime("%Y%m%d")
            p = self.metrics_prefix
            bucket = self._bucket(confidence_score)
            pipe = redis.pipeline(transaction=False)
            pipe.hincrby(f"{p}decisions:{date_key}", tenant_id, 1)
            pipe.hincrby(f"{p}decisions:{date_key}:{decision}", tenant_id, 1)
            pipe.hincrby(f"{p}confidence:{date_key}:{bucket}", tenant_id, 1)
            pipe.hincrby(f"{p}risk:{date_key}:{risk_level}", tenant_id, 1)
            pipe.lpush(f"{p}latency:{tenant_id}", latency_ms)
            pipe.ltrim(f"{p}latency:{tenant_id}", 0, 999)
            pipe.expire(f"{p}decisions:{date_key}", 604800)
            await pipe.execute(raise_on_error=False)
        except Exception as exc:
            logger.debug("record_handoff_decision write failed: %s", exc)

    async def _write_escalation(self, tenant_id, priority, escalation_reason, queue_time_ms):
        try:
            redis = _get_redis()
            date_key = datetime.utcnow().strftime("%Y%m%d")
            p = self.metrics_prefix
            pipe = redis.pipeline(transaction=False)
            pipe.hincrby(f"{p}escalations:{date_key}", tenant_id, 1)
            pipe.hincrby(f"{p}priority:{date_key}:{priority}", tenant_id, 1)
            pipe.lpush(f"{p}queue_time:{tenant_id}", queue_time_ms)
            pipe.ltrim(f"{p}queue_time:{tenant_id}", 0, 999)
            await pipe.execute(raise_on_error=False)
        except Exception as exc:
            logger.debug("record_escalation write failed: %s", exc)

    async def _write_sla_breach(self, tenant_id, priority, breach_minutes):
        try:
            redis = _get_redis()
            date_key = datetime.utcnow().strftime("%Y%m%d")
            p = self.metrics_prefix
            pipe = redis.pipeline(transaction=False)
            pipe.hincrby(f"{p}sla_breach:{date_key}", tenant_id, 1)
            pipe.lpush(f"{p}breach_time:{tenant_id}", breach_minutes)
            pipe.ltrim(f"{p}breach_time:{tenant_id}", 0, 999)
            await pipe.execute(raise_on_error=False)
        except Exception as exc:
            logger.debug("record_sla_breach write failed: %s", exc)

    async def _write_ai_reentry(self, tenant_id, success, confidence):
        try:
            redis = _get_redis()
            date_key = datetime.utcnow().strftime("%Y%m%d")
            p = self.metrics_prefix
            outcome = "success" if success else "failure"
            pipe = redis.pipeline(transaction=False)
            pipe.hincrby(f"{p}reentry:{date_key}", tenant_id, 1)
            pipe.hincrby(f"{p}reentry:{date_key}:{outcome}", tenant_id, 1)
            await pipe.execute(raise_on_error=False)
        except Exception as exc:
            logger.debug("record_ai_reentry write failed: %s", exc)

    # ------------------------------------------------------------------
    # Async read methods
    # ------------------------------------------------------------------

    async def get_handoff_rate(self, tenant_id, hours=24):
        try:
            redis = _get_redis()
            decisions = escalations = 0
            for h in range(hours):
                dk = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                d = await redis.hget(f"{self.metrics_prefix}decisions:{dk}", tenant_id)
                e = await redis.hget(f"{self.metrics_prefix}escalations:{dk}", tenant_id)
                decisions += int(d or 0)
                escalations += int(e or 0)
            return escalations / decisions if decisions else 0.0
        except Exception:
            return 0.0

    async def get_average_latency(self, tenant_id):
        try:
            redis = _get_redis()
            samples = await redis.lrange(f"{self.metrics_prefix}latency:{tenant_id}", 0, -1)
            if not samples:
                return 0.0
            vals = [float(s) for s in samples]
            return sum(vals) / len(vals)
        except Exception:
            return 0.0

    async def get_sla_compliance_rate(self, tenant_id, hours=24):
        try:
            redis = _get_redis()
            total = breaches = 0
            for h in range(hours):
                dk = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                e = await redis.hget(f"{self.metrics_prefix}escalations:{dk}", tenant_id)
                b = await redis.hget(f"{self.metrics_prefix}sla_breach:{dk}", tenant_id)
                total += int(e or 0)
                breaches += int(b or 0)
            return 1.0 if total == 0 else 1.0 - (breaches / total)
        except Exception:
            return 0.0

    async def get_priority_distribution(self, tenant_id, hours=24):
        try:
            redis = _get_redis()
            out = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for h in range(hours):
                dk = (datetime.utcnow() - timedelta(hours=h)).strftime("%Y%m%d")
                for pri in out:
                    v = await redis.hget(f"{self.metrics_prefix}priority:{dk}:{pri}", tenant_id)
                    out[pri] += int(v or 0)
            return out
        except Exception:
            return {}

    async def get_dashboard_metrics(self, tenant_id):
        return {
            "handoff_rate_24h":          await self.get_handoff_rate(tenant_id),
            "avg_latency_ms":            await self.get_average_latency(tenant_id),
            "sla_compliance_24h":        await self.get_sla_compliance_rate(tenant_id),
            "priority_distribution_24h": await self.get_priority_distribution(tenant_id),
            "generated_at":              datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _bucket(confidence):
        if confidence >= 0.9:
            return "0.9-1.0"
        elif confidence >= 0.8:
            return "0.8-0.9"
        elif confidence >= 0.7:
            return "0.7-0.8"
        elif confidence >= 0.6:
            return "0.6-0.7"
        return "0.0-0.6"

    _bucket_confidence = _bucket


__all__ = ["HandoffMetrics"]
