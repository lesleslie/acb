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
    "AdapterPreInitializer",
    "CacheOptimizer",
    "ColdStartMetrics",
    "FastDependencies",
    "LazyInitializer",
    "MetricsCollector",
    "OptimizationConfig",
    "PerformanceMetrics",
    # Core optimization
    "PerformanceOptimizer",
    "QueryOptimizer",
    # Serverless optimization
    "ServerlessOptimizer",
    "ServerlessOptimizerSettings",
    "ServerlessResourceCleanup",
    # Utilities
    "lazy_resource",
    "optimize_cold_start",
]
