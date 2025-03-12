> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Logger](./README.md)

# Logger Adapter

The Logger adapter provides a standardized interface for logging in ACB applications, with support for structured logging and multiple implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Structured Logging](#structured-logging)
  - [Module-Specific Log Levels](#module-specific-log-levels)
  - [Customizing Log Format](#customizing-log-format)
  - [Capturing Standard Library Logs](#capturing-standard-library-logs)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Implementation Details](#implementation-details)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Logger adapter offers a flexible and powerful logging system:

- Asynchronous logging for non-blocking operations
- Multiple backend implementations
- Structured log output (JSON or human-readable)
- Per-module log level configuration
- Customizable log formats and colors
- Integration with Python's standard logging
- Support for context-specific logging

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Loguru** | Feature-rich logging with structured output | Default choice for most applications |
| **Structlog** | Advanced structured logging | Applications requiring extensive log processing |

## Installation

```bash
# Install with Loguru support (default)
pdm add "acb[loguru]"

# Or install with structlog support
pdm add "acb[structlog]"

# Or include it with other dependencies
pdm add "acb[loguru,redis,sql]"
```

## Configuration

### Settings

Configure the logger adapter in your `settings/adapters.yml` file:

```yaml
# Use Loguru implementation (default)
logger: loguru

# Or use Structlog implementation
logger: structlog

# Or disable custom logging (not recommended)
logger: null
```

### Logger Settings

The logger adapter settings can be customized in your `settings/app.yml` file:

```yaml
logger:
  # General settings
  verbose: false
  deployed_level: "WARNING"  # Log level in production
  log_level: "INFO"          # Log level in development

  # Loguru-specific settings
  serialize: false           # Output structured JSON logs

  # Format customization
  format:
    time: "<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>"
    level: " <level>{level:>8}</level>"
    sep: " <b><w>in</w></b> "
    name: "<b>{extra[mod_name]:>20}</b>"
    line: "<b><e>[</e><w>{line:^5}</w><e>]</e></b>"
    message: "  <level>{message}</level>"

  # Module-specific log levels
  level_per_module:
    my_module: "DEBUG"
    another_module: "WARNING"

  # Custom level colors
  level_colors:
    DEBUG: "blue"
    INFO: "green"
    WARNING: "yellow"
    ERROR: "red"
    CRITICAL: "purple"
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the logger adapter
Logger = import_adapter("logger")

# Get the logger instance via dependency injection
logger = depends.get(Logger)

# Log at different levels
logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")

# Log with exception tracing
try:
    1 / 0
except Exception as e:
    logger.error(f"An error occurred: {e}", exc_info=True)
```

## Advanced Usage

### Structured Logging

You can use structured logging to add context and make logs more searchable:

```python
# Add structured context to logs
logger.info("User logged in", extra={"user_id": 12345, "ip_address": "192.168.1.1"})

# In JSON format (with serialize=True in settings), this produces:
# {"time": "2023-08-15T14:23:45.123Z", "level": "INFO", "message": "User logged in",
#  "user_id": 12345, "ip_address": "192.168.1.1", "module": "auth"}
```

### Module-Specific Log Levels

You can configure different log levels for different modules in your `app.yml`:

```yaml
logger:
  level_per_module:
    database: "WARNING"  # Reduce database module logging
    auth: "DEBUG"        # Increase auth module logging
```

You can also dynamically set debug flags in your code:

```python
from acb.config import debug

# Enable debug logging for a specific module
debug["auth"] = True  # Sets DEBUG level for auth module
```

### Customizing Log Format

You can customize the log format in your `app.yml` to fit your needs:

```yaml
logger:
  format:
    time: "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
    level: "<level>{level:>8}</level>"
    message: "{message}"
```

### Capturing Standard Library Logs

ACB automatically routes standard library logging through its logger system using `InterceptHandler`:

```python
import logging

# Standard logging is routed through ACB logger
logging.info("This will go through the ACB logger")
```

## Troubleshooting

### Common Issues

1. **Missing Log Outputs**
   - **Problem**: Logs are not appearing
   - **Solution**:
     - Check log level settings - they might be too restrictive
     - Verify the logger is properly initialized
     - Check for any sink configuration issues

2. **Performance Issues with Extensive Logging**
   - **Problem**: Logging slows down the application
   - **Solution**:
     - Use higher log levels in production (WARNING or above)
     - Disable debug logs for modules that produce excessive output
     - Consider using serialize=True for better performance with large volumes

3. **Missing Context Information**
   - **Problem**: Log entries lack module names or other context
   - **Solution**:
     - Ensure ACB is properly initialized
     - Check format settings to include context
     - Use structured logging with extra parameters

4. **Conflicting Log Formats**
   - **Problem**: Log formats from different systems don't match
   - **Solution**:
     - Use InterceptHandler to capture all logs
     - Standardize format settings
     - Ensure third-party libraries use the standard logging module

## Performance Considerations

When working with the Logger adapter, keep these performance factors in mind:

1. **Log Level Selection**:
   - DEBUG level logging generates significant output and can impact performance
   - In production, use WARNING level or higher for optimal performance

2. **Asynchronous Sink**:
   - The Logger adapter uses an asynchronous sink to prevent blocking the main application
   - This significantly improves performance in high-throughput scenarios

3. **Serialization Trade-offs**:
   | Setting | Pros | Cons |
   |---------|------|------|
   | `serialize: false` | Human-readable, colorized | More CPU processing, larger log size |
   | `serialize: true` | Faster performance, compact | Less readable by humans |

4. **Optimization Tips**:
   ```python
   # Avoid expensive operations inside log statements
   # Bad:
   logger.debug(f"User data: {get_detailed_user_data(user_id)}")

   # Good - check level first:
   if logger.level("DEBUG").no >= logger.level("INFO").no:
       logger.debug(f"User data: {get_detailed_user_data(user_id)}")
   ```

## Implementation Details

The Logger adapter implements these core methods:

```python
class LoggerBase:
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
    async def init(self) -> None: ...
```

The Loguru implementation includes these additional components:

- **Asynchronous Sink**: Uses `aioconsole.aprint` for non-blocking log output
- **InterceptHandler**: Captures standard library logging and routes it through Loguru
- **Module Name Patching**: Automatically extracts and formats module names for better context
- **Per-Module Filtering**: Allows different log levels for different modules

## Related Adapters

The Logger adapter works well with these other ACB adapters:

- [**Monitoring Adapter**](../monitoring/README.md): Send logs to monitoring systems
- [**Storage Adapter**](../storage/README.md): Persist logs to file or cloud storage
- [**NoSQL Adapter**](../nosql/README.md): Store structured logs in a document database

Integration example:

```python
# Send high-level logs to a monitoring service
from acb.depends import depends

# Get both adapters
Logger = depends.get("logger")
Monitoring = depends.get("monitoring")

# Custom handler that sends critical errors to the monitoring service
class MonitoringHandler:
    def __init__(self):
        self.monitoring = depends.get(Monitoring)

    def __call__(self, record):
        # Only send ERROR and CRITICAL logs to monitoring
        if record["level"].no >= Logger.level("ERROR").no:
            self.monitoring.report_error(
                title=f"{record['level'].name}: {record['message']}",
                extra=record["extra"]
            )
        return True

# Add the custom handler (during application initialization)
Logger.configure(handlers=[MonitoringHandler()])
```

## Additional Resources

- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Structlog Documentation](https://www.structlog.org/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [ACB Monitoring Adapter](../monitoring/README.md)
- [ACB Adapters Overview](../README.md)
