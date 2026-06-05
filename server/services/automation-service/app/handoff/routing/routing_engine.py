"""
Routing Engine - Intelligent human assignment based on skills, load, availability
"""
import logging
from typing import Optional, List, Dict
from enum import Enum
import random

logger = logging.getLogger(__name__)

class RoutingStrategy(Enum):
    """Routing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    SKILL_BASED = "skill_based"
    PRIORITY_BASED = "priority_based"

class RoutingEngine:
    """Routes escalated tickets to appropriate human agents"""
    
    def __init__(self, redis_client, postgres_conn):
        self.redis = redis_client
        self.pg_conn = postgres_conn
        self._ensure_routing_tables()
    
    def _ensure_routing_tables(self):
        """Create routing configuration tables"""
        try:
            with self.pg_conn.cursor() as cursor:
                # Agents table (future: populated from CRM/workforce management)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS handoff_agents (
                        id SERIAL PRIMARY KEY,
                        tenant_id VARCHAR(255) NOT NULL,
                        agent_id VARCHAR(255) NOT NULL,
                        agent_name VARCHAR(255) NOT NULL,
                        agent_email VARCHAR(255),
                        skills JSONB DEFAULT '[]',
                        max_concurrent INT DEFAULT 5,
                        is_available BOOLEAN DEFAULT TRUE,
                        priority_tier INT DEFAULT 1,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(tenant_id, agent_id)
                    );
                """)
                
                # Routing rules table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS handoff_routing_rules (
                        id SERIAL PRIMARY KEY,
                        tenant_id VARCHAR(255) NOT NULL,
                        rule_name VARCHAR(255) NOT NULL,
                        conditions JSONB NOT NULL,
                        routing_strategy VARCHAR(50) NOT NULL,
                        target_agents JSONB,
                        priority INT DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                
                self.pg_conn.commit()
        except Exception as e:
            logger.error(f"Failed to create routing tables: {e}")
    
    def route_ticket(
        self,
        tenant_id: str,
        ticket_id: str,
        priority: str,
        escalation_reason: str,
        risk_categories: List[str],
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Route ticket to appropriate agent"""
        
        # Get routing rules for tenant
        routing_rule = self._get_matching_rule(tenant_id, priority, risk_categories, escalation_reason)
        
        if routing_rule:
            strategy = routing_rule.get("routing_strategy", "round_robin")
            target_agents = routing_rule.get("target_agents", [])
        else:
            # Default strategy
            strategy = "least_loaded"
            target_agents = []
        
        # Select agent based on strategy
        selected_agent = self._select_agent(
            tenant_id,
            strategy,
            target_agents,
            priority,
            risk_categories
        )
        
        if selected_agent:
            # Track assignment in Redis
            assignment_key = f"handoff:assignment:{tenant_id}:{selected_agent['agent_id']}"
            self.redis.hincrby(assignment_key, "current_load", 1)
            self.redis.expire(assignment_key, 3600)
            
            logger.info(f"Routed ticket {ticket_id} to agent {selected_agent['agent_id']}")
            
            return {
                "agent_id": selected_agent["agent_id"],
                "agent_name": selected_agent["agent_name"],
                "agent_email": selected_agent.get("agent_email"),
                "routing_strategy": strategy,
                "routing_reason": f"Matched rule: {routing_rule.get('rule_name', 'default')}" if routing_rule else "default_routing"
            }
        
        # Fallback: return generic assignment
        return {
            "agent_id": "support_team",
            "agent_name": "Support Team",
            "agent_email": None,
            "routing_strategy": "fallback",
            "routing_reason": "No available agents, using team queue"
        }
    
    def _get_matching_rule(
        self,
        tenant_id: str,
        priority: str,
        risk_categories: List[str],
        escalation_reason: str
    ) -> Optional[Dict]:
        """Find matching routing rule"""
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM handoff_routing_rules
                    WHERE tenant_id = %s AND is_active = TRUE
                    ORDER BY priority DESC
                """, (tenant_id,))
                
                for row in cursor.fetchall():
                    conditions = row[3]  # conditions JSONB
                    
                    # Check if conditions match
                    if self._match_conditions(conditions, priority, risk_categories, escalation_reason):
                        return {
                            "rule_name": row[2],
                            "routing_strategy": row[4],
                            "target_agents": row[5]
                        }
            return None
        except Exception as e:
            logger.error(f"Failed to get routing rules: {e}")
            return None
    
    def _match_conditions(
        self,
        conditions: Dict,
        priority: str,
        risk_categories: List[str],
        escalation_reason: str
    ) -> bool:
        """Check if conditions match ticket attributes"""
        
        # Priority match
        if "priorities" in conditions:
            if priority not in conditions["priorities"]:
                return False
        
        # Risk category match
        if "risk_categories" in conditions:
            if not any(rc in risk_categories for rc in conditions["risk_categories"]):
                return False
        
        # Keyword match in escalation reason
        if "keywords" in conditions:
            reason_lower = escalation_reason.lower()
            if not any(kw.lower() in reason_lower for kw in conditions["keywords"]):
                return False
        
        return True
    
    def _select_agent(
        self,
        tenant_id: str,
        strategy: str,
        target_agents: List[str],
        priority: str,
        risk_categories: List[str]
    ) -> Optional[Dict]:
        """Select agent based on strategy"""
        
        # Get available agents
        agents = self._get_available_agents(tenant_id, target_agents)
        
        if not agents:
            return None
        
        if strategy == "round_robin":
            return self._round_robin_select(agents)
        elif strategy == "least_loaded":
            return self._least_loaded_select(agents)
        elif strategy == "skill_based":
            return self._skill_based_select(agents, risk_categories)
        elif strategy == "priority_based":
            return self._priority_based_select(agents, priority)
        else:
            return agents[0] if agents else None
    
    def _get_available_agents(self, tenant_id: str, target_agents: List[str]) -> List[Dict]:
        """Get list of available agents"""
        try:
            with self.pg_conn.cursor() as cursor:
                if target_agents:
                    cursor.execute("""
                        SELECT * FROM handoff_agents
                        WHERE tenant_id = %s AND agent_id = ANY(%s) AND is_available = TRUE
                    """, (tenant_id, target_agents))
                else:
                    cursor.execute("""
                        SELECT * FROM handoff_agents
                        WHERE tenant_id = %s AND is_available = TRUE
                    """, (tenant_id,))
                
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get available agents: {e}")
            return []
    
    def _round_robin_select(self, agents: List[Dict]) -> Dict:
        """Round-robin selection"""
        # Simple implementation: could use Redis counter for true round-robin
        return random.choice(agents)
    
    def _least_loaded_select(self, agents: List[Dict]) -> Dict:
        """Select agent with least current load"""
        agent_loads = []
        
        for agent in agents:
            load_key = f"handoff:assignment:{agent['tenant_id']}:{agent['agent_id']}"
            current_load = int(self.redis.hget(load_key, "current_load") or 0)
            max_concurrent = agent.get("max_concurrent", 5)
            
            if current_load < max_concurrent:
                agent_loads.append((agent, current_load))
        
        if agent_loads:
            # Return agent with minimum load
            return min(agent_loads, key=lambda x: x[1])[0]
        
        return agents[0]
    
    def _skill_based_select(self, agents: List[Dict], risk_categories: List[str]) -> Dict:
        """Select agent based on skill match"""
        scored_agents = []
        
        for agent in agents:
            skills = agent.get("skills", [])
            match_score = len(set(skills) & set(risk_categories))
            scored_agents.append((agent, match_score))
        
        if scored_agents:
            return max(scored_agents, key=lambda x: x[1])[0]
        
        return agents[0]
    
    def _priority_based_select(self, agents: List[Dict], priority: str) -> Dict:
        """Select agent based on priority tier"""
        priority_map = {"critical": 1, "high": 1, "medium": 2, "low": 3}
        required_tier = priority_map.get(priority, 2)
        
        eligible = [a for a in agents if a.get("priority_tier", 1) <= required_tier]
        return eligible[0] if eligible else agents[0]
