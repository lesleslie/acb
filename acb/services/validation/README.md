> **ACB Documentation**: [Main](../../../README.md) | [Services](../README.md) | [Validation Services](./README.md)

# ACB Services: Validation

The validation package offers schema validation, sanitization, and contract
enforcement built on top of the services layer.

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Decorators & Shortcuts](#decorators--shortcuts)
- [Usage Patterns](#usage-patterns)
- [Performance & Metrics](#performance--metrics)
- [Related Resources](#related-resources)

## Overview

Validation services guard inputs and outputs with high-performance checks,
security-focused sanitization, and comprehensive metrics. They integrate tightly
with dependency injection, service discovery, and adapters like `models`.

## Core Components

- `ValidationService`: ServiceBase implementation handling schema compilation, sanitization, and metrics
- `ValidationSettings` / `ValidationConfig`: Control default levels, sanitization options, performance thresholds, and adapter integration
- `ValidationSchema` / `ValidationRegistry`: Register reusable schemas from dicts, callables, or adapter-backed models
- `ValidationResult` / `ValidationReport`: Rich result objects with timing data, coercions, and aggregated errors
- `ValidationLevel`: Enumerates relaxed vs. strict validation modes to match workload requirements

## Decorators & Shortcuts

- `validate_input`, `validate_output`, and `validate_contracts` wrap functions with automatic validation and coercion
- `sanitize_input` provides HTML/JS-safe sanitization for untrusted payloads
- Decorators detect async vs. sync callables and route through `ValidationService` transparently via `depends`

## Usage Patterns

```python
from typing import Any

from acb.services.validation import (
    ValidationConfig,
    ValidationLevel,
    ValidationService,
    ValidationSettings,
    validate_input,
)

validation = ValidationService(
    validation_settings=ValidationSettings(
        default_validation_level=ValidationLevel.STRICT,
    ),
)


async def main() -> None:
    async with validation:
        result = await validation.validate({"email": "ops@example.com"})
        assert result.is_valid


@validate_input(
    schema={"payload": {"type": "object"}},
    config=ValidationConfig(level=ValidationLevel.STRICT),
)
async def handle_event(payload: dict[str, Any]) -> dict[str, Any]:
    return payload
```

## Performance & Metrics

- Validation timings are captured per call; monitor `validation_time_ms` on `ValidationResult`
- Enable `enable_performance_monitoring` in settings to emit warnings when thresholds are breached
- Health checks verify schema registry population, models adapter availability, and throughput metrics

## Related Resources

- [Services Layer](../README.md)
- [Repository Services](../repository/README.md)
- [Performance Services](../performance/README.md)
- [Main Documentation](../../../README.md)
