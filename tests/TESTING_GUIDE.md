# ACB Test Suite: Setup and Execution Guide

## Overview

This document provides information about the ACB project's test suite, including setup, execution options, and best practices.

## Test Categories and Markers

The ACB test suite uses various pytest markers to categorize tests for different purposes:

### Core Categories

- `@pytest.mark.unit` - Fast unit tests for individual components
- `@pytest.mark.integration` - Tests for component integration
- `@pytest.mark.architecture` - Architecture validation tests
- `@pytest.mark.quick` - Fast-running tests that provide good coverage
- `@pytest.mark.coverage` - Tests that provide unique coverage

### Component-Specific Markers

- `@pytest.mark.actions` - Tests for ACB actions system
- `@pytest.mark.adapters` - Tests for ACB adapters
- `@pytest.mark.hash`, `@pytest.mark.compress`, `@pytest.mark.encode` - Specific action types
- `@pytest.mark.cache`, `@pytest.mark.storage`, `@pytest.mark.sql` - Specific adapter types

### Special Markers

- `@pytest.mark.benchmark` - Performance benchmark tests (never run in parallel)
- `@pytest.mark.external` - Tests requiring external services (requires `--run-external`)

## Running Tests

### Basic Commands

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run tests with coverage
python -m pytest --cov=acb --cov-report=html

# Run tests in parallel (excluding benchmarks)
python -m pytest -n auto --dist=loadfile
```

### Using the Test Runner Script

The project includes a streamlined test runner script:

```bash
# Run the script directly
python scripts/test_runner.py

# Run only unit tests
python scripts/test_runner.py --unit

# Run with coverage
python scripts/test_runner.py --coverage

# Run integration tests (with external services)
python scripts/test_runner.py --integration --external

# Run only actions tests in parallel
python scripts/test_runner.py --actions --parallel

# Run specific test files
python scripts/test_runner.py tests/test_config.py tests/test_depends.py
```

### Selective Execution

You can run specific categories of tests:

```bash
# Only quick unit tests
python -m pytest -m "unit and quick"

# All tests except external ones
python -m pytest -m "not external"

# Only adapter tests
python -m pytest -m adapters

# Multiple categories
python -m pytest -m "unit or architecture"
```

## Test Structure and Conventions

### Fixtures

Tests use shared fixtures defined in `tests/conftest.py`:

- `mock_config` - Standardized mock configuration object
- `reset_dependency_container` - Ensures test isolation for dependency injection
- `event_loop` - Asyncio event loop for async tests

### Best Practices

1. Use appropriate markers for all tests
1. Make sure tests are isolated (dependency container is reset automatically)
1. Use the shared `mock_config` fixture instead of creating your own
1. Add `@pytest.mark.quick` to tests that run fast (under 1 second)
1. Mark external service tests with `@pytest.mark.external`

## Performance Guidelines

### Parallel Execution

- The test suite supports parallel execution via pytest-xdist
- Tests are distributed by file to reduce fixture overhead
- Benchmark tests are never run in parallel
- Use `--dist=loadfile` for better performance with similar test times

### Optimization Strategies

1. Use `--lf` (last failed) flag to run only previously failed tests
1. Use `--ff` (failed first) to run failed tests first
1. Run specific test files directly for faster feedback during development
1. Use category-based execution for CI/CD pipeline optimization

## CI/CD Configuration

For continuous integration, consider using these commands:

```bash
# For unit tests in CI (fast feedback)
python scripts/test_runner.py --unit --parallel --coverage

# For integration tests
python scripts/test_runner.py --integration --external

# For architecture validation
python scripts/test_runner.py --architecture
```

## Troubleshooting

### Common Issues

- **Import errors**: Make sure you're running tests from the project root
- **Dependency conflicts**: Ensure you're using the correct virtual environment
- **Parallel execution failures**: Some tests might need to be marked as non-parallel

### Debugging Tips

- Use `-v` flag for verbose output
- Use `--tb=short` or `--tb=long` for different traceback detail levels
- Run individual test files to isolate issues: `python -m pytest tests/test_specific.py`
