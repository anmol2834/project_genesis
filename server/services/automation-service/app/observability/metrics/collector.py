"""
Observability - Metrics Collection System
==========================================
Enterprise metrics collection and aggregation.
"""
from typing import Dict, Optional, List
from datetime import datetime
from app.models.observability import (
    MetricPoint, RetrievalMetric, LLMMetric, 
    HallucinationMetric, ConfidenceMetric
)
from app.models.enums import MetricType

class MetricsCollector:
    """Centralized metrics collection"""
    
    def __init__(self):
        self.metrics: List[MetricPoint] = []
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
    
    def record_counter(
        self,
        name: str,
        value: float,
        user_id: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record counter metric"""
        metric = MetricPoint(
            metric_name=name,
            metric_type=MetricType.COUNTER,
            value=value,
            user_id=user_id,
            tags=tags or {},
            timestamp=datetime.utcnow()
        )
        self.metrics.append(metric)
        self.counters[name] = self.counters.get(name, 0) + value
    
    def record_gauge(
        self,
        name: str,
        value: float,
        user_id: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record gauge metric"""
        metric = MetricPoint(
            metric_name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            user_id=user_id,
            tags=tags or {},
            timestamp=datetime.utcnow()
        )
        self.metrics.append(metric)
        self.gauges[name] = value
    
    def record_histogram(
        self,
        name: str,
        value: float,
        user_id: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record histogram metric"""
        metric = MetricPoint(
            metric_name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            user_id=user_id,
            tags=tags or {},
            unit="ms",
            timestamp=datetime.utcnow()
        )
        self.metrics.append(metric)
    
    def record_retrieval_metrics(self, metric: RetrievalMetric):
        """Record retrieval-specific metrics"""
        self.record_histogram("retrieval.latency", metric.total_latency_ms, metric.user_id)
        self.record_counter("retrieval.cache_hits" if metric.cache_hit else "retrieval.cache_misses", 1, metric.user_id)
        self.record_counter("retrieval.chunks_retrieved", metric.chunks_retrieved, metric.user_id)
    
    def record_llm_metrics(self, metric: LLMMetric):
        """Record LLM generation metrics"""
        self.record_histogram("llm.generation_latency", metric.generation_latency_ms, metric.user_id)
        self.record_counter("llm.tokens_used", metric.tokens_used, metric.user_id, tags={"model": metric.model})
        self.record_gauge("llm.confidence", metric.confidence, metric.user_id)
    
    def record_hallucination_metrics(self, metric: HallucinationMetric):
        """Record hallucination detection metrics"""
        self.record_counter("hallucination.detected" if metric.detected else "hallucination.clean", 1, metric.user_id)
        if metric.detected:
            self.record_counter("hallucination.claims", metric.claims_count, metric.user_id)
    
    def record_confidence_metrics(self, metric: ConfidenceMetric):
        """Record confidence scoring metrics"""
        self.record_gauge("confidence.final", metric.final_confidence, metric.user_id)
        self.record_gauge("confidence.retrieval", metric.retrieval_confidence, metric.user_id)
        self.record_gauge("confidence.llm", metric.llm_confidence, metric.user_id)
    
    def get_metric_summary(self) -> Dict[str, any]:
        """Get metrics summary"""
        return {
            "total_metrics": len(self.metrics),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges)
        }

# Global metrics collector
metrics_collector = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector"""
    return metrics_collector

__all__ = ["MetricsCollector", "metrics_collector", "get_metrics_collector"]
