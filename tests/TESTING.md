# Testing ACB

This document provides information about running tests for the ACB project.

## Running Tests

### Using the test script

The recommended way to run tests is to use the provided test script:

```bash
./tests/run_tests.py
```

You can pass additional pytest arguments to the script:

```bash
./tests/run_tests.py -v                # Run with verbose output
./tests/run_tests.py tests/test_config.py  # Run specific tests
```

### Using pytest directly

You can also run tests directly using pytest:

```bash
python -m pytest
```

## Test Configuration

The test configuration is defined in `pyproject.toml` and `tests/conftest.py`. The tests use pytest fixtures to mock dependencies and prevent file system operations during testing.

## Implementation Details

The `pytest_sessionfinish` function in `tests/conftest.py` has been modified to detect when tests are being run by crackerjack. It checks for the presence of the crackerjack module in `sys.modules` and for the `RUNNING_UNDER_CRACKERJACK` environment variable, and skips the aggressive process killing if either is detected.

However, due to issues with crackerjack, we recommend using the `run_tests.py` script instead, which runs pytest directly.

This allows tests to run properly without being killed prematurely.
