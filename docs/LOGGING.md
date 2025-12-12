# Logging Documentation

> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](../acb/actions/README.md) | [Adapters](../acb/adapters/README.md)

## Overview

ACB provides a powerful logging system based on [Loguru](https://loguru.readthedocs.io/) with support for asynchronous operations, structured logging, and multiple output formats. The logging system is designed to work seamlessly with ACB's dependency injection and configuration systems.

## Core Features

### Asynchronous Logging

ACB's logging system is built for async applications:

```python
from acb.depends import depends, Inject
from acb.logger import Logger


@depends.inject
async def async_operation(logger: Inject[Logger]):
    logger.info("Starting async operation")

    # Async logging doesn't block
    await some_async_work()

    logger.info("Async operation completed")
```

### Structured Logging

Support for structured data in log messages:

```python
@depends.inject
async def structured_logging_example(logger: Inject[Logger]):
    # Log with structured data
    logger.info(
        "User login attempt",
        user_id=123,
        ip_address="192.168.1.1",
        success=True,
        duration_ms=150,
    )

    # Log with context
    logger.error(
        "Database connection failed",
        database="postgresql",
        host="db.example.com",
        port=5432,
        retry_count=3,
    )
```

### Multiple Log Levels

Standard logging levels with contextual usage:

```python
@depends.inject
async def log_levels_example(logger: Inject[Logger]):
    # Debug: Detailed information for debugging
    logger.debug("Variable state", user_data=user_dict)

    # Info: General information about program execution
    logger.info("User authenticated successfully", user_id=user.id)

    # Warning: Something unexpected happened but the program continues
    logger.warning("Cache miss, falling back to database", cache_key="user:123")

    # Error: A serious problem occurred but the program continues
    logger.error("Failed to send email", recipient=email, error=str(e))

    # Critical: A very serious error occurred, program may stop
    logger.critical("Database connection lost", database_url=db_url)
```

## Configuration

### Logger Settings

Configure logging behavior in `settings/app.yaml`:

```yaml
logger:
  level: "INFO"           # Minimum log level
  format: "json"          # Output format: json, text
  colorize: true          # Enable colors in development
  serialize: false        # JSON serialization for structured logs
  backtrace: true         # Include backtrace in error logs
  diagnose: true          # Include variable values in tracebacks

  # File output (optional)
  file:
    enabled: true
    path: "logs/app.log"
    rotation: "10 MB"
    retention: "30 days"
    compression: "gz"
```

### Environment-Specific Configuration

```yaml
# Development settings
logger:
  level: "DEBUG"
  colorize: true
  serialize: false

# Production settings
logger:
  level: "INFO"
  colorize: false
  serialize: true
  file:
    enabled: true
    path: "/var/log/myapp/app.log"
```

### Adapter Selection

Choose logging implementation in `settings/adapters.yaml`:

```yaml
# Use Loguru (default)
logger: loguru

# Alternative: use structlog
logger: structlog
```

## Advanced Usage

### Context Managers for Logging

```python
from acb.depends import depends, Inject
from acb.logger import Logger
import time


@depends.inject
async def operation_with_logging_context(logger: Inject[Logger]):
    start_time = time.time()

    try:
        logger.info("Starting complex operation")

        # Your operation here
        await complex_async_operation()

        duration = time.time() - start_time
        logger.info("Operation completed successfully", duration_seconds=duration)

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Operation failed",
            error=str(e),
            duration_seconds=duration,
            exc_info=True,  # Include full traceback
        )
        raise
```

### Custom Log Formatting

```python
from acb.depends import depends, Inject
from acb.logger import Logger


@depends.inject
async def custom_formatting_example(logger: Inject[Logger]):
    # Format messages with context
    request_id = "req-123-456"

    # Use logger context binding
    request_logger = logger.bind(request_id=request_id)

    request_logger.info("Processing request")
    request_logger.info("Validating input data")
    request_logger.info("Request processed successfully")
```

### Integration with Debug Module

```python
from acb.debug import debug, timeit
from acb.depends import depends, Inject
from acb.logger import Logger


@timeit
@depends.inject
async def debug_and_log_example(data: dict, logger: Inject[Logger]):
    # Quick debug output (development only)
    debug(f"Processing {len(data)} items")

    # Structured logging (all environments)
    logger.info("Data processing started", item_count=len(data))

    try:
        result = await process_data(data)

        logger.info(
            "Data processing completed", item_count=len(data), result_count=len(result)
        )
        return result

    except Exception as e:
        logger.error(
            "Data processing failed", item_count=len(data), error=str(e), exc_info=True
        )
        raise
```

## Log Filtering and Routing

### Module-Specific Logging

```yaml
# In settings/debug.yaml, control per-module logging
debug:
  logging: true
  cache: true      # Enable cache module logging
  storage: false   # Disable storage module logging
  sql: true       # Enable SQL module logging
```

### Custom Log Sinks

```python
import sys
from loguru import logger

# Add custom sink for errors only
logger.add(
    "logs/errors.log",
    level="ERROR",
    format="{time} | {level} | {message}",
    rotation="1 day",
    retention="1 week",
)

# Add JSON sink for structured data
logger.add("logs/structured.json", serialize=True, level="INFO")
```

## Performance Considerations

### Async Logging Performance

```python
from acb.depends import depends, Inject
from acb.logger import Logger
import asyncio


@depends.inject
async def high_performance_logging(logger: Inject[Logger]):
    # Batch log operations when possible
    events = []

    for i in range(1000):
        events.append(
            {"event": "data_processed", "item_id": i, "timestamp": time.time()}
        )

    # Log batch summary instead of individual items
    logger.info(
        "Batch processing completed",
        batch_size=len(events),
        first_item=events[0]["item_id"],
        last_item=events[-1]["item_id"],
    )
```

### Conditional Logging

```python
from acb.depends import depends, Inject
from acb.config import Config
from acb.logger import Logger


@depends.inject
async def conditional_logging(
    data: dict, config: Inject[Config], logger: Inject[Logger]
):
    # Only log verbose information in debug mode
    if config.debug.enabled:
        logger.debug("Detailed processing info", data=data)

    # Always log important events
    logger.info("Processing completed", item_count=len(data))
```

## Error Handling and Logging

### Exception Logging

```python
from acb.depends import depends, Inject
from acb.logger import Logger


@depends.inject
async def error_handling_example(logger: Inject[Logger]):
    try:
        result = await risky_operation()
        return result

    except ValueError as e:
        logger.warning("Invalid input data", error=str(e), error_type="ValueError")
        raise

    except ConnectionError as e:
        logger.error(
            "External service unavailable",
            error=str(e),
            error_type="ConnectionError",
            service="external_api",
        )
        raise

    except Exception as e:
        logger.critical(
            "Unexpected error occurred",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,  # Include full traceback
        )
        raise
```

### Retry Logic with Logging

```python
import asyncio
from acb.depends import depends, Inject
from acb.logger import Logger


@depends.inject
async def retry_with_logging(
    operation_name: str, logger: Inject[Logger], max_retries: int = 3
) -> None:
    for attempt in range(max_retries + 1):
        try:
            logger.info(
                "Attempting operation",
                operation=operation_name,
                attempt=attempt + 1,
                max_retries=max_retries,
            )

            result = await some_operation()

            logger.info(
                "Operation succeeded", operation=operation_name, attempt=attempt + 1
            )
            return result

        except Exception as e:
            if attempt == max_retries:
                logger.error(
                    "Operation failed after all retries",
                    operation=operation_name,
                    attempts=max_retries + 1,
                    final_error=str(e),
                )
                raise
            else:
                logger.warning(
                    "Operation attempt failed, retrying",
                    operation=operation_name,
                    attempt=attempt + 1,
                    error=str(e),
                    retry_in_seconds=2**attempt,
                )
                await asyncio.sleep(2**attempt)  # Exponential backoff
```

## Integration Examples

### Web Application Logging

```python
from fastapi import FastAPI, Request
from acb.depends import depends, Inject
from acb.logger import Logger
import time

app = FastAPI()


@depends.inject
async def log_request_middleware(request: Request, call_next, logger: Inject[Logger]):
    start_time = time.time()

    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host,
    )

    response = await call_next(request)

    duration = time.time() - start_time

    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_seconds=duration,
    )

    return response
```

### Data Pipeline Logging

```python
from acb.depends import depends, Inject
from acb.logger import Logger
from acb.debug import timeit


@timeit
@depends.inject
async def data_pipeline_with_logging(input_data: list, logger: Inject[Logger]):
    pipeline_id = f"pipeline-{int(time.time())}"

    logger.info(
        "Pipeline started", pipeline_id=pipeline_id, input_count=len(input_data)
    )

    # Stage 1: Validation
    logger.info("Starting validation stage", pipeline_id=pipeline_id)
    validated_data = await validate_data(input_data)
    logger.info(
        "Validation completed",
        pipeline_id=pipeline_id,
        valid_count=len(validated_data),
        rejected_count=len(input_data) - len(validated_data),
    )

    # Stage 2: Processing
    logger.info("Starting processing stage", pipeline_id=pipeline_id)
    processed_data = await process_data(validated_data)
    logger.info(
        "Processing completed",
        pipeline_id=pipeline_id,
        processed_count=len(processed_data),
    )

    logger.info(
        "Pipeline completed successfully",
        pipeline_id=pipeline_id,
        final_count=len(processed_data),
    )

    return processed_data
```

## Best Practices

1. **Use Structured Logging**: Include relevant context in log messages
1. **Appropriate Log Levels**: Use the right level for each message type
1. **Performance Awareness**: Avoid logging in tight loops or high-frequency operations
1. **Sensitive Data**: Never log passwords, API keys, or personal information
1. **Context Binding**: Use logger binding for request/operation tracking
1. **Error Context**: Include relevant error context and stack traces
1. **Async Considerations**: Use async-compatible logging practices

## Troubleshooting

### Common Issues

**Logs Not Appearing**: Check log level configuration and ensure logger is properly injected.

**Performance Impact**: Reduce log frequency in hot paths or use conditional logging.

**Missing Context**: Use structured logging and context binding for better traceability.

**File Permission Errors**: Ensure the application has write permissions to log directories.
