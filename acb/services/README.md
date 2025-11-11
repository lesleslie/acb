> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Services](./README.md) | [Workflows](../workflows/README.md) | [Testing](../testing/README.md)

# ACB: Services

The services layer defines the runtime backbone for long-lived components that
coordinate adapters, workflows, and background tasks across an ACB deployment.

## Table of Contents

- [Overview](#overview)
- [Core Building Blocks](#core-building-blocks)
- [Lifecycle & Discovery](#lifecycle--discovery)
- [Featured Subpackages](#featured-subpackages)
- [Usage Patterns](#usage-patterns)
- [Best Practices](#best-practices)
- [Related Resources](#related-resources)

## Overview

Services wrap complex capabilities (validation, repository coordination,
performance optimization, etc.) with lifecycle management, dependency
injection, health checks, and metrics.

## Core Building Blocks

- `ServiceBase`: Async lifecycle, metrics, health checks, and cleanup via `CleanupMixin`
- `ServiceConfig`: Declares service identity, dependencies, priority, and metadata
- `ServiceSettings`: Runtime knobs for timeouts, retries, and health intervals
- `ServiceMetrics`: Tracks requests handled, errors, and custom counters
- `ServiceStatus`: Enum describing lifecycle transitions (inactive → active → stopped)

## Lifecycle & Discovery

- Services call `initialize()` / `shutdown()` to manage resources safely
- `health_check()` feeds readiness probes with status, metrics, and custom data
- Discovery helpers (`import_service`, `register_services`, `get_service_descriptor`)
  load implementations dynamically with metadata (`ServiceMetadata`)
- `ServiceRegistry` coordinates registration, dependency checks, and scoped access

## Featured Subpackages

- [Performance](./performance/README.md): Optimizers, metrics, and serverless helpers
- [Repository](./repository/README.md): Repository pattern, registry, and unit of work
- [Validation](./validation/README.md): Schema validation, sanitization, and contracts

## Usage Patterns

```python
from acb.adapters import import_adapter
from acb.depends import depends
from acb.services import ServiceBase, ServiceConfig, ServiceSettings


class ReportService(ServiceBase):
    def __init__(self) -> None:
        super().__init__(
            service_config=ServiceConfig(
                service_id="reports",
                name="ReportService",
                description="Generates analytical reports",
                dependencies=["cache"],
            ),
            settings=ServiceSettings(timeout=30.0, retry_attempts=2),
        )
        self._cache = None

    async def _initialize(self) -> None:
        Cache = import_adapter("cache")
        self._cache = await depends.get(Cache)

    async def _shutdown(self) -> None:
        self._cache = None

    async def generate(self, report_id: str) -> dict[str, object]:
        self.increment_requests()
        if self._cache:
            cached = await self._cache.get(report_id)
            if cached:
                return cached
        data = {"report_id": report_id, "status": "generated"}
        if self._cache:
            await self._cache.set(report_id, data, ttl=3600)
        return data


async def main() -> None:
    async with ReportService() as service:
        await service.generate("daily")
```

## Best Practices

- Declare dependencies in `ServiceConfig.dependencies` so discovery validates startup order
- Use `async with` or explicit `initialize()`/`shutdown()` to keep resources tidy
- Record custom metrics with `set_custom_metric()` for observability dashboards
- Pair services with `acb.services.health` and `acb.services.state` when exposing status or persisting state

## Related Resources

- [Performance Services](./performance/README.md)
- [Repository Services](./repository/README.md)
- [Validation Services](./validation/README.md)
- [Main Documentation](../../README.md)
