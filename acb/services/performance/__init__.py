"""Performance optimization services for ACB.

This module provides performance optimization services that integrate
with FastBlocks and other performance-critical components.
"""

from .cache import CacheOptimizer
from .metrics import MetricsCollector, PerformanceMetrics
from .optimizer import OptimizationConfig, PerformanceOptimizer
from .query import QueryOptimizer
from .serverless import (
    AdapterPreInitializer,
    ColdStartMetrics,
    FastDependencies,
    LazyInitializer,
    ServerlessOptimizer,
    ServerlessOptimizerSettings,
    ServerlessResourceCleanup,
    lazy_resource,
    optimize_cold_start,
)

__all__ = [
    # Core optimization
    "PerformanceOptimizer",
    "OptimizationConfig",
    "MetricsCollector",
    "PerformanceMetrics",
    "CacheOptimizer",
    "QueryOptimizer",
    # Serverless optimization
    "ServerlessOptimizer",
    "ServerlessOptimizerSettings",
    "ColdStartMetrics",
    "LazyInitializer",
    "AdapterPreInitializer",
    "FastDependencies",
    "ServerlessResourceCleanup",
    # Utilities
    "lazy_resource",
    "optimize_cold_start",
]
