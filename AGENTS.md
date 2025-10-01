---
id: 01K6F8HE4NPDKDTCG0JS2ADEEC
---
______________________________________________________________________

## id: 01K6F85P8X4BDMN0CEH5GGA03F

______________________________________________________________________

## id: 01K6F6ZEYRNHWF2W61TMV62G0J

______________________________________________________________________

## id: 01K6F6Y438AWKFTCT432Q4B0B6

______________________________________________________________________

## id: 01K6F0QDHXT266VCBCJ5SWWDTM

______________________________________________________________________

## id: 01K6F05YAAKJX0P6YDRT60FHBX

______________________________________________________________________

## id: 01K6EZZQCY1CXF5FDFMGMX7K3W

______________________________________________________________________

## id: 01K6EZZ2PPZ0YA184ZSMQSW6WD

______________________________________________________________________

## id: 01K6EZMV03KRHXAX95JQ92YHA7

______________________________________________________________________

## id: 01K6EZM0NP9SMC77PT2ESJE0T1

______________________________________________________________________

## id: 01K6EZ6PNW5RFP6SVDX7ATNFXM

______________________________________________________________________

## id: 01K6EZ62VCNKCV2P113NPD8YE3

______________________________________________________________________

## id: 01K6EZ13EPX6RT1MZE6JER0B13

______________________________________________________________________

## id: 01K6EZ06Z2BR5Y5QBN7G5REA45

______________________________________________________________________

## id: 01K6EYXYX690SP6GQNE337NT17

______________________________________________________________________

## id: 01K6EYX6TEP12ZQHSJ31Q1CZTS

______________________________________________________________________

## id: 01K6EXJR6DQNE6SP9EG8JBP5WY

______________________________________________________________________

## id: 01K6EXHQFRY4BC8CHAVKJBNEXM

______________________________________________________________________

## id: 01K6EXCMAXWP8J4Q2QD6KXJ1TJ

______________________________________________________________________

## id: 01K6EXBVMH2V9WCEJTJX3AQXAW

______________________________________________________________________

## id: 01K6EWFKG9AYR18YT4VFYG8GNT

______________________________________________________________________

## id: 01K6EWERKPQDRW0FJVYWZXB0GR

______________________________________________________________________

## id: 01K6ETPS8WBEWVWH0QCQSP1XYG

______________________________________________________________________

## id: 01K6ETP3E2CJS8KRQ2V0C266BQ

______________________________________________________________________

## id: 01K6ETJCE402EWTB8TW9SK41VK

______________________________________________________________________

## id: 01K6ETHMSWNJ4CVSQ74Z131YEY

______________________________________________________________________

## id: 01K6ESWMPAF69E4CWMQTZZ6MDT

______________________________________________________________________

## id: 01K6ESVZW341AMC4JWPC66PHYG

______________________________________________________________________

## id: 01K6ESP3TXD3G4TXNWC37DMWWK

______________________________________________________________________

## id: 01K6ESNEV8JB7YNV79G9XJWXZC

______________________________________________________________________

## id: 01K6ESM15J29NE23B2RYSPMRAS

______________________________________________________________________

## id: 01K6ESKAHCWWCKW2QM3FBA7FCQ

______________________________________________________________________

## id: 01K6ESHFZMV96JMAHYZ88MPYG4

______________________________________________________________________

## id: 01K6ESGWM5S8VKQJCY09ESRQX8

______________________________________________________________________

## id: 01K6EN5SHCHMJQWY67Q3ZSH30E

______________________________________________________________________

## id: 01K6EN50037T4KT8G4M9B7R0B7

______________________________________________________________________

## id: 01K6EMS65P80Y5W6DGQ0XRMRNW

______________________________________________________________________

## id: 01K6EMRCQP69VTRT7FW2RSH7QY

______________________________________________________________________

## id: 01K6EHZXRDFZFCJGQ8E9PGQBR4

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
