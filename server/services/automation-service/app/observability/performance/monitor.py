"""
Observability - Performance Monitoring
=======================================
Enterprise performance tracking and analysis.
"""
import time
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
from datetime import datetime

class PerformanceMonitor:
    """Performance monitoring and profiling"""
    
    def __init__(self):
        self.layer_timings: Dict[str, List[float]] = {}
        self.operation_timings: Dict[str, List[float]] = {}
    
    def record_layer_timing(self, layer: str, duration_ms: float):
        """Record layer execution timing"""
        if layer not in self.layer_timings:
            self.layer_timings[layer] = []
        self.layer_timings[layer].append(duration_ms)
    
    def record_operation_timing(self, operation: str, duration_ms: float):
        """Record operation timing"""
        if operation not in self.operation_timings:
            self.operation_timings[operation] = []
        self.operation_timings[operation].append(duration_ms)
    
    @asynccontextmanager
    async def track_performance(self, operation: str):
        """Track operation performance"""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.record_operation_timing(operation, duration_ms)
    
    def get_layer_stats(self, layer: str) -> Dict[str, float]:
        """Get layer performance statistics"""
        if layer not in self.layer_timings:
            return {}
        
        timings = self.layer_timings[layer]
        return {
            "count": len(timings),
            "avg_ms": sum(timings) / len(timings),
            "min_ms": min(timings),
            "max_ms": max(timings),
            "p95_ms": sorted(timings)[int(len(timings) * 0.95)] if len(timings) > 0 else 0
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get all performance statistics"""
        return {
            layer: self.get_layer_stats(layer)
            for layer in self.layer_timings.keys()
        }

# Global performance monitor
performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor"""
    return performance_monitor

__all__ = ["PerformanceMonitor", "performance_monitor", "get_performance_monitor"]
