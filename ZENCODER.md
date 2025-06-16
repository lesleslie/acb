# Zencoder AI Instructions - Compact

## Core Workflow
**Primary tool**: `python -m crackerjack` for all development operations
**Standard commands**:
```bash
python -m crackerjack -x -t -c    # Clean, test, commit
python -m crackerjack -a micro    # Auto: clean, test, bump, commit
python -m crackerjack -t -s       # Test without pre-commit hooks
python -m crackerjack -i          # Interactive pre-commit selection
python -m crackerjack -v          # Verbose output
```

## Code Quality Standards
- **Ruff**: Primary linting/formatting (replaces Black, isort, flake8)
- **Pyright**: Strict type checking
- **Python 3.13+**: Minimum version
- **PDM**: Dependency management
- **Pre-commit hooks**: Mandatory for all commits

**Ruff config**:
```toml
[tool.ruff]
target-version = "py313"
line-length = 88
fix = true
unsafe-fixes = true

[tool.ruff.lint]
extend-select = ["C901", "D", "F", "I", "UP"]
ignore = ["D100", "D101", "D102", "D103", "D104", "D105", "D106", "D107", "F821", "UP040"]
```

## Testing Requirements
1. **Never create actual files** - Use comprehensive mocking only
2. **Async-aware fixtures** with proper cleanup
3. **Coverage target**: 42% minimum
4. **Parallel execution**: `--test-workers=N` for optimization
5. **Timeout protection**: `--test-timeout=300` for large projects

**Mock pattern**:
```python
class MockStorage:
    def __init__(self):
        self._files = {}
    async def read(self, path: str) -> bytes:
        return self._files.get(path, b"")
```

## Architecture Patterns
**Adapter Pattern** (ACB/FastBlocks):
```python
from acb.adapters import import_adapter
from acb.depends import depends

Cache, Storage = import_adapter("cache", "storage")

@depends.inject
async def my_function(cache: Cache = depends(), storage: Storage = depends()):
    pass
```

**Directory structure**:
```
project/
├── actions/          # Utility functions
├── adapters/         # External integrations (cache/, storage/, sql/)
├── settings/         # YAML configuration
├── tests/           # Mocked test suite
└── pyproject.toml   # All project config
```

## Development Rules
1. **Edit existing files** - Never create new files unless required
2. **No documentation files** unless explicitly requested
3. **Absolute paths only** for all file operations
4. **Type annotations required** with Protocol over ABC
5. **Async-first architecture** throughout
6. **Pathlib for files**: `pathlib.Path` (sync) or `anyio.Path` (async)
7. **Configuration in pyproject.toml** - avoid separate config files

## Code Quality Compliance
**Refurb Standards** (Modern Python):
- Use `pathlib.Path` instead of `os.path`
- Use `str.removeprefix()` / `str.removesuffix()` instead of slicing
- Use `|` for union types instead of `Union`
- Use `dict1 | dict2` for merging instead of `{**dict1, **dict2}`
- Use `any()` / `all()` instead of manual loops
- Use list/dict comprehensions appropriately
- Use `enumerate()` instead of manual indexing
- Always use context managers for resources

**Bandit Security** (Never do):
- `eval()`, `exec()`, `compile()` with user input
- `subprocess.shell=True` or `os.system()`
- `random` for crypto - use `secrets` module
- Hardcoded passwords/secrets in code
- String concatenation for SQL - use parameterized queries
- Predictable temp file names - use `tempfile`
- Missing encoding in file operations

## Version Management
```bash
python -m crackerjack -b micro    # Bump version only
python -m crackerjack -p minor    # Bump and publish
python -m crackerjack -a major    # Auto major release
```

## Framework Specifics
**ACB**: Component registration, dependency injection via `@depends.inject`, Protocol interfaces
**FastBlocks**: Starlette ASGI, HTMX integration, Jinja2 async templates with `[[` `]]` delimiters

## Project Optimization
**Large projects (>1000 files)**: `--test-workers=2 --test-timeout=300`
**Small projects (<100 files)**: Default parallelization, use `python -m crackerjack -x -t -c` frequently

## Security
- Pre-commit hooks prevent credential commits
- Bandit security scanning
- Environment-based settings (dev/prod)
- Secret detection mandatory

## Key Conventions
- **Mock filesystem** - never create real files in tests
- **YAML config** in `settings/` with Pydantic models
- **Comprehensive error handling** with structured exceptions
- **Resource cleanup** via context managers
- **Google docstring format** when documentation needed (rare)

Always prioritize: Code quality → Test coverage → Security → Performance
