# Adapter Guide

This document outlines how adapters are structured, configured, and consumed inside ACB.

## Adapter Architecture

- **Category-based discovery**: Each adapter lives under `acb/adapters/<category>/<implementation>.py`. The framework registers every implementation automatically during import time.
- **Adapter metadata**: Implementations provide metadata (category, name, capabilities) that lets higher layers discover them by category or by feature.
- **Standard entrypoint**: Use `acb.adapters.import_adapter("category")` to pull in the implementation declared in your settings, and call `depends.get()` or `depends.inject` to obtain the adapter instance.
- **Configuration first**: `settings/adapters.yaml` controls which implementation is active for each category. Each implementation reads its own `settings/<category>.yaml` file for tuning options.

## Configuration Workflow

1. **Select the adapter**: Add an entry such as `cache: redis` to `settings/adapters.yaml`.
1. **Tune the implementation**: Supply adapter-specific options inside `settings/cache.yaml` (or whichever category you selected).
1. **Register secrets**: Place sensitive values (passwords, API keys) under `settings/secrets/` or provision them through your configured secret manager.
1. **Utilize via DI**: The adapter becomes available through `depends.get(Cache)` (or via `@depends.inject`), keeping your consumer code implementation-agnostic.

Some adapters expose extra helpers for health checks, retry policies, and caching that you can wire once after acquiring the instance.

## Common Adapter Categories

| Category | Purpose | Typical Implementations |
| --- | --- | --- |
| `cache` | Fast in-memory or distributed caches | memory, redis |
| `sql` | Relational databases | sqlite, postgresql, mysql |
| `nosql` | Document/column stores | firestore, mongodb, redis |
| `storage` | Object/file storage | file, s3, gcs, azure |
| `monitoring` | Observability | sentry, logfire |
| `queue` | Background/job queues | memory, rabbitmq, apscheduler |
| `templates` | Async HTML rendering | jinja2 |
| `secret` | Secret management | infisical, secret_manager |

For the full list of supported adapter categories, inspect `acb/adapters/` or `docs/CONFIGURATION.md`.

## Adapter Best Practices

- Keep consumer code high-level by depending on adapter protocols defined in `_base.py` files.
- Register adapters once via `acb.depends.depends.set()` if you need manual wiring (e.g., in CLI scripts).
- Favor async entrypoints; most adapters expose `async init()` methods and async helpers.
- Use `settings/adapters.yaml` and the category YAML files to propagate configuration to loads, retry settings, secrets, and feature toggles.

## Troubleshooting

- If an adapter fails to load, verify `settings/adapters.yaml` points at a supported implementation and that any required `settings/<category>.yaml` file exists.
- Use `acb.adapters.import_adapter()` with `depends.get()` in a REPL to inspect available categories and implementations.
- Refer to each adapter’s README (e.g., `acb/adapters/sql/README.md`) for category-specific setup notes and diagnostics.
