> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Logger](./README.md)

# Logger Adapter

> **Configuration**
> Choose the `logger` implementation in `settings/adapters.yaml` and tune it via `settings/logger.yaml`. Store secrets in `settings/secrets/` or via a secret manager so they never reach git.

The Logger adapter abstracts structured logging for ACB services. It unifies
formatter defaults, context propagation, correlation IDs, and remote sinks while
allowing teams to swap between Loguru, Structlog, or custom logging targets
without rewriting application code.

## Table of Contents

- [Overview](#overview)
- [Settings](#settings)
- [Protocol & Base Class](#protocol--base-class)
- [Context Management](#context-management)
- [Built-in Implementations](#built-in-implementations)
- [Usage Examples](#usage-examples)
- [Remote Sink Example](#remote-sink-example)
- [Best Practices](#best-practices)
- [Related Adapters](#related-adapters)

## Overview

Adapters implement `LoggerBase`, inheriting lifecycle hooks from `CleanupMixin`
and gaining access to ACB configuration via dependency injection. The shared
settings class ensures consistent log levels, formatting, JSON output, and file
rotation semantics across implementations.

## Settings

`LoggerBaseSettings` controls:

- Log levels for development vs. deployed environments (`log_level`,
  `deployed_level`) and module-specific overrides (`level_per_module`).
- Text/HTML formatter fragments, structured metadata toggles, and serializer
  configuration for JSON logging.
- File output options (`log_file_path`, rotation, retention, compression).
- Remote transport parameters (`remote_endpoint`, `remote_api_key`,
  batch/flush intervals) for log shipping.
- Async behavior (enqueue logging, contextvars) and correlation ID header names.

These settings are surfaced through `settings/adapters.yaml` to keep production
and local environments aligned.

## Protocol & Base Class

- `LoggerProtocol` defines the callable surface (`debug`, `info`, `warning`,
  `error`, `critical`) plus structured methods (`log_structured`, `bind`,
  `with_context`, `with_correlation_id`).
- `LoggerBase` implements public methods that delegate to protected hooks
  (`_debug`, `_info`, etc.), ensuring consistent lifecycle and cleanup.
- Adapters call `init()` to perform one-time setup (sink registration, handler
  configuration) before logging begins.

## Context Management

- `bind(**context)` augments log entries with static key/value pairs.
- `with_context()` returns a derived logger preloaded with extra metadata.
- `with_correlation_id()` standardizes trace identifiers across HTTP handlers,
  background tasks, and messaging flows.

## Built-in Implementations

| Module | Backend | Highlights |
| ------ | ------- | ---------- |
| `loguru` | [Loguru](https://github.com/Delgan/loguru) | Rich formatting, async-friendly sinks, easy rotation. |
| `structlog` | [Structlog](https://www.structlog.org/) | JSON/structured output, processor pipeline support. |
| `logly` | Example HTTP/remote sink | Demonstrates remote batching and API-key authentication. |

Each adapter declares `MODULE_METADATA` so discovery can expose capabilities and
health checks to the rest of the system.

## Usage Examples

```python
from acb.adapters import import_adapter
from acb.depends import depends

LoggerAdapter = import_adapter("logger")


async def report_metrics(metrics: dict[str, object]) -> None:
    logger = await depends.get(LoggerAdapter)
    logger = logger.with_correlation_id(metrics["request_id"])
    logger = logger.with_context(**metrics)
    logger.info("Collected metrics")
```

To record structured events:

```python
async def log_order_processed(payload) -> None:
    logger = await depends.get(LoggerAdapter)
    logger.log_structured(
        level="info",
        msg="order_processed",
        order_id=payload.order_id,
        items=len(payload.items),
        duration_ms=payload.duration_ms,
    )
```

## Remote Sink Example

```python
from pydantic import SecretStr


async def configure_remote_logging() -> None:
    logger = await depends.get(LoggerAdapter)
    logger.settings.remote_endpoint = "https://logs.example.com/ingest"
    logger.settings.remote_api_key = SecretStr("token")
    logger.settings.remote_flush_interval = 1.0
    logger.init()
```

This configuration forwards logs to a remote collector while preserving the
shared formatting and context propagation defined in `LoggerBaseSettings`.

## Best Practices

- Prefer structured logging (`log_structured`) for events consumed by analytics
  systems or SIEM pipelines.
- Keep `serialize` off locally for readability; enable JSON output in staging and
  production environments.
- Use module-level overrides to reduce noise from verbose third-party packages.
- Configure `remote_endpoint` with TLS and API keys when streaming logs to a
  centralized service.
- Always call `init()` once during service startup to ensure sinks are ready.

## Related Adapters

- [Monitoring](../monitoring/README.md)
- [Requests](../requests/README.md)
- [Messaging](../messaging/README.md)
