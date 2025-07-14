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

Tests should **never** create actual files, directories, or settings during test execution. Instead, use the mock fixtures provided in `tests/conftest.py`:

- `mock_config`: Provides a mocked Config object with mock paths
- `mock_file_system`: Simplified in-memory file system for tests
- `mock_async_file_system`: Simplified in-memory async file system for tests
- `mock_settings`: Provides mock settings without creating actual settings files
- `mock_tmp_path`: Simple mock replacement for pytest's built-in tmp_path fixture
- `mock_tempfile`: Simple mock replacement for Python's tempfile module
- `mock_async_path`: Mock for AsyncPath objects
- `mock_path_constructor`: Mock for Path constructor
- `mock_secrets_path`: Mock for secrets directory path

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

### Mock Class Method Delegation

When creating mock classes for testing adapters, it's important to implement proper method delegation, especially when the class being mocked has both public and private methods. Follow these guidelines:

1. **Public-Private Method Delegation**: Ensure that public methods in mock classes properly delegate to their private counterparts, just as they do in the actual implementation.

   ```python
   # Original class
   class SomeAdapter:
       def public_method(self, arg):
           return self._private_method(arg)

       def _private_method(self, arg):
           # Implementation

   # Mock class - CORRECT implementation
   class MockAdapter:
       def public_method(self, arg):
           return self._private_method(arg)  # Proper delegation

       def _private_method(self, arg):
           # Mock implementation
   ```

2. **Separate Test Classes for Complex Mocks**: For adapters with complex dependencies (like Redis, SQLModel), create separate test classes with their own fixtures to avoid conflicts with base classes.

3. **Patching External Dependencies**: Use `unittest.mock.patch` to mock external dependencies like file system operations:

   ```python
   @pytest.mark.asyncio
   @patch.object(AsyncPath, "exists")
   async def test_with_patched_method(self, mock_exists):
       mock_exists.return_value = False  # Mock the behavior
       # Test implementation
   ```

4. **Exception Handling in Mocks**: Ensure that mock objects properly handle exceptions that would occur in the real implementation, such as `FileNotFoundError` for file operations.

### Example: Proper Mock Implementation

```python
# Test class with proper method delegation
class TestRedisCache:
    @pytest.fixture
    def redis_mock(self):
        class MockRedis:
            def __init__(self):
                self.data = {}

            async def get(self, key):
                # Public method delegates to private method
                return await self._get(key)

            async def _get(self, key):
                # Mock implementation
                return self.data.get(key)

        return MockRedis()

    @pytest.mark.asyncio
    async def test_redis_get(self, redis_mock):
        redis_mock.data["test_key"] = "test_value"
        result = await redis_mock.get("test_key")
        assert result == "test_value"
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

### Test Organization

For adapter tests, the project follows a structured approach:

1. **Base Test Files**: Each adapter category has a base test file (e.g., `test_cache_base.py`, `test_sql_base.py`) that contains:
   - Common test fixtures
   - Base class tests
   - Shared assertion utilities

2. **Implementation-Specific Tests**: Each adapter implementation has its own test file (e.g., `test_redis.py`, `test_infisical.py`) that:
   - Focuses on implementation-specific behavior
   - Uses fixtures and utilities from the base test file
   - Implements proper mock objects with method delegation

3. **Reusable Test Functions**: Where possible, test functions are designed to be reusable across different adapter implementations, like the `assert_cache_operations` function.

This organization allows for thorough testing of both the base adapter functionality and the specific implementation details of each adapter variant.

## Implementation Details

The `pytest_sessionfinish` function in `tests/conftest.py` has been modified to detect when tests are being run by crackerjack. It checks for the presence of the crackerjack module in `sys.modules` and for the `RUNNING_UNDER_CRACKERJACK` environment variable, and skips the aggressive process killing if either is detected.

This allows tests to run properly without being killed prematurely when using crackerjack.

## Testing with Crackerjack

[Crackerjack](https://github.com/lesleslie/crackerjack) is a tool that can be used to run tests with AI assistance. It's particularly useful for debugging failing tests and understanding test behavior.

### Basic Usage

To run tests with Crackerjack:

```bash
python -m crackerjack
```

Or if using UV:

```bash
uv run python -m crackerjack
```

### Using the AI Agent

The `--ai-agent` flag enables AI assistance when running tests:

```bash
python -m crackerjack --ai-agent
```

This will provide AI-powered analysis of test failures and suggestions for fixes.

### Showing Output with -s Flag

When running tests with Crackerjack, you can use the `-s` flag to show print statements and other output during test execution:

```bash
python -m crackerjack -s
```

You can combine this with the AI agent flag:

```bash
python -m crackerjack --ai-agent -s
```

### Running Specific Tests

Crackerjack accepts command line arguments for specific options, but doesn't directly accept test file paths like pytest does. Instead, it's typically run with specific flags for its automated workflow:

```bash
# Run with AI agent assistance
python -m crackerjack --ai-agent

# Show output during test execution
python -m crackerjack -s

# Run the full automated workflow (linting, testing, version bump, commit)
python -m crackerjack -x -t -p <version> -c

# Alternative automated workflow
python -m crackerjack -a <version>
```

To run specific tests, you should use pytest directly:

```bash
# Run tests in a specific directory
pytest tests/adapters/cache/

# Run a specific test file with output shown
pytest tests/adapters/cache/test_redis.py -s
```

### Benefits of Using Crackerjack

1. **AI-Assisted Debugging**: The AI agent can analyze test failures and suggest fixes
2. **Detailed Output**: Using the `-s` flag provides visibility into what's happening during test execution
3. **Compatible with ACB's Test Suite**: The test suite has been configured to work properly with Crackerjack

Remember that when using Crackerjack, the `pytest_sessionfinish` function in our test configuration will automatically detect it and adjust behavior accordingly.
