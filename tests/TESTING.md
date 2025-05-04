# Testing ACB

This document provides information about running tests for the ACB project.

## Running Tests

### Using pytest

The recommended way to run tests is to use pytest directly:

```bash
python -m pytest
```

You can pass additional pytest arguments:

```bash
python -m pytest -v                # Run with verbose output
python -m pytest tests/test_config.py  # Run specific tests
python -m pytest --run-slow        # Run slow tests
```

## Test Configuration

The test configuration is defined in `pyproject.toml` and `tests/conftest.py`. The tests use pytest fixtures to mock dependencies and prevent file system operations during testing.

## Mocking Guidelines

### Avoiding File System Operations

Tests should **never** create actual files, directories, or settings during test execution. Instead, use the simplified mock fixtures provided in `tests/conftest.py`:

- `temp_dir`: Returns a mock Path object instead of creating an actual directory
- `mock_config`: Provides a mocked Config object with mock paths
- `mock_file_system`: Simplified in-memory file system for tests
- `patch_file_operations`: Patches pathlib.Path operations to use the mock file system
- `mock_async_file_system`: Simplified in-memory async file system for tests
- `patch_async_file_operations`: Patches anyio.Path operations to use the mock async file system
- `mock_settings`: Provides mock settings without creating actual settings files
- `mock_tmp_path`: Simple mock replacement for pytest's built-in tmp_path fixture
- `mock_tempfile`: Simple mock replacement for Python's tempfile module

The mock file system implementations have been simplified to reduce complexity while still providing the necessary functionality.

### Adapter and Config Mocking

The test suite includes automatic patching for adapter imports and configuration directly in the main conftest.py file:

- `patch_adapter_imports`: Automatically patches adapter imports to avoid looking for actual adapter files
- `patch_config`: Automatically patches the config module to avoid looking for actual config files

These fixtures are applied automatically for all tests, so you don't need to explicitly import or use them. They ensure that:

1. No actual files or directories are created during tests
2. No actual configuration files are read
3. Adapter imports work without requiring actual adapter files
4. Modules that import other adapters (like SMTP and FTPD) can be tested without dependencies

### Example: Using Mock File System

```python
@pytest.mark.asyncio
async def test_file_operations(self, mock_file_system, patch_file_operations):
    # Create a mock file path
    file_path = Path("/mock/path/test_file.txt")

    # Write to the mock file system
    file_path.write_text("test content")

    # Read from the mock file system
    content = file_path.read_text()
    assert content == "test content"
```

### Example: Using Mock Async File System

```python
@pytest.mark.asyncio
async def test_async_file_operations(self, mock_async_file_system, patch_async_file_operations):
    from anyio import Path as AsyncPath

    file_path = AsyncPath("/mock/path/test_file.txt")

    # Write to the mock async file system
    await file_path.write_text("test content")

    # Read from the mock async file system
    content = await file_path.read_text()
    assert content == "test content"
```

### Consolidating Tests

For adapter tests, consolidate module-specific test files into a single `_test.py` file rather than creating separate test files for each module. Follow the pattern of existing adapter tests.

## Implementation Details

The `pytest_sessionfinish` function in `tests/conftest.py` has been modified to detect when tests are being run by crackerjack. It checks for the presence of the crackerjack module in `sys.modules` and for the `RUNNING_UNDER_CRACKERJACK` environment variable, and skips the aggressive process killing if either is detected.

This allows tests to run properly without being killed prematurely when using crackerjack.
