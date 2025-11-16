> **ACB Documentation**: [Main](../../../README.md) | [Services](../README.md) | [Performance Services](./README.md)

# ACB Services: Performance

The performance package bundles caching, query, and serverless optimizations
that keep ACB applications responsive under load.

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Serverless Toolkit](#serverless-toolkit)
- [Usage Patterns](#usage-patterns)
- [Metrics & Observability](#metrics--observability)
- [Related Resources](#related-resources)

## Overview

Performance services provide drop-in helpers for latency reduction, caching, and
cold-start optimization. They rely on the services layer lifecycle, DI
integration, and registry metadata so you can compose optimizers alongside
other services.

## Core Components

- `PerformanceOptimizer`: ServiceBase implementation that coordinates cache,
  SQL, and background optimization loops
- `OptimizationConfig` / `PerformanceOptimizerSettings`: Fine-tune cache TTLs,
  batch sizes, compression, and background frequency
- `CacheOptimizer` / `QueryOptimizer`: Targeted helpers for wrapping expensive
  cache or database calls
- `PerformanceMetrics` / `MetricsCollector`: Typed metrics objects for surfacing
  timing, throughput, and resource data to monitoring backends
- `AdapterPreInitializer` / `FastDependencies`: Warm adapters and resolve DI
  dependencies just-in-time to keep throughput high

## Serverless Toolkit

Serverless workloads can reduce cold starts with the utilities exposed here:

- `ServerlessOptimizer` and `ServerlessOptimizerSettings` coordinate warmup
  routines and background refresh
- `lazy_resource()` and `LazyInitializer` defer construction until first access
  while still tracking lifecycles
- `optimize_cold_start()` and `ServerlessResourceCleanup` implement prefetch and
  teardown hooks for ephemeral environments

## Usage Patterns

```python
from acb.services.performance import (
    OptimizationConfig,
    PerformanceOptimizer,
    PerformanceOptimizerSettings,
)

settings = PerformanceOptimizerSettings(
    optimization_config=OptimizationConfig(cache_ttl_seconds=120),
    background_optimization=False,
)

optimizer = PerformanceOptimizer(settings=settings)


async def main() -> None:
    async with optimizer:

        async def load_report() -> dict[str, object]:
            # expensive call to a repository or external API
            return {"report_id": "weekly", "status": "ready"}

        result = await optimizer.optimize_cache_operation("reports:weekly", load_report)
        print(f"Cache hit after {result.duration_ms:.2f}ms: {result.success}")
```

## Metrics & Observability

- Invoke `MetricsCollector` to stream aggregated latency, cache hit rates, and throughput
- Store counters using `PerformanceOptimizer.set_custom_metric()` so they surface via the base service health checks
- Pair with `acb.services.health` to expose optimizer health in readiness probes

## Related Resources

- [Services Layer](../README.md)
- [Repository Services](../repository/README.md)
- [Validation Services](../validation/README.md)
- [Main Documentation](../../../README.md)
