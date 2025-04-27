# ACB Testing Guide

This document outlines the comprehensive testing approach for the ACB package, focusing on the interface-based testing pattern that ensures consistent behavior across all adapter implementations.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Architecture](#test-architecture)
- [Test Interfaces](#test-interfaces)
- [Mock Implementations](#mock-implementations)
- [Writing Tests](#writing-tests)
- [Running Tests](#running-tests)
- [Adding New Tests](#adding-new-tests)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Testing Philosophy

The ACB testing approach is built on these core principles:

1. **Behavior-Based Testing**: Focus on testing the behavior of components, not their implementation details. This ensures that tests remain valid even when the internal implementation changes.

2. **Interface-Based Testing**: Use standardized interfaces to test different implementations consistently. All implementations of a given adapter type should pass the same set of tests.

3. **Simplified Mocking**: Use simple, predictable mocks instead of complex ones that are prone to failure. Mock implementations should be easy to understand and maintain.

4. **Reusable Test Patterns**: Define test patterns once and reuse them across different implementations. This reduces duplication and ensures consistency.

5. **Dependency Isolation**: Tests should not depend on external services or resources. Use mock implementations to isolate tests from external dependencies.

## Test Architecture

The ACB test architecture is organized around the concept of test interfaces and mock implementations:

```
tests/
├── test_interfaces.py       # Standardized test interfaces and mock implementations
├── adapters/                # Tests for adapter implementations
│   ├── cache/              # Cache adapter tests
│   │   ├── test_memory.py  # Memory cache tests
│   │   └── test_redis.py   # Redis cache tests
│   ├── storage/            # Storage adapter tests
│   │   ├── test_memory.py  # Memory storage tests
│   │   └── test_file.py    # File storage tests
│   ├── sql/                # SQL adapter tests
│   │   └── test_sql.py     # SQL adapter tests
│   └── ...                 # Other adapter tests
└── README.md               # This documentation file
```

## Test Interfaces

The `tests/test_interfaces.py` file contains standardized test interfaces for different adapter types. Each interface defines a set of tests that all implementations of that adapter type should pass.

Currently, the following test interfaces are available:

- **`StorageTestInterface`**: For testing storage adapters (file, memory, S3, etc.)
- **`CacheTestInterface`**: For testing cache adapters (Redis, memory, etc.)
- **`SQLTestInterface`**: For testing SQL adapters (PostgreSQL, MySQL, etc.)
- **`NoSQLTestInterface`**: For testing NoSQL adapters (MongoDB, Firestore, etc.)
- **`RequestsTestInterface`**: For testing HTTP client adapters (HTTPX, Niquests, etc.)
- **`SMTPTestInterface`**: For testing email adapters (Gmail, Mailgun, etc.)
- **`SecretTestInterface`**: For testing secret management adapters (Infisical, Secret Manager, etc.)
- **`DNSTestInterface`**: For testing DNS adapters (Cloud DNS, etc.)
- **`FTPDTestInterface`**: For testing FTP adapters (FTP, SFTP, etc.)
- **`MonitoringTestInterface`**: For testing monitoring adapters (Logfire, Sentry, etc.)
- **`ModelsTestInterface`**: For testing model adapters (SQLModel, etc.)

Each interface defines a set of test methods that verify the behavior of the adapter. For example, the `StorageTestInterface` includes tests for putting and getting files, checking if files exist, creating directories, etc.

### Example: StorageTestInterface

```python
class StorageTestInterface:
    """Standard interface for testing storage adapters."""

    @pytest.mark.asyncio
    async def test_init(self, storage):
        """Test initializing the storage."""
        # Initialize the storage
        result = await storage.init()
        # Verify the result
        assert result is not None

    @pytest.mark.asyncio
    async def test_put_get_file(self, storage):
        """Test putting and getting a file."""
        # Put a file
        content = b"test content"
        await storage.put_file("test.txt", content)

        # Get the file
        result = await storage.get_file("test.txt")

        # Verify the result
        assert result == content

    # Additional test methods...
```

## Mock Implementations

The `tests/test_interfaces.py` file also contains mock implementations of the adapters. These mock implementations provide a simple, in-memory version of each adapter type that can be used for testing.

Currently, the following mock implementations are available:

- **`MockStorage`**: A simple in-memory storage implementation
- **`MockCache`**: A simple in-memory cache implementation
- **`MockSQL`**: A simple in-memory SQL implementation
- **`MockNoSQL`**: A simple in-memory NoSQL implementation
- **`MockRequests`**: A simple mock HTTP client implementation
- **`MockSMTP`**: A simple mock email implementation
- **`MockSecret`**: A simple in-memory secret management implementation
- **`MockDNS`**: A simple in-memory DNS implementation
- **`MockFTPD`**: A simple mock FTP implementation
- **`MockMonitoring`**: A simple mock monitoring implementation
- **`MockModels`**: A simple in-memory model implementation

These mock implementations can be used for testing components that depend on these adapters, without requiring actual external services or resources.

### Example: MockStorage

```python
class MockStorage:
    """Mock storage implementation for testing."""

    def __init__(self):
        self._files = {}
        self._directories = set()
        self._initialized = False

    async def init(self):
        self._initialized = True
        return self

    async def put_file(self, path, content):
        # Store the file content in memory
        self._files[path] = content

        # Create parent directories if needed
        parts = path.split('/')
        if len(parts) > 1:
            directory = '/'.join(parts[:-1])
            self._directories.add(directory)

        return True

    # Additional methods...
```

## Writing Tests

To write tests for a new adapter implementation, you simply need to create a test fixture that returns an instance of your adapter, and then create a test class that inherits from the appropriate test interface.

### Storage Adapter Tests

```python
import pytest
from tests.test_interfaces import StorageTestInterface

@pytest.fixture
async def storage():
    """Create a Storage adapter instance for testing."""
    # Create and initialize your storage adapter
    storage = YourStorageAdapter()
    await storage.init()
    return storage

@pytest.mark.unit
class TestYourStorage(StorageTestInterface):
    """Test your storage adapter."""
    pass  # All tests are inherited from StorageTestInterface
```

### Cache Adapter Tests

```python
import pytest
from tests.test_interfaces import CacheTestInterface

@pytest.fixture
async def cache():
    """Create a Cache adapter instance for testing."""
    # Create and initialize your cache adapter
    cache = YourCacheAdapter()
    await cache.init()
    return cache

@pytest.mark.unit
class TestYourCache(CacheTestInterface):
    """Test your cache adapter."""
    pass  # All tests are inherited from CacheTestInterface
```

### Adding Implementation-Specific Tests

If your adapter implementation has specific behavior that needs to be tested beyond the standard interface, you can add additional test methods to your test class:

```python
import pytest
from tests.test_interfaces import StorageTestInterface

@pytest.fixture
async def storage():
    """Create a Storage adapter instance for testing."""
    storage = YourStorageAdapter()
    await storage.init()
    return storage

@pytest.mark.unit
class TestYourStorage(StorageTestInterface):
    """Test your storage adapter."""

    @pytest.mark.asyncio
    async def test_your_specific_feature(self, storage):
        """Test a feature specific to your storage adapter."""
        # Test your specific feature
        result = await storage.your_specific_method()
        assert result is not None
```

## Running Tests

ACB uses pytest for running tests. Here are some common commands for running tests:

### Run All Tests

```bash
python -m pytest
```

### Run Tests for a Specific Adapter

```bash
python -m pytest tests/adapters/storage/test_file.py
```

### Run Tests with Verbose Output

```bash
python -m pytest -v
```

### Run Tests with Coverage

```bash
python -m pytest --cov=acb
```

### Run Tests in Parallel

```bash
python -m pytest -xvs -n auto
```

## Adding New Tests

### Adding Tests to All Implementations

To add a new test to all implementations of an adapter type:

1. Add the test method to the appropriate interface class in `tests/test_interfaces.py`.
2. All implementations that inherit from that interface will automatically include the new test.

Example:

```python
class StorageTestInterface:
    # Existing test methods...

    @pytest.mark.asyncio
    async def test_new_feature(self, storage):
        """Test a new feature that all storage adapters should support."""
        # Test the new feature
        result = await storage.new_feature()
        assert result is not None
```

### Adding Tests to a Specific Implementation

To add a test specific to one implementation:

1. Add the test method to the implementation's test class.
2. The test will only be run for that implementation.

Example:

```python
class TestFileStorage(StorageTestInterface):
    # Inherits all tests from StorageTestInterface

    @pytest.mark.asyncio
    async def test_file_specific_feature(self, storage):
        """Test a feature specific to the file storage adapter."""
        # Test the file-specific feature
        result = await storage.file_specific_feature()
        assert result is not None
```

## Troubleshooting

### Common Issues

1. **Test Fixture Not Found**: Make sure your test fixture is named correctly. For example, the `StorageTestInterface` expects a fixture named `storage`.

2. **Async Test Errors**: Make sure you're using the `@pytest.mark.asyncio` decorator on all async test methods, and that you have the `pytest-asyncio` plugin installed.

3. **Mock Implementation Errors**: If you're using a mock implementation and getting errors, check that the mock implementation correctly implements all the methods required by the test interface.

4. **Test Isolation Issues**: Make sure each test is isolated from others. Use the fixture's `init()` method to reset the adapter state between tests.

### Debugging Tests

To debug tests, you can use the `-v` flag for verbose output and the `--pdb` flag to drop into the debugger on failure:

```bash
python -m pytest -v --pdb
```

## Best Practices

1. **Test Against Interfaces**: Always test against the adapter interface, not the specific implementation details.

2. **Use Mock Implementations**: Use mock implementations for testing components that depend on adapters, rather than real implementations that might require external services.

3. **Keep Tests Fast**: Tests should run quickly to encourage frequent testing. Avoid unnecessary I/O or network operations in tests.

4. **Maintain Test Independence**: Each test should be independent of others. Don't rely on state from previous tests.

5. **Test Edge Cases**: Make sure to test edge cases like empty inputs, large inputs, and error conditions.

6. **Keep Mock Implementations Simple**: Mock implementations should be simple and predictable, focusing on the behavior being tested rather than complex logic.

7. **Document Test Requirements**: Document any special requirements or setup needed for tests, especially for tests that interact with external services.

8. **Use Descriptive Test Names**: Test names should clearly describe what is being tested and what the expected outcome is.

9. **Add Tests for Bug Fixes**: When fixing a bug, add a test that would have caught the bug to prevent regression.

10. **Review Test Coverage**: Regularly review test coverage to identify areas that need more testing.
