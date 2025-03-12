> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Logger](./README.md)

# Logger Adapter

The Logger adapter provides a standardized interface for application logging in ACB applications, with support for Loguru and structlog implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Settings](#settings)
  - [Detailed Settings](#detailed-settings)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Structured Logging](#structured-logging)
  - [Context-Based Logging](#context-based-logging)
  - [Log Filtering](#log-filtering)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Logger adapter offers:

- Consistent logging interface across your application
- Structured logging with rich context
- Multiple output formats (console, JSON, file)
- Asynchronous logging for non-blocking performance
- Log level control and filtering
- Integration with monitoring systems

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Loguru** | Feature-rich logging with Loguru | Default choice, colorful console output, development |
| **Structlog** | Structured logging with structlog | Production, JSON logging, log aggregation systems |

## Installation

```bash
# Install with logging support
pdm add "acb[logging]"

# Or include it with other dependencies
pdm add "acb[logging,monitoring]"
```

## Configuration

### Settings

Configure the Logger adapter in your `settings/adapters.yml` file:

```yaml
# Use Loguru implementation (default)
logger: loguru

# Or use Structlog implementation
logger: structlog
```

### Detailed Settings

The Logger adapter settings can be customized in your `settings/app.yml` file:

```yaml
logger:
  # Log level (debug, info, warning, error, critical)
  level: "info"

  # Log format
  format: "{time} | {level} | {message}"

  # Output destinations
  outputs:
    - type: "console"
      colorize: true
    - type: "file"
      path: "logs/app.log"
      rotation: "10 MB"
      retention: "1 week"
    - type: "json"
      path: "logs/app.json"

  # Loguru-specific settings
  loguru:
    backtrace: true
    diagnose: true

  # Structlog-specific settings
  structlog:
    processors:
      - "TimeStamper"
      - "ExceptionPrettyPrinter"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the logger adapter (automatically selects the one enabled in config)
Logger = import_adapter("logger")

# Get the logger instance via dependency injection
logger = depends.get(Logger)

# Basic logging
logger.info("Application started")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical failure")

# Logging with variables
user_id = "user123"
logger.info(f"User {user_id} logged in")

# Logging exceptions
try:
    result = 1 / 0
except Exception as e:
    logger.exception("Division by zero error")
```

## Advanced Usage

### Structured Logging

```python
from acb.depends import depends
from acb.adapters import import_adapter

Logger = import_adapter("logger")
logger = depends.get(Logger)

# Log with structured data
logger.info("User logged in",
    user_id="user123",
    ip_address="192.168.1.1",
    login_method="oauth",
    session_id="abc123"
)

# Log with nested structured data
logger.info("Order processed",
    order={
        "id": "order123",
        "total": 99.99,
        "items": 3,
        "shipping_method": "express"
    },
    customer={
        "id": "cust456",
        "tier": "premium"
    }
)
```

### Context-Based Logging

```python
# Create a contextualized logger
user_logger = logger.bind(
    user_id="user123",
    session_id="abc123"
)

# All logs from this logger will include the bound context
user_logger.info("User viewed product", product_id="prod456")
user_logger.warning("Failed login attempt", attempt=3)

# Context managers for temporary context
with logger.contextualize(request_id="req789"):
    logger.info("Processing request")
    # ... processing code ...
    logger.info("Request completed")
```

### Log Filtering

```python
# Filter logs for specific modules
module_logger = logger.get_logger("acb.adapters.sql")
module_logger.set_level("debug")  # More verbose for this module

# Create a filtered logger
filtered_logger = logger.filter(lambda record: record["level"].no >= logger.level("warning").no)

# Use the filtered logger
filtered_logger.debug("This won't be logged")
filtered_logger.warning("This will be logged")
```

## Troubleshooting

### Common Issues

1. **Missing Logs**
   - **Problem**: Logs not appearing where expected
   - **Solution**: Check log level settings and output configurations

2. **Performance Issues**
   - **Problem**: Logging causing performance bottlenecks
   - **Solution**: Use async logging, reduce log verbosity, or batch logs

3. **File Permission Errors**
   - **Problem**: `PermissionError: [Errno 13] Permission denied: 'logs/app.log'`
   - **Solution**: Ensure the application has write permissions to the log directory

4. **Memory Leaks**
   - **Problem**: Growing memory usage with extensive logging
   - **Solution**: Configure log rotation, limit context size, and avoid logging large objects

## Implementation Details

The Logger adapter implements these core methods:

```python
class LoggerBase:
    def debug(self, message: str, **kwargs) -> None: ...
    def info(self, message: str, **kwargs) -> None: ...
    def warning(self, message: str, **kwargs) -> None: ...
    def error(self, message: str, **kwargs) -> None: ...
    def critical(self, message: str, **kwargs) -> None: ...
    def exception(self, message: str, **kwargs) -> None: ...

    def bind(self, **kwargs) -> "LoggerBase": ...
    def contextualize(self, **kwargs) -> ContextManager: ...
    def get_logger(self, name: str) -> "LoggerBase": ...
    def set_level(self, level: str) -> None: ...
    def level(self, level_name: str) -> Any: ...
    def filter(self, filter_fn: Callable) -> "LoggerBase": ...
```

## Related Adapters

- [**Monitoring Adapter**](../monitoring/README.md): Send logs to monitoring systems
- [**SQL Adapter**](../sql/README.md): Log database operations
- [**Storage Adapter**](../storage/README.md): Log file operations

## Additional Resources

- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Structlog Documentation](https://www.structlog.org/en/stable/)
- [Logging Best Practices](https://www.loggly.com/blog/logging-best-practices/)
- [ACB Adapters Overview](../README.md)
- [ACB Configuration Guide](../../README.md)
