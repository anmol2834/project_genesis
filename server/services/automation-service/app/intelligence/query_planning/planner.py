"""
Query Planning Engine
=====================
Decides retrieval strategy based on intent, entities, and memory context.

Performance: <10ms target
"""

import logging
from typing import Optional, Any, Dict
from app.intelligence.models.intelligence_result import (
    QueryPlan, RetrievalStrategy, ContinuationResolution
)

logger = logging.getLogger(__name__)


class QueryPlanner:
    """
    Intelligent retrieval strategy planner.
    Decides which retrieval approach to use based on query characteristics.
    """
    
    def plan(
        self,
        qu_result: Any,
        memory: Optional[Any],
        memory_context: Optional[Dict],
        continuation: ContinuationResolution
    ) -> QueryPlan:
        """
        Plan retrieval strategy.
        
        Strategy Selection:
        - EXACT_MATCH: Product name present ("AeroCam X1 price")
        - HYBRID: Specific features ("4k camera drone")
        - SEMANTIC: Use case driven ("best for crop monitoring")
        - CACHED: Continuation with memory
        - HIERARCHICAL: Default L1-L7
        - SKIP: No retrieval needed (greeting, acknowledgment)
        
        Args:
            qu_result: Query understanding result
            memory: Thread memory
            memory_context: Enriched memory context
            continuation: Continuation resolution
            
        Returns:
            QueryPlan with strategy and execution details
        """
        
        # ── SKIP retrieval cases ──────────────────────────────────────────
        if qu_result.intent.value in ["casual", "unknown"]:
            return QueryPlan(
                retrieval_strategy=RetrievalStrategy.SKIP,
                confidence=0.9,
                memory_dependency="none",
                needs_new_retrieval=False,
                stages=["skip"],
                cache_reusable=False,
                expected_result_count=0,
                skip_reranking=True,
                skip_embedding=True,
                plan_confidence=0.9
            )
        
        # ── EXACT MATCH strategy ──────────────────────────────────────────
        has_exact_product = self._has_exact_product_name(qu_result)
        
        if has_exact_product:
            return QueryPlan(
                retrieval_strategy=RetrievalStrategy.EXACT_MATCH,
                confidence=0.95,
                memory_dependency="low",
                needs_new_retrieval=True,
                stages=["exact", "filter"],
                secondary_queries=[],
                cache_reusable=True,
                cache_key=self._build_cache_key(qu_result, "exact"),
                expected_chunk_types=["product", "pricing", "specifications"],
                expected_result_count=3,
                min_score_threshold=0.9,
                skip_reranking=True,
                use_exact_match_only=True,
                estimated_latency_ms=50,
                plan_confidence=0.95
            )
        
        # ── CACHED strategy (continuation) ────────────────────────────────
        if continuation.resolved and continuation.confidence > 0.7:
            cached_entities = []
            if continuation.resolved_entity:
                cached_entities.append(continuation.resolved_entity)
            
            return QueryPlan(
                retrieval_strategy=RetrievalStrategy.CACHED,
                confidence=continuation.confidence,
                memory_dependency="high",
                needs_new_retrieval=False,
                stages=["cache_lookup"],
                cache_reusable=True,
                cached_entities_reusable=cached_entities,
                expected_chunk_types=["product", "pricing"],
                expected_result_count=3,
                skip_reranking=True,
                skip_embedding=True,
                estimated_latency_ms=5,
                plan_confidence=continuation.confidence
            )
        
        # ── HYBRID strategy (specific features) ───────────────────────────
        has_specific_features = self._has_specific_features(qu_result)
        
        if has_specific_features:
            return QueryPlan(
                retrieval_strategy=RetrievalStrategy.HYBRID,
                confidence=0.85,
                memory_dependency="medium",
                needs_new_retrieval=True,
                stages=["exact", "semantic", "rerank"],
                secondary_queries=self._build_secondary_queries(qu_result),
                cache_reusable=True,
                cache_key=self._build_cache_key(qu_result, "hybrid"),
                expected_chunk_types=["product", "feature", "comparison"],
                expected_result_count=5,
                min_score_threshold=0.75,
                skip_reranking=False,
                estimated_latency_ms=200,
                plan_confidence=0.85
            )
        
        # ── SEMANTIC strategy (use case driven) ───────────────────────────
        has_use_case = bool(qu_result.use_case or qu_result.user_goal)
        
        if has_use_case:
            return QueryPlan(
                retrieval_strategy=RetrievalStrategy.SEMANTIC,
                confidence=0.8,
                memory_dependency="medium",
                needs_new_retrieval=True,
                stages=["semantic", "rerank", "filter"],
                secondary_queries=self._build_use_case_queries(qu_result),
                cache_reusable=True,
                cache_key=self._build_cache_key(qu_result, "semantic"),
                expected_chunk_types=["use_case", "product", "recommendation"],
                expected_result_count=7,
                min_score_threshold=0.7,
                skip_reranking=False,
                estimated_latency_ms=300,
                plan_confidence=0.8
            )
        
        # ── HIERARCHICAL strategy (default L1-L7) ─────────────────────────
        return QueryPlan(
            retrieval_strategy=RetrievalStrategy.HIERARCHICAL,
            confidence=0.75,
            memory_dependency="low",
            needs_new_retrieval=True,
            stages=["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
            secondary_queries=[],
            cache_reusable=False,
            expected_chunk_types=["product", "category", "general"],
            expected_result_count=5,
            min_score_threshold=0.7,
            skip_reranking=False,
            estimated_latency_ms=400,
            plan_confidence=0.75
        )
    
    # ══════════════════════════════════════════════════════════════════════
    # Private Helper Methods
    # ══════════════════════════════════════════════════════════════════════
    
    def _has_exact_product_name(self, qu_result: Any) -> bool:
        """Check if query has exact product name."""
        if not qu_result.entities:
            return False
        
        product_name = qu_result.entities.get("product_name", "")
        
        if not product_name:
            return False
        
        # Check if it's a real product name (not generic)
        generic_terms = {"drone", "camera", "product", "service", "item"}
        
        clean = product_name.lower().strip()
        
        if clean in generic_terms:
            return False
        
        # Check if contains model numbers or specific identifiers
        has_model = any(char.isdigit() for char in clean)
        has_uppercase = any(char.isupper() for char in product_name)
        
        if has_model or has_uppercase or len(clean.split()) > 1:
            return True
        
        return False
    
    def _has_specific_features(self, qu_result: Any) -> bool:
        """Check if query has specific feature requirements."""
        if not qu_result.entities:
            return False
        
        features = qu_result.entities.get("features", [])
        
        if features and len(features) > 0:
            return True
        
        # Check keywords for feature terms
        if qu_result.keywords:
            feature_keywords = {
                "4k", "hd", "battery", "range", "speed", "weight",
                "resolution", "sensor", "gps", "camera", "gimbal"
            }
            
            keywords_lower = [k.lower() for k in qu_result.keywords]
            
            if any(fk in keywords_lower for fk in feature_keywords):
                return True
        
        return False
    
    def _build_secondary_queries(self, qu_result: Any) -> list:
        """Build secondary queries for hybrid search."""
        queries = []
        
        # Add rewritten query
        if qu_result.rewritten_query:
            queries.append(qu_result.rewritten_query)
        
        # Add feature-focused query
        if qu_result.entities and "features" in qu_result.entities:
            features = qu_result.entities["features"]
            if features:
                feature_str = " ".join(features[:3])
                queries.append(f"products with {feature_str}")
        
        # Add category query
        if qu_result.entities and "category" in qu_result.entities:
            category = qu_result.entities["category"]
            if category:
                queries.append(f"{category} options")
        
        return queries[:3]  # Max 3 secondary queries
    
    def _build_use_case_queries(self, qu_result: Any) -> list:
        """Build queries for use case driven search."""
        queries = []
        
        if qu_result.use_case:
            queries.append(qu_result.use_case)
        
        if qu_result.user_goal:
            queries.append(qu_result.user_goal)
        
        if qu_result.rewritten_query:
            queries.append(qu_result.rewritten_query)
        
        return queries[:2]  # Max 2 for semantic
    
    def _build_cache_key(self, qu_result: Any, strategy: str) -> str:
        """Build cache key for query plan."""
        product = qu_result.entities.get("product_name", "") if qu_result.entities else ""
        category = qu_result.entities.get("category", "") if qu_result.entities else ""
        intent = qu_result.intent.value
        
        key_parts = [strategy, intent]
        
        if product:
            key_parts.append(product.lower().replace(" ", "_"))
        elif category:
            key_parts.append(category.lower().replace(" ", "_"))
        
        return ":".join(key_parts)
