# Repository Guidelines

## Project Structure & Module Organization

`acb/` houses production code, split into domain-focused packages such as `acb/actions/` for orchestration, `acb/adapters/` for IO bridges, `acb/core/` for reusable primitives, and `acb/services/` for transport helpers. Runtime composition lives in `config.py`, `depends.py`, and `context.py`; follow `CONFIGURATION.md` before touching them. Tests mirror the tree under `tests/`, while docs sit in `docs/`, sample flows in `examples/`, and generated artifacts in `build/`—never edit generated outputs by hand.

## Build, Test, and Development Commands

Run `uv sync --extra dev` to install the pinned Python 3.13 toolchain. `uv run ruff format` and `uv run ruff check` enforce formatting and lint rules; run both before committing. Use `uv run pyright` for strict type analysis, and `uv run pytest --cov=acb --cov-fail-under=42` for the full suite. Scope work with flags like `uv run pytest -m "unit"` or `-k adapter` during iteration.

## Coding Style & Naming Conventions

Write Python 3.13 code with Ruff’s 88-character limit, single quotes, and import sorting. Modules stay snake_case, public classes use PascalCase, async helpers end with `_async`, and factory helpers start with `build_`. Add concise comments only when behavior is non-obvious.

## Testing Guidelines

Unit tests live beside their subjects as `tests/<package>/test_*.py`. Reuse fixtures such as `mock_config`, `mock_async_file_system`, and adapter patches from `tests/conftest.py` to avoid real IO. Maintain coverage above the enforced 42%; add targeted cases when integrating new adapters or services.

## Commit & Pull Request Guidelines

Follow Conventional Commits (e.g., `fix(cache): handle ttl drift`). PRs should explain intent, reference issues, and attach CLI output or screenshots when behavior changes. Run formatting, linting, typing, and tests before requesting review.

## Security & Configuration Tips

Load secrets and endpoints through the adapter configuration hooks in `acb/config.py`; never hardcode credentials. Prefer TLS-ready settings, validate external hosts with helpers under `acb/adapters/`, and document environment tweaks in the relevant README.
