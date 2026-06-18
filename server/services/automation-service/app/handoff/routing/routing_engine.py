"""
Routing Engine — Intelligent human assignment based on skills, load, availability.

Task 7 fix (R7):
  Original used synchronous psycopg2-style cursor calls (pg_conn.cursor()) on
  what is actually an async SQLAlchemy AsyncSession / AsyncEngine from the
  resource manager.  Calling .cursor() on an AsyncSession raises:
      AttributeError: 'AsyncSession' has no attribute 'cursor'

  Fix:
  - __init__ no longer calls _ensure_routing_tables() synchronously at construction.
  - Table DDL is deferred to an async _ensure_tables() that runs on first use.
  - route_ticket() and all DB-reading helpers are now async.
  - All queries use SQLAlchemy text() + resource manager get_db_session().
  - Redis calls use the async Redis client via fire-and-forget (same pattern as
    metrics_collector.py) since route_ticket is called from a sync context in
    evaluate_handoff but runs inside the async execution engine.

  postgres_conn parameter is retained in __init__ for backward-compat but unused.
"""

import logging
import random
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DDL — table definitions (idempotent CREATE TABLE IF NOT EXISTS)
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_AGENTS_SQL = """
CREATE TABLE IF NOT EXISTS handoff_agents (
    id              SERIAL PRIMARY KEY,
    tenant_id       VARCHAR(255) NOT NULL,
    agent_id        VARCHAR(255) NOT NULL,
    agent_name      VARCHAR(255) NOT NULL,
    agent_email     VARCHAR(255),
    skills          JSONB DEFAULT '[]',
    max_concurrent  INT DEFAULT 5,
    is_available    BOOLEAN DEFAULT TRUE,
    priority_tier   INT DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, agent_id)
);
"""

_CREATE_RULES_SQL = """
CREATE TABLE IF NOT EXISTS handoff_routing_rules (
    id               SERIAL PRIMARY KEY,
    tenant_id        VARCHAR(255) NOT NULL,
    rule_name        VARCHAR(255) NOT NULL,
    conditions       JSONB NOT NULL,
    routing_strategy VARCHAR(50) NOT NULL,
    target_agents    JSONB,
    priority         INT DEFAULT 0,
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT NOW()
);
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_resource_manager():
    from app.core.resource_management import get_resource_manager
    return get_resource_manager()


def _fire_and_forget(coro) -> None:
    """Schedule a coroutine on the running event loop without blocking."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            coro.close()
        except Exception:
            pass


class RoutingStrategy(Enum):
    ROUND_ROBIN    = "round_robin"
    LEAST_LOADED   = "least_loaded"
    SKILL_BASED    = "skill_based"
    PRIORITY_BASED = "priority_based"


# ─────────────────────────────────────────────────────────────────────────────
# RoutingEngine
# ─────────────────────────────────────────────────────────────────────────────

