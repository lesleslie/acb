---
id: 01K6EHYF5YF6K5257BX909PW0C
---
# Repository Guidelines

## Project Structure & Module Organization
- `acb/` holds production code; `actions/`, `adapters/`, `core/`, `services/`, and `gateway/` supply reusable primitives, IO bridges, orchestration, and transport helpers.
- Runtime glue lives in `config.py`, `depends.py`, and `context.py`; follow `CONFIGURATION.md` when wiring new packages or environment layers.
- Tests mirror the package under `tests/`; reference material stays in `docs/`, sample flows in `examples/`, and generated build outputs in `build/`—avoid hand-editing generated assets.

## Build, Test, and Development Commands
- `uv sync --extra dev` installs pinned tooling for Python 3.13 contributors.
- `uv run ruff format && uv run ruff check` keep code style and lint findings aligned with `pyproject.toml`.
- `uv run pyright` runs strict type analysis; address protocol warnings instead of suppressing them.
- `uv run pytest --cov=acb --cov-fail-under=42` executes the suite; add `-m "unit"` or `-k adapter` to focus, and prefer `python -m crackerjack -x -t -p <version> -c` before releasing.

## Coding Style & Naming Conventions
- Use Python 3.13 features (`|` unions, `match`, dataclass transforms) and favor async-friendly APIs.
- Ruff enforces 88-character lines, sorted imports without blank separators before first-party modules, and single-quote strings.
- Modules remain snake_case; public classes in PascalCase, async utilities end with `_async`, and factory helpers start with `build_`.

## Testing Guidelines
- Place tests beside their domain peers (e.g., `tests/adapters/cache/` against `acb/adapters/cache/`) using `test_*.py` filenames.
- Reuse fixtures from `tests/conftest.py`—`mock_config`, `mock_async_file_system`, and adapter patches block filesystem and network access.
- Mark slower suites with `@pytest.mark.integration` or `@pytest.mark.benchmark`; CI expectations center on unit coverage above the enforced threshold.

## Commit & Pull Request Guidelines
- Follow conventional commits (`fix(cache): handle ttl drift`) for clarity; maintainer `checkpoint:` messages remain automated.
- Keep branches focused and include reproduction notes, linked issues, and CLI captures or screenshots when behavior changes.
- Run the full formatter, type checker, and tests (or `python -m crackerjack -a <version>`) before opening a PR, and document configuration changes in the relevant README.

## Configuration & Security Notes
- Do not commit secrets; adapters load credentials via environment variables or secret backends described in `acb/config.py`.
- Prefer TLS-ready adapter settings and validate external endpoints with the DNS and monitoring helpers under `acb/adapters/`.
