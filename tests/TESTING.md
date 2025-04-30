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
```


## Test Configuration

The test configuration is defined in `pyproject.toml` and `tests/conftest.py`. The tests use pytest fixtures to mock dependencies and prevent file system operations during testing.

## Implementation Details

The `pytest_sessionfinish` function in `tests/conftest.py` has been modified to detect when tests are being run by crackerjack. It checks for the presence of the crackerjack module in `sys.modules` and for the `RUNNING_UNDER_CRACKERJACK` environment variable, and skips the aggressive process killing if either is detected.

This allows tests to run properly without being killed prematurely when using crackerjack.
