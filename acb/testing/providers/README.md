> **ACB Documentation**: [Main](<../../../README.md>) | [Testing](<../README.md>) | [Test Providers](<./README.md>)

# ACB Testing Providers

The providers package extends the testing layer with reusable factories that
produce realistic mocks, fixtures, and instrumentation for exercising actions,
adapters, services, and end-to-end integrations.

## Table of Contents

- [Overview](<#overview>)
- [Provider Catalog](<#provider-catalog>)
- [Working with Metadata](<#working-with-metadata>)
- [Usage Patterns](<#usage-patterns>)
- [Integration Tips](<#integration-tips>)
- [Related Resources](<#related-resources>)

## Overview

Each provider implements a focused testing capability and exposes a shared
`PROVIDER_METADATA` template so discovery can register, enable, and override
providers at runtime. Providers mirror production adapters and services while
adding hooks for fault injection, metrics, and resource cleanup.

## Provider Catalog

| Provider | Category | Highlights |
| --- | --- | --- |
| `MockAdapterProvider` | `mocking` | Cache, storage, SQL/NoSQL, and secret adapter mocks with latency, miss-rate, and error toggles |
| `MockServiceProvider` | `mocking` | Performance, health, validation, and repository service mocks with async behavior simulation |
| `MockActionProvider` | `mocking` | Compression, encoding, and hashing action doubles with configurable side effects |
| `DatabaseTestProvider` | `integration` | Ephemeral database fixtures, migration helpers, and dataset seeders |
| `IntegrationTestProvider` | `integration` | Cross-service orchestration, scenario runners, and environment setup helpers |
| `PerformanceTestProvider` | `performance` | Benchmark, load, and profiling runners with async/sync support |
| `SecurityTestProvider` | `security` | Threat simulations, credential rotation checks, and policy validation utilities |

## Working with Metadata

Every provider exports a `PROVIDER_METADATA` instance built from
`create_test_provider_metadata_template()`. Discovery helpers combine this
metadata with runtime status so you can:

- Generate stable IDs with `generate_test_provider_id()`
- Inspect capabilities via `TestProviderCapability` enums
- Toggle availability through `enable_test_provider()` / `disable_test_provider()`
- Fetch concrete classes using `get_test_provider_class(category, name)`

Use configuration overrides (`settings/testing.yaml`) or
`apply_test_provider_overrides()` when you want to swap implementations without
touching test code.

## Usage Patterns

```python
import pytest
from acb.testing.providers import MockAdapterProvider


@pytest.mark.asyncio
async def test_cache_round_trip():
    provider = MockAdapterProvider()
    cache = provider.create_cache_mock({"miss_rate": 0.0})

    await cache.set("user:1", {"id": 1})
    assert await cache.get("user:1") == {"id": 1}
```

Discovery APIs let you resolve providers dynamically:

```python
import pytest
from acb.testing import enable_test_provider, get_test_provider_class

enable_test_provider("mocking", "mock_service_provider")
MockServiceProvider = get_test_provider_class("mocking", "mock_service_provider")


@pytest.mark.asyncio
async def test_repository_service_contract():
    provider = MockServiceProvider()
    async with provider.mock_service_context("repository") as repository:
        repo = await repository.get_repository("orders")
        await repo.save({"id": 1, "status": "created"})
        order = await repo.find(1)
        assert order["status"] == "created"
```

## Integration Tips

- Combine providers with fixtures from `acb.testing.fixtures` to isolate discovery
  state between tests
- Store provider instances on the pytest `request` object to reset metrics after
  each test
- Leverage `TestProviderCapability` flags when filtering providers for targeted
  test modules or marks
- Wrap provider context managers in `pytest` fixtures to deliver scoped resources

## Related Resources

- [Testing Layer](<../README.md>)
- [Services Layer](<../../services/README.md>)
- [Workflow Engine](<../../workflows/README.md>)
- [Main Documentation](<../../../README.md>)
