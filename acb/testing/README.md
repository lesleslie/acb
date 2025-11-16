> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Testing](./README.md) | [Workflows](../workflows/README.md) | [Services](../services/README.md)

# ACB: Testing

ACB's testing layer packages fixtures, async utilities, and provider discovery so
projects can exercise adapters, services, and workflows with realistic mocks and
metrics.

## Table of Contents

- [Overview](#overview)
- [Key Capabilities](#key-capabilities)
- [Module Reference](#module-reference)
- [Provider Ecosystem](#provider-ecosystem)
- [Usage Patterns](#usage-patterns)
- [Extending the Layer](#extending-the-layer)
- [Related Resources](#related-resources)

## Overview

The testing layer supplies batteries-included pytest fixtures, utilities, and
performance helpers that mirror production behavior. Everything is wired into
the dependency injection container, keeping lifecycle hooks and cleanup
routines aligned with runtime services.

## Key Capabilities

- Async-aware helpers for orchestrating background tasks, timeouts, and cleanup
- Deterministic adapter, service, and action mocks with configurable behavior
- Registry initializers that isolate discovery state between test sessions
- Performance timers, load generators, and metrics collectors for regression checks
- Seamless overrides for configuration and settings objects delivered via `depends`

## Module Reference

- `async_helpers.py`: Async test case base class, timeout guards, and lifecycle tools
- `discovery.py`: Test provider registry, metadata helpers, and enable/disable APIs
- `fixtures.py`: Pytest fixtures for config, registries, and reusable adapter/service mocks
- `performance.py`: Benchmark utilities, load runners, and assertion helpers
- `providers/`: Ready-to-use provider implementations (see `providers/README.md`)
- `utils.py`: Interface assertions, DI-friendly factories, and suite orchestration

## Provider Ecosystem

`acb.testing.providers` ships drop-in providers that register realistic mocks,
database fixtures, security probes, and integration harnesses. Discovery helpers
such as `list_test_providers()`, `apply_test_provider_overrides()`, and
`generate_test_provider_id()` make it easy to introspect available providers or
swap behaviors on demand.

## Usage Patterns

```python
import pytest
from acb.testing import PerformanceTimer


@pytest.mark.asyncio
async def test_handles_cache_miss(acb_service_mocks):
    performance = acb_service_mocks["performance"]

    async with PerformanceTimer() as timer:
        await performance.optimize("cache-miss")

    assert timer.elapsed < 0.050
```

Combine the built-in fixtures with test providers when you need richer behavior:

```python
import pytest
from acb.testing.providers import MockServiceProvider


@pytest.mark.asyncio
async def test_validation_contract():
    provider = MockServiceProvider()
    validation = provider.create_validation_service_mock({"error_rate": 0.0})

    result = await validation.validate({"payload": "ok"})
    assert result["valid"] is True
```

## Extending the Layer

- Create custom providers with the metadata template in `discovery.py`
- Register overrides via `apply_test_provider_overrides()` to tailor behavior per test
- Export project-specific fixtures that compose the shared helpers in this package
- Reuse `setup_test_environment()` and `teardown_test_environment()` for integration suites

## Related Resources

- [Test Providers](./providers/README.md)
- [Services Layer](../services/README.md)
- [Workflows Engine](../workflows/README.md)
- [Project Overview](../../README.md)