class RoutingEngine:
    """Routes escalated tickets to appropriate human agents."""

    def __init__(self, redis_client=None, postgres_conn=None):
        # redis_client / postgres_conn retained for backward-compat with
        # HandoffOrchestrator(redis_client, postgres_conn) but are unused.
        # All I/O goes through the async resource manager.
        self._tables_initialized = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def route_ticket(
        self,
        tenant_id: str,
        ticket_id: str,
        priority: str,
        escalation_reason: str,
        risk_categories: List[str],
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Route ticket to appropriate agent.
        Returns routing dict: agent_id, agent_name, routing_strategy, routing_reason.
        Always returns a valid dict — falls back to support_team if no agents available.
        """
        await self._ensure_tables()

        routing_rule = await self._get_matching_rule(
            tenant_id, priority, risk_categories, escalation_reason
        )

        if routing_rule:
            strategy     = routing_rule.get("routing_strategy", "round_robin")
            target_agents = routing_rule.get("target_agents") or []
        else:
            strategy      = "least_loaded"
            target_agents = []

        selected_agent = await self._select_agent(
            tenant_id, strategy, target_agents, priority, risk_categories
        )

        if selected_agent:
            _fire_and_forget(
                self._track_assignment(tenant_id, selected_agent["agent_id"])
            )
            logger.info("Routed ticket %s to agent %s", ticket_id, selected_agent["agent_id"])
            return {
                "agent_id":        selected_agent["agent_id"],
                "agent_name":      selected_agent["agent_name"],
                "agent_email":     selected_agent.get("agent_email"),
                "routing_strategy": strategy,
                "routing_reason":  (
                    f"Matched rule: {routing_rule['rule_name']}"
                    if routing_rule else "default_routing"
                ),
            }

        # Fallback — no agents configured / available
        return {
            "agent_id":        "support_team",
            "agent_name":      "Support Team",
            "agent_email":     None,
            "routing_strategy": "fallback",
            "routing_reason":  "No available agents, using team queue",
        }

    # ── Table initialisation (deferred) ───────────────────────────────────────

    async def _ensure_tables(self) -> None:
        """Create routing tables once per process (idempotent DDL)."""
        if self._tables_initialized:
            return
        try:
            from sqlalchemy import text
            rm = _get_resource_manager()
            async with rm.get_db_session() as session:
                await session.execute(text(_CREATE_AGENTS_SQL))
                await session.execute(text(_CREATE_RULES_SQL))
            self._tables_initialized = True
            logger.debug("Routing tables ensured")
        except Exception as e:
            logger.warning("Could not create routing tables: %s", e)
            # Non-fatal: tables may already exist; mark initialized to avoid retrying
            self._tables_initialized = True

    # ── Redis assignment tracker (async, fire-and-forget) ─────────────────────

    async def _track_assignment(self, tenant_id: str, agent_id: str) -> None:
        try:
            redis = _get_resource_manager().get_redis()
            key   = f"handoff:assignment:{tenant_id}:{agent_id}"
            await redis.hincrby(key, "current_load", 1)
            await redis.expire(key, 3600)
        except Exception as e:
            logger.debug("Assignment tracking failed: %s", e)

    # ── Routing rule lookup ───────────────────────────────────────────────────

    async def _get_matching_rule(
        self,
        tenant_id: str,
        priority: str,
        risk_categories: List[str],
        escalation_reason: str,
    ) -> Optional[Dict]:
        try:
            from sqlalchemy import text
            rm = _get_resource_manager()
            async with rm.get_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT rule_name, routing_strategy, target_agents, conditions
                        FROM handoff_routing_rules
                        WHERE tenant_id = :tid AND is_active = TRUE
                        ORDER BY priority DESC
                    """),
                    {"tid": tenant_id},
                )
                rows = result.fetchall()

            for row in rows:
                rule_name, routing_strategy, target_agents, conditions = row
                if self._match_conditions(
                    conditions or {}, priority, risk_categories, escalation_reason
                ):
                    return {
                        "rule_name":        rule_name,
                        "routing_strategy": routing_strategy,
                        "target_agents":    target_agents or [],
                    }
            return None
        except Exception as e:
            logger.debug("_get_matching_rule failed: %s", e)
            return None

    def _match_conditions(
        self,
        conditions: Dict,
        priority: str,
        risk_categories: List[str],
        escalation_reason: str,
    ) -> bool:
        if "priorities" in conditions:
            if priority not in conditions["priorities"]:
                return False
        if "risk_categories" in conditions:
            if not any(rc in risk_categories for rc in conditions["risk_categories"]):
                return False
        if "keywords" in conditions:
            reason_lower = escalation_reason.lower()
            if not any(kw.lower() in reason_lower for kw in conditions["keywords"]):
                return False
        return True

    # ── Agent selection ───────────────────────────────────────────────────────

    async def _select_agent(
        self,
        tenant_id: str,
        strategy: str,
        target_agents: List[str],
        priority: str,
        risk_categories: List[str],
    ) -> Optional[Dict]:
        agents = await self._get_available_agents(tenant_id, target_agents)
        if not agents:
            return None

        if strategy == "round_robin":
            return random.choice(agents)
        elif strategy == "least_loaded":
            return await self._least_loaded_select(agents, tenant_id)
        elif strategy == "skill_based":
            return self._skill_based_select(agents, risk_categories)
        elif strategy == "priority_based":
            return self._priority_based_select(agents, priority)
        else:
            return agents[0]

    async def _get_available_agents(
        self, tenant_id: str, target_agents: List[str]
    ) -> List[Dict]:
        try:
            from sqlalchemy import text
            rm = _get_resource_manager()
            async with rm.get_db_session() as session:
                if target_agents:
                    result = await session.execute(
                        text("""
                            SELECT tenant_id, agent_id, agent_name, agent_email,
                                   skills, max_concurrent, priority_tier
                            FROM handoff_agents
                            WHERE tenant_id = :tid
                              AND agent_id  = ANY(:agents)
                              AND is_available = TRUE
                        """),
                        {"tid": tenant_id, "agents": target_agents},
                    )
                else:
                    result = await session.execute(
                        text("""
                            SELECT tenant_id, agent_id, agent_name, agent_email,
                                   skills, max_concurrent, priority_tier
                            FROM handoff_agents
                            WHERE tenant_id = :tid AND is_available = TRUE
                        """),
                        {"tid": tenant_id},
                    )
                cols = list(result.keys())
                return [dict(zip(cols, row)) for row in result.fetchall()]
        except Exception as e:
            logger.debug("_get_available_agents failed: %s", e)
            return []

    async def _least_loaded_select(
        self, agents: List[Dict], tenant_id: str
    ) -> Dict:
        """Select agent with least current load (reads from Redis)."""
        redis = _get_resource_manager().get_redis()
        agent_loads: List[tuple] = []
        for agent in agents:
            try:
                key  = f"handoff:assignment:{tenant_id}:{agent['agent_id']}"
                raw  = await redis.hget(key, "current_load")
                load = int(raw or 0)
            except Exception:
                load = 0
            max_c = agent.get("max_concurrent", 5)
            if load < max_c:
                agent_loads.append((agent, load))

        if agent_loads:
            return min(agent_loads, key=lambda x: x[1])[0]
        return agents[0]

    def _skill_based_select(
        self, agents: List[Dict], risk_categories: List[str]
    ) -> Dict:
        scored = [
            (a, len(set(a.get("skills") or []) & set(risk_categories)))
            for a in agents
        ]
        return max(scored, key=lambda x: x[1])[0]

    def _priority_based_select(self, agents: List[Dict], priority: str) -> Dict:
        tier_map  = {"critical": 1, "high": 1, "medium": 2, "low": 3}
        required  = tier_map.get(priority, 2)
        eligible  = [a for a in agents if a.get("priority_tier", 1) <= required]
        return eligible[0] if eligible else agents[0]


__all__ = ["RoutingEngine", "RoutingStrategy"]
