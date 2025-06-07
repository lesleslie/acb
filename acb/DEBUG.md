# Debug Documentation

> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

## Overview

ACB's debug module provides comprehensive debugging tools designed for asynchronous applications. It offers enhanced output, performance timing, and environment-aware behavior to help troubleshoot applications effectively.

## Core Features

### Enhanced Debug Output

ACB uses [icecream](https://github.com/gruns/icecream) for improved debug output:

```python
from acb.debug import debug

# Basic debugging
user_id = 123
debug(user_id)  # Output: debug: user_id = 123

# Debug multiple values
name = "Alice"
age = 30
debug(name, age)  # Output: debug: name = 'Alice', age = 30

# Debug complex objects with automatic formatting
user_data = {
    "id": 123,
    "name": "Alice",
    "roles": ["admin", "user"],
    "settings": {"theme": "dark", "notifications": True}
}
debug(user_data)  # Outputs nicely formatted representation
```

### Performance Timing

The `timeit` decorator measures function execution time:

```python
from acb.debug import timeit
import asyncio
import typing as t

@timeit
async def slow_operation(data: dict[str, t.Any]) -> dict[str, t.Any]:
    """This function's execution time will be logged."""
    await asyncio.sleep(0.5)  # Simulate slow operation
    return {"processed": True, "input_size": len(data)}

# When called, outputs: slow_operation took 0.501s
result = await slow_operation({"key": "value"})
```

### Pretty Printing

For complex data structures, use the async pretty print function:

```python
from acb.debug import pprint
import asyncio

async def main():
    complex_data = {
        "users": [
            {"id": 1, "name": "Alice", "roles": ["admin"]},
            {"id": 2, "name": "Bob", "roles": ["user"]}
        ],
        "metadata": {
            "version": "1.0",
            "created": "2024-01-01",
            "settings": {"debug": True, "verbose": False}
        }
    }

    # Pretty print with enhanced formatting
    await pprint(complex_data)

asyncio.run(main())
```

## Configuration

### Debug Settings

Configure debugging behavior in `settings/debug.yml`:

```yaml
debug:
  enabled: true           # Global debug enable/disable
  production: false       # Production mode changes behavior
  log_level: "DEBUG"      # Debug log level

  # Module-specific debug settings
  cache: true             # Enable debugging for cache operations
  storage: false          # Disable debugging for storage operations
  sql: true              # Enable debugging for SQL operations
  requests: false        # Disable debugging for HTTP requests
```

### Environment-Aware Behavior

Debug output automatically adjusts based on environment:

```python
from acb.debug import debug, init_debug

# Initialize debug system (called automatically by ACB)
init_debug()

# Debug behavior changes based on environment:
# - Development: Colorized, verbose output to stderr
# - Production: Minimal output routed to logging system
# - Testing: Simplified output for test clarity
```

## Advanced Debugging Techniques

### Module Context Debugging

Get information about calling modules:

```python
from acb.debug import get_calling_module, patch_record
from acb.depends import depends
from acb.logger import Logger

def debug_with_context():
    # Get the module that called this function
    module = get_calling_module()

    # Add module context to log records
    logger = depends.get(Logger)
    patch_record(module, "Debug message with module context")

    print(f"Called from module: {module}")
```

### Conditional Debugging

Enable debugging based on conditions:

```python
from acb.debug import debug
from acb.depends import depends
from acb.config import Config

@depends.inject
async def conditional_debug(
    data: dict,
    config: Config = depends()
):
    if config.debug.enabled and config.debug.cache:
        debug(f"Cache operation: {data}")

    # Your logic here
    await process_data(data)
```

### Performance Profiling

Combine timing with detailed analysis:

```python
from acb.debug import timeit, debug
import time

@timeit
async def profile_operation():
    debug("Starting expensive operation")

    # Simulate database query
    start = time.time()
    await asyncio.sleep(0.2)
    debug(f"Database query took: {time.time() - start:.3f}s")

    # Simulate data processing
    start = time.time()
    await asyncio.sleep(0.1)
    debug(f"Data processing took: {time.time() - start:.3f}s")

    return "Operation complete"

# Output includes both overall timing and internal breakdowns
```

## Integration with Logging

### Debug to Logger Integration

Debug output can be routed through the logging system:

```python
from acb.debug import debug
from acb.depends import depends
from acb.logger import Logger

@depends.inject
async def debug_with_logging(
    data: dict,
    logger: Logger = depends()
):
    # Debug output in development goes to stderr
    # In production, it's routed to the logger
    debug(f"Processing data: {len(data)} items")

    # Explicit logging
    logger.debug(f"Explicit debug log: {data}")
```

### Structured Debug Data

Combine debug output with structured logging:

```python
from acb.debug import debug, pprint
from acb.depends import depends
from acb.logger import Logger

@depends.inject
async def structured_debugging(
    operation: str,
    data: dict,
    logger: Logger = depends()
):
    # Quick debug for development
    debug(f"Operation: {operation}")

    # Structured logging for production
    logger.info(
        "Operation started",
        operation=operation,
        data_size=len(data),
        timestamp=time.time()
    )

    # Pretty print complex data
    await pprint(data)
```

## Best Practices

### Development vs Production

```python
from acb.debug import debug
from acb.depends import depends
from acb.config import Config

@depends.inject
async def environment_aware_debug(
    config: Config = depends()
):
    if not config.debug.production:
        # Verbose debugging in development
        debug("Detailed development information")
        debug(locals())  # Show all local variables
    else:
        # Minimal debugging in production
        debug("Production debug info only")
```

### Performance Considerations

```python
from acb.debug import debug, timeit
from acb.depends import depends
from acb.config import Config

# Only apply timing decorator in debug mode
@depends.inject
def maybe_time_function(func):
    config = depends.get(Config)
    if config.debug.enabled:
        return timeit(func)
    return func

@maybe_time_function
async def potentially_slow_function():
    # This is only timed when debug is enabled
    await expensive_operation()
```

### Debugging Complex Flows

```python
from acb.debug import debug, timeit
import typing as t

class DebugContext:
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None

    async def __aenter__(self):
        debug(f"Starting {self.operation}")
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            debug(f"{self.operation} failed after {duration:.3f}s: {exc_val}")
        else:
            debug(f"{self.operation} completed in {duration:.3f}s")

# Usage
async def complex_operation():
    async with DebugContext("User data processing"):
        # Your complex logic here
        await process_user_data()
        await update_cache()
        await send_notifications()
```

## Troubleshooting Debug Issues

### Common Problems

**Debug Output Not Appearing**:
- Check that `debug.enabled` is `true` in configuration
- Verify that the module-specific debug flag is enabled
- Ensure you're not in production mode when expecting verbose output

**Performance Impact**:
- Use conditional debugging in production
- Disable debug output for high-frequency operations
- Consider using module-specific debug flags

**Type Errors with Debug Functions**:
- Ensure proper async/await usage with `pprint`
- Check that debug functions are imported correctly

### Debug Configuration Examples

```yaml
# Development configuration
debug:
  enabled: true
  production: false
  log_level: "DEBUG"
  cache: true
  storage: true
  sql: true

# Production configuration
debug:
  enabled: true
  production: true
  log_level: "INFO"
  cache: false
  storage: false
  sql: false
```

## Integration Examples

### With FastAPI/Web Applications

```python
from fastapi import FastAPI, Depends
from acb.debug import debug, timeit
from acb.depends import depends as acb_depends

app = FastAPI()

@timeit
@app.get("/users/{user_id}")
async def get_user(
    user_id: str,
    cache=Depends(lambda: acb_depends.get("cache"))
):
    debug(f"Fetching user: {user_id}")

    user = await cache.get(f"user:{user_id}")
    if not user:
        debug("User not in cache, fetching from database")
        # Fetch from database...

    return user
```

### With Data Processing Pipelines

```python
from acb.debug import debug, timeit, pprint

@timeit
async def process_data_pipeline(data: list[dict]):
    debug(f"Processing {len(data)} records")

    results = []
    for i, item in enumerate(data):
        if i % 100 == 0:  # Debug every 100 items
            debug(f"Processed {i}/{len(data)} items")

        result = await process_item(item)
        results.append(result)

    debug("Pipeline complete")
    await pprint({"total": len(results), "sample": results[:3]})
    return results
```
