# Testing

This guide covers how to run, focus, and validate tests for ACB.

## Setup

- Install toolchain and dev deps:
  - `uv sync --extra dev`

## Commands

- Format and lint:
  - `uv run ruff format`
  - `uv run ruff check`
- Type checking:
  - `uv run pyright`
- Run tests with coverage gate (42%):
  - `uv run pytest --cov=acb --cov-fail-under=42`
- Focused runs:
  - By marker: `uv run pytest -m "unit"`
  - By keyword: `uv run pytest -k adapter`

## Coverage Policy

- Minimum coverage enforced: 42% (via `--cov-fail-under=42`).
- Keep unit tests targeted and fast; prefer integration tests in `tests/integration/`.

## Fixtures & Patterns

- Prefer existing fixtures to avoid real IO:
  - `mock_config`
  - `mock_async_file_system`
  - Adapter patches for external services
- Use dependency injection (`depends.get` or `await depends.get`) to obtain adapters
  and services under test to keep tests implementation‑agnostic.

## Tips

- Run `python -m crackerjack` before submitting for the curated quality workflow.
- When adding new adapters or background workers, add targeted tests alongside
  their modules under `tests/<package>/test_*.py`.
