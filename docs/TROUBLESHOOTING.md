# ACB Troubleshooting Guide

> **ACB Documentation**: [Main](../README.md) | [Core Systems](../acb/README.md) | [Actions](../acb/actions/README.md) | [Adapters](../acb/adapters/README.md)

This guide helps you troubleshoot common issues when working with ACB.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Dependency Injection Issues](#dependency-injection-issues)
- [Adapter Issues](#adapter-issues)
- [Testing Issues](#testing-issues)
- [Performance Issues](#performance-issues)
- [Common Error Messages](#common-error-messages)

## Installation Issues

### Python Version Compatibility

**Problem**: `ERROR: Package requires a different Python version`

**Solution**: ACB requires Python 3.13 or later. Check your Python version:
```bash
python --version
# Should show Python 3.13.x or higher
```

### UV Installation Problems

**Problem**: `uv: command not found`

**Solution**: Install UV first:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or using pip
pip install uv
```

### Optional Dependencies Not Installing

**Problem**: Import errors for specific adapters

**Solution**: Install the correct optional dependencies:
```bash
# For cache features
uv add "acb[cache]"

# For SQL database features
uv add "acb[sql]"

# For all features
uv add "acb[all]"
```

## Configuration Issues

### Configuration Files Not Found

**Problem**: `FileNotFoundError: No such file or directory: 'settings/app.yml'`

**Solution**: Create the required configuration structure:
```bash
mkdir -p settings
touch settings/app.yml
touch settings/adapters.yml
touch settings/debug.yml
```

### Invalid YAML Syntax

**Problem**: `yaml.scanner.ScannerError: mapping values are not allowed here`

**Solution**: Check your YAML syntax. Common issues:
- Inconsistent indentation (use spaces, not tabs)
- Missing spaces after colons
- Special characters in strings (use quotes)

```yaml
# Correct YAML
app:
  name: "MyApp"
  domain: "example.com"

# Incorrect YAML
app:
name:"MyApp"  # Missing space after colon
domain:example.com  # Missing space after colon
```

### Secret Management Issues

**Problem**: `SecretError: Unable to load secrets`

**Solution**:
1. Check that secret files exist in `settings/secrets/`
2. Verify file permissions allow reading
3. Ensure YAML syntax is correct in secret files

## Dependency Injection Issues

### Adapter Not Found

**Problem**: `KeyError: 'cache'` or similar adapter not found errors

**Solution**:
1. Ensure the adapter is configured in `settings/adapters.yml`:
   ```yaml
   cache: redis  # or memory
   ```
2. Check that optional dependencies are installed
3. Verify the adapter name matches exactly

### Type Annotation Errors

**Problem**: IDE shows type errors with `depends()` calls

**Solution**: Import and use adapter types correctly:
```python
from acb.adapters import import_adapter

# Get the adapter class (not instance)
Cache = import_adapter("cache")

# Use in function signature
@depends.inject
async def my_function(cache: Cache = depends()):
    pass
```

### Circular Dependency Errors

**Problem**: `RecursionError: maximum recursion depth exceeded`

**Solution**: Restructure your dependencies to avoid circles:
- Use interfaces/protocols instead of concrete classes
- Consider using factory patterns
- Break circular references with lazy loading

## Adapter Issues

### Redis Connection Issues

**Problem**: `ConnectionError: Error connecting to Redis`

**Solution**:
1. Ensure Redis server is running: `redis-cli ping`
2. Check connection settings in configuration
3. Verify network connectivity
4. Check Redis logs for specific errors

### Database Connection Issues

**Problem**: `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server`

**Solution**:
1. Verify database server is running
2. Check connection credentials
3. Ensure database exists
4. Check network connectivity and firewall settings

### Storage Access Issues

**Problem**: `PermissionError: [Errno 13] Permission denied`

**Solution**:
1. Check file/directory permissions
2. Verify the application has write access
3. For cloud storage, check authentication credentials
4. Ensure storage buckets/containers exist

## Testing Issues

### Mock Dependencies Not Working

**Problem**: Tests still use real dependencies instead of mocks

**Solution**: Ensure proper mock setup in conftest.py:
```python
@pytest.fixture(autouse=True)
def mock_dependencies():
    # Mock your dependencies here
    mock_cache = AsyncMock()
    depends.set("cache", mock_cache)
    yield
    # Cleanup if needed
```

### File System Tests Failing

**Problem**: Tests create actual files or fail due to missing files

**Solution**: Use the provided mock file system fixtures:
```python
def test_file_operation(mock_async_file_system, patch_async_file_operations):
    # Your test code here - files will be mocked
    pass
```

### Async Test Issues

**Problem**: `RuntimeError: cannot be called from a running event loop`

**Solution**: Use proper async test decorators:
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

## Performance Issues

### Slow Application Startup

**Problem**: Application takes a long time to start

**Solution**:
1. Check for blocking I/O in initialization code
2. Use lazy loading for expensive resources
3. Profile startup to identify bottlenecks
4. Consider async initialization patterns

### Memory Usage Issues

**Problem**: High memory consumption

**Solution**:
1. Check cache TTL settings - lower values reduce memory usage
2. Review object lifecycle management
3. Use connection pooling for database adapters
4. Monitor for memory leaks in long-running processes

### Slow Database Queries

**Problem**: Database operations are slow

**Solution**:
1. Enable query caching where appropriate
2. Add database indexes for frequently queried columns
3. Use connection pooling
4. Consider read replicas for read-heavy workloads

## Common Error Messages

### `ModuleNotFoundError: No module named 'acb'`

**Cause**: ACB is not installed or not in Python path

**Solution**: Install ACB: `uv add acb`

### `ImportError: cannot import name 'import_adapter'`

**Cause**: Incorrect import path

**Solution**: Use correct import: `from acb.adapters import import_adapter`

### `AttributeError: 'NoneType' object has no attribute 'get'`

**Cause**: Adapter not properly initialized or registered

**Solution**:
1. Check adapter configuration
2. Ensure proper dependency injection setup
3. Verify adapter registration

### `pydantic.ValidationError: validation error for AppSettings`

**Cause**: Invalid configuration values

**Solution**:
1. Check configuration file syntax
2. Verify all required fields are provided
3. Check data types match field definitions

### `RuntimeError: Event loop is closed`

**Cause**: Async operations after event loop shutdown

**Solution**:
1. Ensure proper async context management
2. Use `asyncio.run()` for main application entry
3. Avoid async operations in destructors

## Debug Mode

When troubleshooting, enable debug mode for more detailed information:

```yaml
# settings/debug.yml
debug:
  enabled: true
  production: false
  log_level: "DEBUG"

  # Enable debug for specific modules
  cache: true
  storage: true
  sql: true
```

## Getting Help

If you continue to experience issues:

1. Check the [ACB documentation](../README.md)
2. Review adapter-specific documentation
3. Enable debug logging for more details
4. Create a minimal reproduction case
5. Report issues on the [GitHub repository](https://github.com/lesleslie/acb/issues)
