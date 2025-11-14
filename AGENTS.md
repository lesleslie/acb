# Repository Guidelines

## Project Structure & Module Organization

Production code lives under `acb/`, grouped by concern: `acb/actions/` (orchestration), `acb/adapters/` (IO bridges), `acb/core/` (shared primitives), and `acb/services/` (transport helpers). Runtime composition is handled in `config.py`, `depends.py`, and `context.py`—reference `CONFIGURATION.md` before touching them. Tests mirror the tree in `tests/`, docs sit in `docs/`, runnable examples in `examples/`, and generated artifacts under `build/` (never edit generated files).

## Build, Test, and Development Commands

- `uv sync --group dev` – install the pinned Python 3.13 toolchain plus dev dependencies into `.venv/`.
- `uv run ruff format` / `uv run ruff check` – format and lint the codebase.
- `uv run pyright` – run strict static typing across `acb/` and `tests/`.
- `uv run pytest --cov=acb --cov-fail-under=42` – execute the full suite with coverage gate; narrow scope with `-m` or `-k` while iterating.
- `python -m crackerjack` – run the curated quality workflow (zuban, complexipy, refurb, etc.) before submitting.

## Coding Style & Naming Conventions

Use Python 3.13 with Ruff’s 88-character limit. Prefer single quotes, sorted imports, and type hints everywhere. Modules stay `snake_case`, public classes use `PascalCase`, async helpers end with `_async`, and factories begin with `build_`. Rely on `ruff` and `pyright` to catch formatting or typing drift instead of manual tweaks.

## Testing Guidelines

Place unit tests beside their subjects (`tests/<package>/test_*.py`). Reuse fixtures such as `mock_config`, `mock_async_file_system`, and adapter patches to avoid real IO. Keep coverage above the enforced 42%; add targeted cases when introducing adapters or background workers. Run `uv run pytest -m "unit"` or `uv run pytest -k adapter` for focused feedback.

## Commit & Pull Request Guidelines

Follow Conventional Commits (e.g., `fix(cache): handle ttl drift`). PRs should explain intent, reference related issues, note configuration changes, and attach CLI output or screenshots when behavior shifts. Verify formatting (`ruff format`), linting (`ruff check`), typing (`pyright`), tests (`pytest`), and the quality workflow (`python -m crackerjack`) before requesting review.

## Security & Configuration Tips

Load secrets through adapter hooks in `acb/config.py`; never hardcode credentials. Favor TLS-ready settings, validate external hosts via helpers in `acb/adapters/`, and document environment tweaks in the relevant README. When integrating new services, ensure cleanup paths use `CleanupMixin` and type-safe dependency injection (`depends.get_sync` or `await depends.get`) to avoid runtime leaks.
